"""
Quorum - AI Group & Event Recommender (deterministic core).

Design rule (Episteme pattern): every function here is PURE and deterministic.
The LLM only writes free-text reasons on top of this ranking; it is NEVER
allowed to decide which groups exist or to invent entities. If the LLM call
fails, callers fall back to the deterministic order produced here.

No network calls, no DB access, no email fields. Unit-testable in isolation.
Takes plain dicts so it works before the groups/events schema exists.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# The trailing (?:\|[^\]]*)? tolerates a model writing [[group:7|Some Label]]
# instead of the bare [[group:7]] it was told to - a real drift we saw in
# production output. Whatever label the model put there is discarded; the
# allow-list's own name is always what gets substituted in, so a stale or
# invented label can never leak through.
_ENTITY_RE = re.compile(r"\[\[(group|event):(\d+)(?:\|[^\]]*)?\]\]")

# Small, dependency-free stopword set. Keep deterministic.
_STOP = {
    "the", "and", "for", "with", "this", "that", "group", "groups", "like",
    "love", "want", "interested", "interest", "hobby", "hobbies", "join",
    "campus", "tenant", "member", "members", "really", "very",
    # Question and request framing.
    "any", "anything", "some", "something", "someone", "there", "have", "has",
    "had", "does", "doe", "did", "are", "was", "were", "can", "could", "would",
    "should", "will", "you", "your", "our", "ours", "not", "but", "how", "what",
    "which", "who", "whom", "whose", "where", "why", "here",
    "find", "show", "tell", "give", "get", "know", "need", "looking", "look",
    "suggest", "suggestion", "suggestions", "recommend", "recommendation",
    "recommendations", "please", "about", "into", "from", "out", "also", "just",
    "good", "great", "best", "nice", "cool", "help", "available", "option",
    "options", "thing", "things", "one", "ones", "something",
}

# interest keyword -> canonical group category (lowercase)
INTEREST_CATEGORY_MAP = {
    "coding": "technology", "programming": "technology", "robotics": "technology",
    "ai": "technology", "ml": "technology", "web": "technology", "app": "technology",
    "painting": "arts", "sketching": "arts", "design": "arts", "photography": "arts",
    "football": "sports", "cricket": "sports", "chess": "sports", "fitness": "sports",
    "astronomy": "science", "physics": "science", "biology": "science", "space": "science",
    "reading": "literature", "writing": "literature", "poetry": "literature", "debate": "literature",
    "music": "cultural", "dance": "cultural", "drama": "cultural", "theatre": "cultural",
    "gaming": "gaming", "esports": "gaming",
}


@dataclass(frozen=True)
class ScoreConfig:
    w_interest: float = 0.55
    w_category: float = 0.20
    w_branch: float = 0.10
    w_popularity: float = 0.15
    group_threshold: float = 0.30
    event_threshold: float = 0.25
    top_k: int = 10
    branch_category: dict = field(default_factory=lambda: {
        "cse": "technology", "cs": "technology", "it": "technology",
        "ece": "technology", "eee": "technology", "design": "arts",
    })


DEFAULT_CFG = ScoreConfig()


# ---------------------------------------------------------------------------
# tokenisation
# ---------------------------------------------------------------------------
def normalize_tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 2}


def profile_tokens(profile: dict) -> set[str]:
    parts = list(profile.get("interests") or []) + list(profile.get("hobbies") or [])
    parts.append(profile.get("reason") or "")
    return normalize_tokens(" ".join(parts))


def _item_tokens(*texts: str) -> set[str]:
    return normalize_tokens(" ".join(t for t in texts if t))


# How many derived tags a group is allowed to show. Enough to characterise it,
# few enough to fit a card without wrapping.
_MAX_DERIVED_TAGS = 4


def derive_tags(group: dict) -> list[str]:
    """
    Work out a group's topic tags from the data the schema already has.

    There is no tags column on groups, so rather than inventing one (a
    migration against a shared database) or letting the model make tags up
    (ungrounded), tags are read out of the group's own name, category and
    description using the same vocabulary the recommender already scores
    against. Every tag returned is therefore a word the group actually used
    about itself, or the category an admin already assigned it.

    Ordering is deliberate: the category first because it is curated, then
    matched interest keywords in vocabulary order so the same group always
    produces the same tags.
    """
    tags: list[str] = []

    category = (group.get("category") or "").strip()
    if category:
        tags.append(category.title())

    text = _item_tokens(
        group.get("name", ""), group.get("description", ""),
    )

    for keyword in INTEREST_CATEGORY_MAP:
        if len(tags) >= _MAX_DERIVED_TAGS:
            break

        matched = keyword in text or any(_same_family(tok, keyword) for tok in text)
        if not matched:
            continue

        label = keyword.title()
        if label.lower() not in {t.lower() for t in tags}:
            tags.append(label)

    return tags[:_MAX_DERIVED_TAGS]


# How many leading characters two words must share to count as the same word
# family. Five is the smallest value that connects robots/robotics and
# photo/photography without also connecting design/desire.
_PREFIX_MIN = 5


def _same_family(a: str, b: str) -> bool:
    if len(a) < _PREFIX_MIN or len(b) < _PREFIX_MIN:
        return False
    return a[:_PREFIX_MIN] == b[:_PREFIX_MIN]


def _matches_token(token: str, item_tokens: set[str]) -> bool:
    """
    Does one member token match anything in the item's text?

    Exact match first, then a shared-prefix test. Without the second test a
    member who writes "robots" scores zero against a group whose description
    says "robotics", which is the single most common way the ranker missed an
    obvious fit and dropped to the popularity fallback. A real stemmer would
    handle more cases, but it would be a dependency and a source of non-obvious
    behaviour; a fixed prefix is deterministic and readable.
    """
    if token in item_tokens:
        return True
    return any(_same_family(token, other) for other in item_tokens)


# Beyond this many signal words, extra ones stop diluting the score. A member
# who types a full sentence gives us more filler, not less evidence, and
# dividing by every token meant "I really like building robots and electronics"
# scored lower than "robots" for the same match.
_SIGNAL_CAP = 4


# What a shared-prefix match is worth next to an exact one. Half credit, not
# full, so a lone stem coincidence cannot qualify an item by itself.
_FUZZY_CREDIT = 0.5


def _match_credit(token: str, item_tokens: set[str]) -> float:
    """How strongly one member token matches the item's text. In [0, 1]."""
    if token in item_tokens:
        return 1.0
    if any(_same_family(token, other) for other in item_tokens):
        return _FUZZY_CREDIT
    return 0.0


