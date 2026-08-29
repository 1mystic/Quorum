"""Turns a member's raw sentence into clean signal for the deterministic
recommender, via the LLM instead of a hand-maintained stopword list and a
fixed interest-to-category map.

on_topic is the scope gate - the stage that lets the turn stop before
answering something that was never a group or event question.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.agent import providers

logger = logging.getLogger("quorum.agent")

# Was a global COLLEGE_TIMEZONE setting in Campus Connect. Per docs/GLOSSARY.md
# this is now a per-tenant value (Tenant.timezone), not a deployment-wide env
# var - a platform with tenants in different timezones cannot have one. Wiring
# the tenant's actual timezone through the agent's tool-calling loop is agent
# integration work (see docs/WORKPLAN.md card C.18), so this module falls
# back to UTC until that lands.
DEFAULT_TENANT_TIMEZONE = "UTC"

_INTENT_TIMEOUT = 10.0

EMPTY_SIGNAL = {
    "keywords": [],
    "category": None,
    "time_scope": "any",
    "wants_events": False,
    "date_range": {"from": None, "to": None},
    "on_topic": True,
    "clean_query": "",
}


def _tenant_tz(tz_name: str = DEFAULT_TENANT_TIMEZONE):
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("bad tenant timezone %r, using UTC", tz_name)
        return timezone.utc


def tenant_today(tz_name: str = DEFAULT_TENANT_TIMEZONE) -> date:
    """Today's date in the tenant's local timezone - what "tomorrow" is counted from."""
    return datetime.now(_tenant_tz(tz_name)).date()


def to_tenant_date(value, tz_name: str = DEFAULT_TENANT_TIMEZONE) -> date | None:
    """The tenant-local calendar day an event falls on."""
    if value is None:
        return None
    if not hasattr(value, "astimezone"):
        return value if isinstance(value, date) else None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_tenant_tz(tz_name)).date()


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


_SYSTEM_PROMPT = """Extract search signal from a member's message to a campus group/event assistant.
Return STRICT JSON only, matching this shape:
{"keywords": [<1-5 short interest words/phrases, the member's own words or close synonyms>],
 "category": <one value from CATEGORIES that best fits the keywords, or null if none fit>,
 "time_scope": "past" | "upcoming" | "any",
 "wants_events": <true if the member is asking about events, happenings, schedules, tournaments,
   workshops etc - as opposed to just asking about a group itself - else false>,
 "date_range": {"from": "YYYY-MM-DD" or null, "to": "YYYY-MM-DD" or null},
 "on_topic": <true if this message is about campus groups, events or member activities in any
   way - including vague asks like "suggest me something" - false if it is about anything else>,
 "clean_query": <the member's message, rewritten to remove any part that asks for something
   this assistant does not do - general knowledge, maths, code, translation, writing, or
   anything else that is not about this tenant's groups or events. Keep the group/event part in
   the member's own words, changed as little as possible. If the WHOLE message is off-topic,
   return an empty string. If NONE of it is off-topic, return the message essentially unchanged.>}

Rules:
- keywords: the actual topics/interests the member named, stripped of filler like "show me", "can you", "I have an interest in". These are matched literally against the words a group uses to describe ITSELF, so include the member's own word AND the vocabulary a group on that topic would actually use - a member saying "climate" will never literally match a group that calls itself "Environmental and Sustainability... greener campus, tree plantation", so return both. Stay on-topic: only words that genuinely name the same subject, never a broader category word just to widen the net. Never include a word whose only job in the sentence is describing what KIND of thing is being asked for rather than what it's about - words like "event", "events", "activity", "activities", "session", "workshop", "programme", "happening", "planned", "group", "upcoming", "any", "schedule" describe the shape of the request, not a topic, and would wrongly match any group whose own description happens to mention hosting events at all. "Activity" in particular is just another word for "event" here - a member asking "any planned activity" is asking about events, not about a group that has the word "activity" in its description. If you strip those out and nothing topical is left (e.g. "any upcoming events?" or "is there any activity planned?" with no subject), return an empty keywords list rather than keeping the request-shape words as if they were topics.
- keywords must also carry no polarity or preference words. "less competitive", "beginner friendly", "not too serious" describe what the member wants the group to BE LIKE, not what it is about - and matched literally they do the opposite of what was asked ("less competitive" matches a group describing itself as "competitive programming"). Drop them entirely; keep only the subject.
- category: only ever a value copied verbatim from the CATEGORIES list given, or null. Never invent one.
- time_scope: "past" if they ask about something that already happened (last week, previous, before), "upcoming" if they ask about what's coming/next/soon, "any" if unclear or not about events at all.
- wants_events: default to false. Only true when the message itself uses event-ish language (event, events, activity, activities, anything planned, anything on, happening, schedule, tournament, workshop, session, when is/does). Treat "activity" and "event" as the same thing - "is there any activity planned" is an events question - true even if a group/topic is also named in the same message (e.g. "does the gaming group have any events" is both a group topic AND wants_events=true). A message that ONLY asks about a group/topic in general - "do you have something for X", "tell me about X", "any X group" - is wants_events=false, even if that group happens to run events; the member didn't ask about them.
- on_topic: default to true - err on the side of true whenever the message could plausibly be about finding a group, an event or something to do on campus, even with no topic named ("suggest me something", "what should I join", "anything fun?") and even when it is phrased as wanting to DO something rather than asking to FIND a group for it ("I have a cool startup idea, where do I find like-minded people" is on_topic - it is a group search phrased as a goal, keywords ["startup", "entrepreneurship"]). This bias toward true is not weakened by the clean_query rule above - clean_query only removes a part that is a clearly different, unrelated request; it never makes an otherwise on-topic message become off-topic. Only false when it is clearly about something else entirely: general knowledge or maths ("what is 2 plus 2"), coding help, the weather, or a question about the conversation itself. A false here suppresses group/event suggestions for the turn, so a wrong false is worse than a wrong true.
- date_range: only when the message names a specific day or window - "tomorrow", "tonight", "this weekend", "next week", "on the 24th", "last month". Compute it against TODAY given below, and make it inclusive of both ends (a single day has from == to). Leave BOTH null when no specific window is named: "upcoming", "any events", "what's next" are NOT date ranges - time_scope already covers those.
- clean_query exists because a message can ask for two different things at once - a real group question, plus something unrelated riding along with it ("suggest me a coding group, also what is 17*23"). The reply is written by a SEPARATE step that only ever sees clean_query, never your original input - so this is not a hint or a suggestion, it is the only thing standing between the unrelated part and getting answered. Cut it out completely rather than flagging it. Do not just trim polite filler here (that is what keywords already handles) - only remove a part that is a genuinely different request: a question this assistant should never answer regardless of how the rest of the message reads. A message that is entirely a group/event question, however it's phrased, keeps clean_query equal to itself.

EXAMPLES (follow this pattern exactly - request-shape words never survive into keywords, even when a real topic sits right next to them; assume TODAY is 2026-08-22 for these):
"any upcoming event ?" -> {"keywords": [], "category": null, "time_scope": "upcoming", "wants_events": true, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "any upcoming event ?"}
"any event in robotics" -> {"keywords": ["robotics"], "category": null, "time_scope": "any", "wants_events": true, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "any event in robotics"}
"is there any acitivty planned" -> {"keywords": [], "category": null, "time_scope": "any", "wants_events": true, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "is there any acitivty planned"}
"does the gaming group have any events" -> {"keywords": ["gaming"], "category": null, "time_scope": "any", "wants_events": true, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "does the gaming group have any events"}
"I like painting and photography" -> {"keywords": ["painting", "photography"], "category": null, "time_scope": "any", "wants_events": false, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "I like painting and photography"}
"Find AI groups" -> {"keywords": ["artificial intelligence", "machine learning", "AI"], "category": null, "time_scope": "any", "wants_events": false, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "Find AI groups"}
"what is 2 plus 2" -> {"keywords": [], "category": null, "time_scope": "any", "wants_events": false, "date_range": {"from": null, "to": null}, "on_topic": false, "clean_query": ""}
"suggest me something to join" -> {"keywords": [], "category": null, "time_scope": "any", "wants_events": false, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "suggest me something to join"}
"I want to fight climate problems" -> {"keywords": ["climate", "environment", "sustainability", "green"], "category": null, "time_scope": "any", "wants_events": false, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "I want to fight climate problems"}
"what's happening tomorrow" -> {"keywords": [], "category": null, "time_scope": "upcoming", "wants_events": true, "date_range": {"from": "2026-08-23", "to": "2026-08-23"}, "on_topic": true, "clean_query": "what's happening tomorrow"}
"any coding events this week" -> {"keywords": ["coding"], "category": null, "time_scope": "upcoming", "wants_events": true, "date_range": {"from": "2026-08-22", "to": "2026-08-28"}, "on_topic": true, "clean_query": "any coding events this week"}
"suggest me a coding group, also what is 17*23" -> {"keywords": ["coding"], "category": null, "time_scope": "any", "wants_events": false, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "suggest me a coding group"}
"which dance group should I join and translate hello to French" -> {"keywords": ["dance"], "category": null, "time_scope": "any", "wants_events": false, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "which dance group should I join"}
"Find AI groups and write Python code for sorting" -> {"keywords": ["artificial intelligence", "machine learning", "AI"], "category": null, "time_scope": "any", "wants_events": false, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "Find AI groups"}
"I have a cool startup idea, where do I find like-minded people" -> {"keywords": ["startup", "entrepreneurship"], "category": null, "time_scope": "any", "wants_events": false, "date_range": {"from": null, "to": null}, "on_topic": true, "clean_query": "I have a cool startup idea, where do I find like-minded people"}
"""

_PRONOUN_RULE = """
PREVIOUS MESSAGE (the member's last message before this one, for context only):
{previous}

Use it for TWO purposes, and nothing else:
1. If the current message is a follow-up that names no topic of its own -
   "any upcoming events for this", "what about them", "tell me more" - resolve
   what it refers to and put THAT topic in keywords.
2. If the current message is a refinement that only states a preference -
   "I'm a beginner", "something less competitive" - carry the PREVIOUS topic
   into keywords, since the refinement itself contributes no subject. The
   preference words themselves still never become keywords.

Otherwise ignore it completely. If the current message names its own topic, the
previous message must not contribute a single keyword: a member who asked
about dance and then asks "any coding groups?" wants coding only, and leaking
"dance" into that turn is worse than the unresolved pronoun this rule fixes.

The keyword rules above apply to anything taken from the previous message just
as they do to the current one. If the previous message was ITSELF a topicless
follow-up ("is there any activity planned"), it contains no subject to carry -
return an empty keywords list. Never fall back to lifting a request-shape word
like "activity", "event" or "planned" out of it just to have something to
return; that word matches no group's own description and turns the turn into a
false "nothing found".
"""

_DATE_CUE_RE = re.compile(
    r"\b(today|tonight|tomorrow|yesterday|weekend|week|weeks|month|months|"
    r"morning|afternoon|evening|night|"
    r"mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"\d{1,2}(st|nd|rd|th)?|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)


_EVENT_WORDS = (
    "event", "events", "happening", "schedule", "tournament", "workshop",
    "workshops", "session", "sessions", "meet", "meetup", "activities",
    "activity"
)


def _mock_extract(text: str, categories: list[str]) -> dict:
    """Deterministic fallback with no provider configured. This is the old
    keyword behaviour - callers should treat a turn served by this path as
    degraded."""
    from app.agent import recommender as R

    lowered = (text or "").lower()
    words = [w for w in R.normalize_tokens(text)]

    time_scope = "any"
    if any(w in lowered for w in ("last", "past", "previous", "happened", "ago")):
        time_scope = "past"
    elif any(w in lowered for w in ("upcoming", "next", "soon")):
        time_scope = "upcoming"

    today = tenant_today()
    if "tomorrow" in lowered:
        day_from = day_to = today + timedelta(days=1)
    elif "today" in lowered or "tonight" in lowered:
        day_from = day_to = today
    else:
        day_from = day_to = None

    return {
        "keywords": words,
        "category": next((c for c in categories if c.lower() in lowered), None),
        "time_scope": time_scope,
        "wants_events": any(w in lowered for w in _EVENT_WORDS),
        "date_range": {"from": day_from, "to": day_to},
        "on_topic": True,
        "clean_query": text,
    }


async def extract_interest_signal(
    text: str, categories: list[str], previous_text: str = ""
) -> dict:
    """Pull clean keywords / category / time-scope / scope-decision out of one
    message. Falls back to the plain tokenizer when no provider is configured
    or the call fails."""
    text = (text or "").strip()
    if not text:
        return dict(EMPTY_SIGNAL)

    if providers.resolve() is None:
        return _mock_extract(text, categories)

    system = (
        _SYSTEM_PROMPT
        + f"\nTODAY: {tenant_today().isoformat()}"
        + "\nCATEGORIES: " + json.dumps(categories)
        + (_PRONOUN_RULE.format(previous=previous_text.strip())
           if previous_text.strip() else "")
    )

    try:
        reply = await providers.complete(
            system=system,
            messages=[{"role": "user", "content": text}],
            max_tokens=150,
            timeout_seconds=_INTENT_TIMEOUT,
            temperature=0.0,
            json_mode=True,
        )
        data = providers.extract_json(reply.text)
    except Exception as exc:  # noqa: BLE001 - enrichment must never sink the turn
        logger.warning("intent extraction failed, falling back to tokenizer: %s", exc)
        return _mock_extract(text, categories)

    keywords = [str(k).strip() for k in (data.get("keywords") or []) if str(k).strip()][:5]

    category = data.get("category")
    category = str(category).strip() if category and str(category).strip() in categories else None

    time_scope = data.get("time_scope")
    time_scope = time_scope if time_scope in ("past", "upcoming", "any") else "any"

    raw_range = data.get("date_range") or {}
    day_from = _parse_date(raw_range.get("from")) if isinstance(raw_range, dict) else None
    day_to = _parse_date(raw_range.get("to")) if isinstance(raw_range, dict) else None
    if (day_from or day_to) and not _DATE_CUE_RE.search(text):
        logger.info("dropping invented date_range for %r", text)
        day_from = day_to = None
    if day_from and day_to and day_to < day_from:
        day_from, day_to = day_to, day_from

    clean_query = data.get("clean_query")
    clean_query = clean_query.strip() if isinstance(clean_query, str) else text

    return {
        "keywords": keywords,
        "category": category,
        "time_scope": time_scope,
        "wants_events": bool(data.get("wants_events")),
        "date_range": {"from": day_from, "to": day_to},
        "on_topic": data.get("on_topic") is not False,
        "clean_query": clean_query,
    }
