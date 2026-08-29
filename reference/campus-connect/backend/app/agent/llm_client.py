"""
Haiku client for the AI Club Finder (design doc Section 4).

Calls the real Anthropic API only when ANTHROPIC_API_KEY is set; otherwise
falls back to a deterministic mock so the feature - and its tests - keep
working with no key and no network call. The real client only ever gets to
phrase reason text on top of the deterministic ranking from recommender.py -
it never decides which clubs or events exist.

Security: the key is read once from the environment (backend/.env, which is
gitignored) via python-dotenv + os.getenv. It is never hardcoded, logged, or
echoed back in any response body - callers only ever see the phrased text.
Put your key in backend/.env as:
    ANTHROPIC_API_KEY=sk-ant-...
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

# Resolve backend/.env explicitly instead of relying on load_dotenv()'s
# cwd-relative search, which silently no-ops (leaving _API_KEY empty and
# every call falling back to the mock) if uvicorn isn't launched from
# exactly the backend/ directory.
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

_MODEL = "claude-haiku-4-5-20251001"
_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

_cache: dict[str, str] = {}   # key -> raw text (swap for a TTL cache in prod)
_client = None


def _get_client():
    """Lazily construct the Anthropic client - only touched once a key exists,
    so `anthropic` never needs to be imported (or even installed) in mock mode."""
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic(api_key=_API_KEY)
    return _client


def _key(*parts: str) -> str:
    return hashlib.sha256("||".join(parts).encode()).hexdigest()


# ---------------------------------------------------------------------------
# mock fallbacks - used whenever no ANTHROPIC_API_KEY is configured
# ---------------------------------------------------------------------------
_CANDIDATE_RE = re.compile(r"club_id=(\d+) \| ([^|]+) \| ([^|]+) \|")
_AVAILABLE_ENTITY_RE = re.compile(r"\[\[(club|event):(\d+)\]\] ([^(\-]+)")


def _mock_finder(prompt: str) -> str:
    reasons = [
        {"club_id": int(club_id), "reason": f"Matches your interests and fits {category.strip().lower()} activities."}
        for club_id, name, category in _CANDIDATE_RE.findall(prompt)
    ]
    return json.dumps(reasons)


def _mock_chat(system_prompt: str) -> str:
    match = _AVAILABLE_ENTITY_RE.search(system_prompt)
    if not match:
        return "I could not find a club or public event that matches yet - try describing a different interest."

    kind, entity_id, name = match.group(1), match.group(2), match.group(3).strip()
    return f"You might like [[{kind}:{entity_id}]] - {name} looks like a good fit for what you described."


_LISTING_LINE_RE = re.compile(r'^- "?([^"\n(]+)', re.MULTILINE)


def _mock_message(prompt: str) -> str:
    names = [n.strip() for n in _LISTING_LINE_RE.findall(prompt)]
    if not names:
        return "Nothing matched closely, but here are some active options on campus."
    preview = " and ".join(names[:2])
    return f"Nothing matched exactly, but {preview} might still be worth checking out."


# ---------------------------------------------------------------------------
# public interface
# ---------------------------------------------------------------------------
def call_finder(prompt: str, candidate_hash: str) -> str:
    """Single-shot, deterministic. Cached by (prompt, candidate set)."""
    k = _key(prompt, candidate_hash)
    if k in _cache:
        return _cache[k]

    if _API_KEY:
        resp = _get_client().messages.create(
            model=_MODEL, max_tokens=150, temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
    else:
        text = _mock_finder(prompt)

    _cache[k] = text
    return text


def call_chat(system_prompt: str, history: list[dict]) -> str:
    """Multi-turn. history = [{role, content}, ...]. Grounded via system prompt."""
    if _API_KEY:
        resp = _get_client().messages.create(
            model=_MODEL, max_tokens=200, temperature=0.3,
            system=system_prompt, messages=history,
        )
        return resp.content[0].text

    return _mock_chat(system_prompt)


def call_message(prompt: str) -> str:
    """Single-shot free-form phrasing for the finder's top-level assistant
    reply (see recommender.build_conversational_message_prompt). Cached by
    the prompt text alone - there is no separate candidate set to key on."""
    k = _key("message", prompt)
    if k in _cache:
        return _cache[k]

    if _API_KEY:
        resp = _get_client().messages.create(
            model=_MODEL, max_tokens=120, temperature=0.4,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
    else:
        text = _mock_message(prompt)

    _cache[k] = text
    return text