def _overlap(a: set[str], b: set[str]) -> float:
    """Fraction of the member's signals that the item matches. In [0, 1]."""
    if not a or not b:
        return 0.0
    matched = sum(_match_credit(token, b) for token in a)
    return min(matched / min(len(a), _SIGNAL_CAP), 1.0)


def mapped_category(token: str) -> str | None:
    """
    Public alias of _mapped_category.

    agent/memory.py uses this to decide whether a word is recognisably about
    an interest before storing it as a durable fact.
    """
    return _mapped_category(token)


def _mapped_category(token: str) -> str | None:
    """The canonical category one interest word implies, allowing word families."""
    direct = INTEREST_CATEGORY_MAP.get(token)
    if direct:
        return direct
    for keyword, category in INTEREST_CATEGORY_MAP.items():
        if _same_family(token, keyword):
            return category
    return None


def _category_hit(ptokens: set[str], category: str) -> float:
    cat = (category or "").lower()
    return 1.0 if any(_mapped_category(tok) == cat for tok in ptokens) else 0.0


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
def score_group(profile: dict, group: dict, max_activity: int, cfg: ScoreConfig = DEFAULT_CFG) -> float:
    p = profile_tokens(profile)
    text = _item_tokens(
        group.get("name", ""), group.get("category", ""),
        group.get("description", ""), " ".join(group.get("tags") or []),
    )
    interest = _overlap(p, text)
    category = _category_hit(p, group.get("category", ""))
    branch = 1.0 if cfg.branch_category.get((profile.get("branch") or "").lower()) \
        == (group.get("category") or "").lower() else 0.0
    pop = (group.get("activity_score", 0) / max_activity) if max_activity else 0.0
    score = (cfg.w_interest * interest + cfg.w_category * category
             + cfg.w_branch * branch + cfg.w_popularity * pop)
    return round(min(score, 1.0), 4)


