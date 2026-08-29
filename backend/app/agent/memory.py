"""
Durable per-member memory that the model cannot write to.

The usual way to build this is to give the model a save_memory() tool. We
deliberately do not, and the reason is not cost (see decision 4.10 in the
architecture report):

  - Group descriptions and announcements are user-authored text that flows
    into the model's context. If the model could write durable memory, a
    crafted group description could plant an instruction that survives across
    sessions. That is a stored prompt-injection with a long half-life.
  - Nothing would validate a model-authored memory. The entire architecture
    rests on the model never being the authority on facts about a real
    member.

So memory here is *derived*, never authored. Facts come from things that
actually happened in the system - an approved membership, a confirmed
registration, interest text the member typed themselves. There is no entry
in the tool registry that writes memory, so no prompt can reach this code.

Storage is a small JSON file rather than a database table. This service does
not own the members table (that lives in the deployed API), the whole record
is at most ten short facts per member, and a file keeps the offline test
suite genuinely offline with no migration to run. If this outgrows a file, the
shape below maps one-to-one onto an ai_member_memory table.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

# backend/app/agent/memory.py -> parents[2] is backend/
STORE_PATH = Path(__file__).resolve().parents[2] / "var" / "member_memory.json"

# Keep the injected context small; this rides in every request's prompt.
MAX_FACTS_PER_MEMBER = 10

# One lock for the whole file. Writes are rare (a handful per conversation)
# and tiny, so a single lock is simpler and safer than per-key locking.
_LOCK = threading.Lock()


def _load_all() -> dict:
    if not STORE_PATH.exists():
        return {}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        # A corrupt store must not break the assistant; it just means no
        # personalisation this turn.
        return {}
    return data if isinstance(data, dict) else {}


def _save_all(data: dict) -> None:
    """Write atomically so a crash mid-write cannot corrupt the store."""
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(STORE_PATH.parent),
        delete=False,
    )
    try:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, STORE_PATH)


def remember(member_key: str, fact_key: str, value: str) -> None:
    """
    Record one derived fact.

    Callers are system events, never the model. fact_key is a stable slug
    such as "joined_group:7" or "interest:robotics" so repeat observations
    update in place instead of accumulating duplicates.
    """
    if not member_key or member_key == "anonymous" or not fact_key:
        return

    with _LOCK:
        data = _load_all()
        facts = data.get(member_key)
        if not isinstance(facts, dict):
            facts = {}

        facts[str(fact_key)] = str(value)[:200]

        # Cap the record. dicts preserve insertion order, so dropping from the
        # front discards the oldest observations first.
        while len(facts) > MAX_FACTS_PER_MEMBER:
            oldest = next(iter(facts))
            facts.pop(oldest)

        data[member_key] = facts
        _save_all(data)


def recall(member_key: str) -> dict:
    """Every stored fact for one member. Empty dict when there is none."""
    if not member_key or member_key == "anonymous":
        return {}
    with _LOCK:
        facts = _load_all().get(member_key)
    return facts if isinstance(facts, dict) else {}


def forget(member_key: str) -> None:
    """Delete a member's whole record. Used by tests and by data requests."""
    with _LOCK:
        data = _load_all()
        if member_key in data:
            del data[member_key]
            _save_all(data)


def record_interest(member_key: str, interest_text: str) -> None:
    """
    Derive interest facts from text the member typed themselves.

    Tokenisation is reused from the deterministic recommender so the stored
    keywords are exactly the ones ranking already uses - no second notion of
    "what counts as an interest" to drift out of step.
    """
    from app.agent import recommender as R

    tokens = R.normalize_tokens(interest_text or "")

    # Keep only words that are recognisably about an interest. Ranking by
    # length alone stored things like "already", "part" and "option" from
    # ordinary questions, and those then read back into the system prompt as
    # "interests they have mentioned before", which is both wrong and, once
    # the per-member cap is reached, evicts real facts.
    #
    # Precision matters more than recall here: a remembered interest is
    # asserted to the model as fact, so it is better to remember nothing than
    # to remember noise.
    recognised = [tok for tok in tokens if R.mapped_category(tok)]

    ranked = sorted(recognised, key=len, reverse=True)[:3]
    for token in ranked:
        remember(member_key, "interest:" + token, token)


def record_memberships(member_key: str, membership_rows: list) -> None:
    """
    Derive facts from confirmed memberships.

    The rows come from the get_my_groups tool, which projects MyGroupItem down
    to id / name / category / membership_role / membership_status. The field
    names below must match that projection - reading a `status` or `group_id`
    key here would silently record nothing, which is exactly what this used
    to do.
    """
    approved = ("APPROVED", "ACTIVE")

    for row in membership_rows or []:
        if not isinstance(row, dict):
            continue

        status = row.get("membership_status") or row.get("status") or ""
        if str(status).upper() not in approved:
            continue

        group_id = row.get("id") or row.get("group_id")
        group_name = row.get("name") or row.get("group_name")

        if group_id and group_name:
            remember(member_key, "joined_group:" + str(group_id), str(group_name))


def as_prompt_context(member_key: str) -> Optional[str]:
    """
    Render the stored facts as a short block for the system prompt.

    Returns None when there is nothing to say, so callers can skip the
    section entirely rather than injecting an empty header.
    """
    facts = recall(member_key)
    if not facts:
        return None

    joined = []
    interests = []
    for key, value in facts.items():
        if key.startswith("joined_group:"):
            joined.append(value)
        elif key.startswith("interest:"):
            interests.append(value)

    lines = []
    if joined:
        lines.append("Groups this member has already joined: " + ", ".join(joined) + ".")
    if interests:
        lines.append("Interests they have mentioned before: " + ", ".join(interests) + ".")

    if not lines:
        return None

    lines.append(
        "Use this for context only. Verify anything you state with a tool before "
        "relying on it, and do not suggest a group they are already in."
    )
    return "\n".join(lines)