def score_event(profile: dict, event: dict, cfg: ScoreConfig = DEFAULT_CFG) -> float:
    p = profile_tokens(profile)
    # group_name counts as part of an event's own text - the hosting group's
    # own word for itself, the same text score_group already reads.
    text = _item_tokens(
        event.get("title", ""), event.get("description", ""),
        event.get("group_name", ""),
    )
    return round(_overlap(p, text), 4)


# ---------------------------------------------------------------------------
# selection: groups first -> event fallback -> popularity fallback
#
# The event set passed in is already the discoverable one: upcoming events of
# APPROVED groups in the member's tenant (see discovery layer). The schema
# has no public/private event flag, so there is nothing to filter here - every
# event handed to this function is fair game.
# ---------------------------------------------------------------------------
def select_recommendations(profile: dict, groups: list[dict], events: list[dict],
                           cfg: ScoreConfig = DEFAULT_CFG) -> dict:
    max_activity = max((c.get("activity_score", 0) for c in groups), default=0)
    scored = sorted(
        ({**c, "_score": score_group(profile, c, max_activity, cfg)} for c in groups),
        key=lambda c: (c["_score"], c.get("activity_score", 0)),
        reverse=True,
    )
    matched = [c for c in scored if c["_score"] >= cfg.group_threshold]
    if matched:
        return {"kind": "groups", "items": matched[:cfg.top_k]}

    # fallback 1: closest matching events
    scored_e = sorted(
        ({**e, "_score": score_event(profile, e, cfg)} for e in events),
        key=lambda e: e["_score"], reverse=True,
    )
    ev = [e for e in scored_e if e["_score"] >= cfg.event_threshold]
    if ev:
        best = ev[0]
        top_events = [
            {**e, "reason": f'Hosted by {e.get("group_name", "a group")} - closest match to what you described.'}
            for e in ev[:3]
        ]
        return {
            "kind": "event_fallback",
            "items": top_events,
            # Deterministic safety net only - routers/ai.py overwrites this
            # with an LLM-phrased message when interest_text is present, and
            # only falls back to this string if that call fails.
            "message": (
                f'I could not find a group that matches, but the event '
                f'"{best["title"]}" covered something similar. It is run by '
                f'{best.get("group_name", "a group")} '
                f'(organiser: {best.get("leader_name", "the group lead")}). '
                f'You can reach out through the platform if you would like to know more.'
            ),
        }

    # fallback 2: most active groups
    pop = sorted(groups, key=lambda c: c.get("activity_score", 0), reverse=True)
    top_popular = [
        {**c, "reason": f"Ranked #{i + 1} by member activity on campus."}
        for i, c in enumerate(pop[:cfg.top_k])
    ]
    return {
        "kind": "popularity",
        "items": top_popular,
        # Deterministic safety net only - see comment above.
        "message": "Nothing matched your exact interests yet, so here are the most active groups on campus.",
    }


# ---------------------------------------------------------------------------
# LLM output handling (validation + grounding)
# ---------------------------------------------------------------------------
def strip_code_fences(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[A-Za-z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def validate_finder_json(raw: str, allowed_ids: set[int]) -> list[dict]:
    """Parse strict-JSON finder output. Raises on malformed input (caller
    falls back to deterministic order). Drops any group_id not in candidates."""
    data = json.loads(strip_code_fences(raw))
    if not isinstance(data, list):
        raise ValueError("expected a JSON array")
    out, seen = [], set()
    for item in data:
        if not isinstance(item, dict):
            continue
        cid = item.get("group_id")
        if cid in allowed_ids and cid not in seen:
            out.append({"group_id": cid, "reason": str(item.get("reason", "")).strip()[:200]})
            seen.add(cid)
    return out


def resolve_entities(text: str, allowed_map: dict) -> tuple[str, list[tuple[str, int]]]:
    """Replace [[group:ID]] / [[event:ID]] with names from allowed_map.
    Unknown IDs are never surfaced. Returns (clean_text, unknown_refs).
    allowed_map keys: ("group", id) / ("event", id) -> display name."""
    unknown: list[tuple[str, int]] = []

    def repl(m: re.Match) -> str:
        kind, sid = m.group(1), int(m.group(2))
        name = allowed_map.get((kind, sid))
        if name:
            return name
        unknown.append((kind, sid))
        return "that option"

    resolved = _ENTITY_RE.sub(repl, text)

    return _collapse_repeated_names(resolved, allowed_map), unknown


def _collapse_repeated_names(text: str, allowed_map: dict) -> str:
    """
    Fix "Photography Circle Photography Circle".

    Models often write the group's name AND the reference tag next to each
    other ("you're in Photography Circle [[group:4]]"), and expanding the tag
    then prints the name twice. Rather than fight it in the prompt - which
    only ever reduces the odds - collapse an immediate repeat after
    substitution, where it is unambiguous.

    Only names the allow-list actually produced are collapsed, so this can
    never alter a member's own words or a legitimate repetition elsewhere in
    the sentence.
    """
    for name in set(allowed_map.values()):
        if not name:
            continue
        # Same name twice, separated by nothing more than a short bridge of
        # punctuation/quoting, optionally with a determiner.
        bridge = r"[\s,\-–—:;\"'“”‘’()]*(?:the|a|an)?[\s,\-–—:;\"'“”‘’()]*"
        pattern = re.compile(
            r"\b" + re.escape(name) + r"\b" + bridge + re.escape(name) + r"\b[\"'“”]*",
            re.IGNORECASE,
        )
        text = pattern.sub(name, text)

    return text


def scrub_emails(text: str) -> str:
    return _EMAIL_RE.sub("[hidden]", text)


# A leading list marker: "- ", "* ", "• ", "1. ", "2) ", or a bare marker on
# its own line. Indented/nested bullets are covered by the leading \s*.
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•–—]|\d{1,2}[.)])(?:\s+|$)")

# An internal-format heading label at the start of a line ("MATCHED GROUPS:",
# "CANDIDATE EVENTS:"). >=3 chars so a short acronym in prose is not eaten,
# and it only ever removes the LABEL, never the line.
_LEAK_HEADING_RE = re.compile(r"^\s*[A-Z][A-Z ]{2,}:\s*")


def strip_echoed_listing(text: str) -> str:
    """Stop the model echoing the internal candidate block back as prose.
    Normalises rather than deletes: only a line that is nothing but a marker
    or a bare label is dropped, so real content is never lost."""
    out: list[str] = []
    for line in text.splitlines():
        cleaned = _LEAK_HEADING_RE.sub("", _LIST_MARKER_RE.sub("", line)).strip()
        if not cleaned and line.strip():
            continue  # marker/label only - nothing lost
        out.append(cleaned)
    return "\n".join(out).strip()


# ---------------------------------------------------------------------------
# prompt builders (pure)
# ---------------------------------------------------------------------------
def build_finder_prompt(profile: dict, top_groups: list[dict]) -> str:
    lines = [
        f'- group_id={c["id"]} | {c["name"]} | {c.get("category", "")} | {c.get("description", "")[:160]}'
        for c in top_groups
    ]
    interests = ", ".join((profile.get("interests") or []) + (profile.get("hobbies") or [])) or "general"
    return (
        "You match members to campus groups. Only use groups from the CANDIDATES list.\n"
        "Never invent a group or a group_id. Return STRICT JSON only - no prose, no code fences.\n"
        'Format: [{"group_id": <int from list>, "reason": "<=20 words, specific to the member"}]\n'
        f"Member interests: {interests}\n"
        "CANDIDATES:\n" + "\n".join(lines)
    )


CHAT_SYSTEM_PROMPT = (
    "You are Quorum's group assistant. You help members discover groups and events.\n"
    "HARD RULES:\n"
    "1. Only mention groups/events from the AVAILABLE list below. Never invent one.\n"
    "2. Reference any group as [[group:ID]] and any event as [[event:ID]] using the exact IDs given.\n"
    "3. If nothing matches, say so plainly; if an event fits, mention it and that the member "
    "can contact the organiser through the platform. Never reveal email addresses.\n"
    "4. Keep replies under 90 words.\n"
    "AVAILABLE:\n{available}\n"
)


def build_conversational_message_prompt(interest_text: str, kind: str, items: list[dict],
                                        remaining: int = 0) -> str:
    """Prompt for the top-level assistant reply shown above the result cards.

    Strictly grounded: the model is only ever given the names of items the
    deterministic core already selected, and told not to introduce anything
    else. It writes the *tone*, never the *selection*.
    """
    rules = (
        "You are Quorum's group assistant, replying to a member who just "
        "described their interests. Sound like a helpful, honest person - not a "
        "template. Reference specific things they said. Never invent a group or "
        "event name beyond the list given below.\n"
    )

    if remaining > 0:
        follow_up = (
            f"End with a short, natural follow-up question - there are {remaining} more "
            "matches you could show, so offer to bring them up (e.g. ask if they'd like "
            "to see a few more, or want events too)."
        )
    else:
        follow_up = (
            "End with a short, natural follow-up question to keep the conversation going "
            "- for example ask if they'd like related events, or to refine what they're after."
        )

    output_format = (
        "\nOutput as GitHub-flavoured Markdown: you may use **bold** for group or event "
        "names and keep it to 2-3 short sentences, under 60 words. " + follow_up +
        " Do not repeat, quote, or bullet-list the items above - the app already shows "
        "them as cards below your message. No headings, no code fences, no labels like "
        "'Reply:' - just your message."
    )

    if kind == "groups":
        listing = "\n".join(f'- {c["name"]} ({c.get("category", "")})' for c in items[:5])
        return (
            rules
            + f'The member described their interests as: "{interest_text}"\n'
            + "These groups matched - write a short, warm intro line to precede the "
              "list (do not restate their interests verbatim, paraphrase them):\n"
            + f"MATCHED GROUPS:\n{listing}\n"
            + output_format
        )

    if kind == "event_fallback":
        listing = "\n".join(
            f'- "{e["title"]}" hosted by {e.get("group_name", "a group")}' for e in items[:3]
        )
        return (
            rules
            + f'The member described their interests as: "{interest_text}"\n'
            + "No group matched closely, but these events did. Write an honest "
              "reply that says so, then introduces the event(s) as a next-best option:\n"
            + f"MATCHED EVENTS:\n{listing}\n"
            + output_format
        )

    listing = "\n".join(f'- {c["name"]} ({c.get("category", "")})' for c in items[:5])
    return (
        rules
        + f'The member described their interests as: "{interest_text}"\n'
        + "Nothing matched closely enough - be honest about that without being "
          "discouraging, then gently mention a couple of these active groups as "
          "options worth exploring anyway:\n"
        + f"CAMPUS GROUPS:\n{listing}\n"
        + output_format
    )


def build_chat_available(groups: list[dict], events: list[dict]) -> str:
    lines = [
        f'[[group:{c["id"]}]] {c["name"]} ({c.get("category", "")}) - {c.get("description", "")[:120]}'
        for c in groups
    ]
    lines += [
        f'[[event:{e["id"]}]] {e["title"]} - event by {e.get("group_name", "")} '
        f'(organiser {e.get("leader_name", "")})'
        for e in events
    ]
    return "\n".join(lines) if lines else "(no groups or events available yet)"
