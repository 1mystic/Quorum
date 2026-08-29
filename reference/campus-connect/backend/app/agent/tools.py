"""
The read-only tool registry.

Seven tools, each a pure async function plus a JSON schema. Two properties
hold across the whole registry, and both are enforced structurally rather
than by review:

1. Nothing here mutates. Every tool calls a read method on ClubService,
   EventService or AnnouncementService - .list(), .get(), .my_clubs(),
   .feed(). There is no .create()/.update()/.approve()/.join() in reach, so a
   prompt injection hidden in a club description has no lever to pull. That
   is grounding gate 5.

2. No tool takes an identity parameter. There is no college_id or user_id in
   any input_schema, and additionalProperties is false everywhere, so the
   model cannot request another student's or another college's data. Scope
   comes from `payload` - the JWT claims FastAPI already verified via
   Security(get_user_info, ...) - which every service reads to resolve the
   caller's own college and student record. That is grounding gate 2.

This calls the same ClubService/EventService/AnnouncementService every other
router uses, via the same DI pattern (see app/core/di.py). There is no HTTP
hop, no separate auth surface, and no duplicate copy of the club/event data -
earlier drafts of this module called the deployed API over HTTP because the
AI service's own database had no club/event tables yet. It does now, so this
version calls straight into the same process.

The registry shape here - name, description, input_schema, read_only, fn - is
deliberately the same shape MCP's tools/list and tools/call expect. We are not
shipping an MCP server (decision 4.5 in the architecture report explains why),
but structuring it this way keeps that door a short wrapper away.

recommend_clubs is the notable entry: it wraps the v1 deterministic
recommender. The model does not take over ranking, it decides *when* ranking
should happen. The scoring itself stays pure Python with no network access.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from app.agent.grounding import AllowList, redact_for_model
from app.exceptions import AppException
from app.models import ClubType
from app.services import AnnouncementService, ClubService, EventService, StudentService
from app.agent import intent
from app.agent import recommender as R

# Fields the model is allowed to see. Anything a service adds to its response
# later is invisible until someone deliberately adds it here.
CLUB_FIELDS = [
    "id",
    "name",
    "category",
    "type",
    "description",
    "member_count",
    "head_name",
    "status",
]
CLUB_DETAIL_FIELDS = CLUB_FIELDS + ["links", "head"]
EVENT_FIELDS = [
    "id",
    "club_id",
    "club_name",
    "title",
    "description",
    "venue",
    "starts_at",
    "ends_at",
    "seats_left",
    "status",
]
EVENT_DETAIL_FIELDS = EVENT_FIELDS + [
    "capacity",
    "registration_count",
    "is_registered",
]
ANNOUNCEMENT_FIELDS = [
    "id",
    "club_id",
    "club_name",
    "title",
    "body",
    "category",
    "is_pinned",
    "created_at",
]
# Club heads carry contact fields (email, roll_no, branch, year) that are only
# ever populated for campus admins - see ClubHeadInfo. This student-facing
# tool set never receives that populated version, but we still whitelist
# defensively rather than trust "the field happens to be None right now".
CLUB_HEAD_FIELDS = ["student_id", "full_name"]


@dataclass
class Tool:
    """One callable capability offered to the model."""

    name: str
    description: str
    input_schema: dict
    fn: Callable
    read_only: bool = True

    def to_anthropic_schema(self) -> dict:
        """
        The tool definition sent to the Messages API.

        strict=True plus additionalProperties=false means the API guarantees
        the tool input validates against this schema, which is what let us
        stop hand-repairing malformed JSON (decision 4.12).
        """
        return {
            "name": self.name,
            "description": self.description,
            "strict": True,
            "input_schema": self.input_schema,
        }


@dataclass
class Services:
    """The read services every tool draws on, bundled for one turn."""

    club: ClubService
    event: EventService
    announcement: AnnouncementService
    # Read-only, like the rest: the student's own saved profile, used to seed
    # recommendations before they have typed anything this session.
    student: StudentService


def _dump(items) -> list:
    """Pydantic response models -> plain dicts, JSON-safe (datetimes, enums)."""
    return [item.model_dump(mode="json") for item in items]


# Shape returned when the profile cannot be read. Scoring treats every field
# as absent, which is exactly how the module behaved before profiles existed.
_EMPTY_PROFILE = {"interests": [], "branch": "", "year": 0}


async def _saved_profile(payload: dict, services: Services) -> dict:
    """
    The student's stored interests, branch and year.

    A missing or unreadable profile is not an error here - it just means the
    student has not onboarded yet, and ranking falls back to the text they
    typed. Recommendations must never fail because a profile lookup did.
    """
    try:
        profile = await services.student.my_profile(payload)
    except Exception:  # noqa: BLE001 - a profile read must never sink a recommendation
        return dict(_EMPTY_PROFILE)

    return {
        "interests": list(profile.interests or []),
        "branch": profile.branch or "",
        "year": profile.year or 0,
    }


def _dump_one(item) -> dict:
    return item.model_dump(mode="json") if item is not None else {}


# ---------------------------------------------------------------------------
# Tool implementations
#
# Every function takes (payload, services, allow_list, **model_supplied_args)
# and returns a JSON-serialisable dict. They never raise: a service error
# comes back as {"error": ...} so the loop can hand the model an is_error
# tool result and keep going with whatever else worked.
# ---------------------------------------------------------------------------


async def _search_clubs(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    club_type = kwargs.get("club_type")
    try:
        rows = await services.club.list(
            payload,
            search=kwargs.get("query"),
            category=kwargs.get("category"),
            type=ClubType(club_type) if club_type else None,
        )
    except AppException as exc:
        return {"error": exc.message}

    dumped = _dump(rows)
    allow_list.add_many("club", dumped, "id", "name")
    return {
        "count": len(dumped),
        "clubs": redact_for_model(dumped, CLUB_FIELDS),
    }


async def _get_club(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    try:
        club = await services.club.get(payload, kwargs["club_id"])
    except AppException as exc:
        return {"error": exc.message}

    row = _dump_one(club)
    allow_list.add("club", row.get("id"), row.get("name"))
    if row.get("head"):
        row["head"] = {k: v for k, v in row["head"].items() if k in CLUB_HEAD_FIELDS}
    projected = redact_for_model([row], CLUB_DETAIL_FIELDS)
    return {"club": projected[0] if projected else {}}


async def _get_my_clubs(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    try:
        rows = await services.club.my_clubs(payload)
    except AppException as exc:
        return {"error": exc.message}

    dumped = _dump(rows)
    allow_list.add_many("club", dumped, "id", "name")
    return {
        "count": len(dumped),
        "memberships": redact_for_model(
            dumped,
            ["id", "name", "category", "membership_role", "membership_status"],
        ),
    }


async def _search_events(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    try:
        rows = await services.event.list(
            payload,
            club_id=kwargs.get("club_id"),
            search=kwargs.get("query"),
            upcoming_only=kwargs.get("upcoming_only", True),
        )
    except AppException as exc:
        return {"error": exc.message}

    dumped = _dump(rows)
    allow_list.add_many("event", dumped, "id", "title")
    return {
        "count": len(dumped),
        "events": redact_for_model(dumped, EVENT_FIELDS),
    }


async def _get_event(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    try:
        event = await services.event.get(payload, kwargs["event_id"])
    except AppException as exc:
        return {"error": exc.message}

    row = _dump_one(event)
    allow_list.add("event", row.get("id"), row.get("title"))
    if row.get("club_id") and row.get("club_name"):
        allow_list.add("club", row["club_id"], row["club_name"])
    projected = redact_for_model([row], EVENT_DETAIL_FIELDS)
    return {"event": projected[0] if projected else {}}


async def _get_announcements(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    try:
        rows = await services.announcement.feed(
            payload,
            club_id=kwargs.get("club_id"),
            limit=min(int(kwargs.get("limit", 10)), 20),
        )
    except AppException as exc:
        return {"error": exc.message}

    dumped = _dump(rows)
    return {
        "count": len(dumped),
        "announcements": redact_for_model(dumped, ANNOUNCEMENT_FIELDS),
    }


def _in_date_range(starts_at, day_from, day_to) -> bool:
    """Does this event fall inside the campus-local window the student named?

    Compared in campus-local days, not UTC days - see intent.to_college_date
    for why those differ for evening events."""
    if not day_from and not day_to:
        return True
    day = intent.to_college_date(starts_at)
    if day is None:
        return False
    if day_from and day < day_from:
        return False
    if day_to and day > day_to:
        return False
    return True


async def _recommend_clubs(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    """
    The deterministic recommender, exposed as a tool.

    Ranking authority stays in select_recommendations(). intent.extract_interest_signal
    reads the student's sentence first and hands over clean keywords, a real
    category, and a date window, and also decides the turn's shape:
    off_topic (scope gate), events, or no_match.
    """
    interest_text = (kwargs.get("interest_text") or "").strip()
    if not interest_text:
        return {"error": "interest_text is required and must not be empty."}

    # Three independent reads (clubs, events, saved profile) used to run one
    # after another - each is a real network round trip to Neon, so that was
    # adding up before the model call had even started. None depends on the
    # others' result, so gather them instead.
    clubs_result, events_result, saved = await asyncio.gather(
        services.club.list(payload),
        services.event.list(payload, upcoming_only=True),
        _saved_profile(payload, services),
        return_exceptions=True,
    )

    if isinstance(clubs_result, AppException):
        return {"error": clubs_result.message}
    if isinstance(clubs_result, BaseException):
        raise clubs_result
    clubs = clubs_result

    events = [] if isinstance(events_result, BaseException) else events_result

    # Shape the service rows into what the v1 recommender expects. It scores
    # on name/category/description/tags and an activity_score popularity
    # prior; member_count is the same signal ClubListItem already carries.
    scored_clubs = [
        {
            "id": club.id,
            "name": club.name,
            "category": club.category,
            "description": club.description,
            # The schema has no tags column, so these are read back out of the
            # club's own name, category and description - see
            # recommender.derive_tags. Grounded by construction, and no
            # migration needed to ship the feature.
            "tags": R.derive_tags(
                {
                    "name": club.name,
                    "category": club.category,
                    "description": club.description,
                }
            ),
            "activity_score": club.member_count,
            "leader_name": club.head_name,
            # Passengers for ClubCard.vue - not read by score_club.
            "image_url": club.image_url,
            "member_count": club.member_count,
        }
        for club in clubs
    ]

    scored_events = [
        {
            "id": event.id,
            "club_id": event.club_id,
            "title": event.title,
            "description": event.description,
            "club_name": event.club_name,
            "leader_name": "",
            # Passengers for the UI card - not read by score_event.
            "venue": event.venue,
            "starts_at": event.starts_at,
            "ends_at": event.ends_at,
            "capacity": event.capacity,
            "registration_count": event.registration_count,
            "seats_left": event.seats_left,
            "status": event.status,
            "image_url": event.image_url,
        }
        for event in events
    ]

    categories = sorted({c.category for c in clubs if c.category})
    signal = await intent.extract_interest_signal(
        interest_text, categories, kwargs.get("previous_text") or ""
    )

    # The scope gate.
    if not signal["on_topic"]:
        return {"kind": "off_topic", "count": 0, "items": [], "note": "", "signal": signal}

    keywords = signal["keywords"]
    interest_parts = keywords or [interest_text]

    # A stated topic wins outright over the saved profile; the profile only
    # fills in when there is no topic to go on.
    stated_topic = bool(keywords)
    profile = {
        "interests": interest_parts if stated_topic else interest_parts + saved["interests"],
        "hobbies": [],
        "reason": " ".join(interest_parts),
        "branch": "" if stated_topic else saved["branch"],
        "year": saved["year"],
        "category_hint": signal["category"],
    }

    day_from = signal["date_range"]["from"]
    day_to = signal["date_range"]["to"]

    if signal["wants_events"]:
        in_window = [
            e for e in scored_events
            if _in_date_range(e.get("starts_at"), day_from, day_to)
        ]
        ranked = sorted(
            ({**e, "_score": R.score_event(profile, e)} for e in in_window),
            key=lambda e: e["_score"], reverse=True,
        )
        matched = [e for e in ranked if e["_score"] > 0] if keywords else ranked
        if matched:
            items, kind = matched[:3], "events"
            note = "" if keywords else (
                "No topic could be resolved from the message, so these are "
                "simply this college's upcoming events, not matches for any "
                "particular subject. If the student was asking about a specific "
                "club or topic and none of these belong to it, say so rather "
                "than presenting these as answers."
            )
        else:
            items, kind = [], "no_match"
            note = "No events matched what the student asked about."
    else:
        outcome = R.select_recommendations(profile, scored_clubs, scored_events)
        # More than the three shown, since the caller splits into new vs.
        # already-joined and caps after that split.
        items = outcome.get("items", [])[:8]
        kind = outcome.get("kind", "clubs")
        note = outcome.get("message", "")

        # Popularity fallback only stands when no topic was named at all.
        if kind == "popularity" and keywords:
            items, kind, note = [], "no_match", (
                "Nothing in this college's clubs matched what the student asked about."
            )

    # Register whatever the ranker chose, so the model may name it.
    if kind in ("event_fallback", "events"):
        allow_list.add_many("event", items, "id", "title")
    else:
        allow_list.add_many("club", items, "id", "name")

    # _score is internal ranking detail; strip it before the model sees it.
    cleaned = [{k: v for k, v in item.items() if k != "_score"} for item in items]

    return {
        "kind": kind,
        "count": len(cleaned),
        "items": cleaned,
        "note": note,
        "signal": signal,
    }


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

REGISTRY: dict = {}


def _register(tool: Tool) -> None:
    REGISTRY[tool.name] = tool


_register(
    Tool(
        name="recommend_clubs",
        description=(
            "Rank this college's clubs against a student's stated interests using the "
            "deterministic Campus Connect recommender. Use this whenever the student "
            "describes what they enjoy or asks what they should join, rather than "
            "picking clubs yourself. Falls back to relevant events, then to the most "
            "active clubs, when nothing matches well."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "interest_text": {
                    "type": "string",
                    "description": "The student's interests in their own words.",
                },
                "previous_text": {
                    "type": "string",
                    "description": (
                        "The student's previous message, used only to resolve a "
                        "follow-up that names no topic of its own."
                    ),
                },
            },
            "required": ["interest_text"],
            "additionalProperties": False,
        },
        fn=_recommend_clubs,
    )
)

_register(
    Tool(
        name="search_clubs",
        description=(
            "Search active clubs in this student's college by keyword, category or "
            "type. Use this to look up a club the student named, or to browse a "
            "category. For open-ended 'what should I join' questions prefer "
            "recommend_clubs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text search over club name and description.",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter, e.g. technology, arts, sports.",
                },
                "club_type": {
                    "type": "string",
                    "enum": ["OFFICIAL", "UNOFFICIAL"],
                    "description": "Optional club type filter.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        fn=_search_clubs,
    )
)

_register(
    Tool(
        name="get_club",
        description=(
            "Fetch full detail for one club by id: description, member count, "
            "category, and who heads it. Call this after search_clubs or "
            "recommend_clubs when the student wants to know more about a specific club."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "club_id": {
                    "type": "integer",
                    "description": "The club's id, taken from an earlier tool result.",
                },
            },
            "required": ["club_id"],
            "additionalProperties": False,
        },
        fn=_get_club,
    )
)

_register(
    Tool(
        name="get_my_clubs",
        description=(
            "List the clubs this student has already joined, with their role and "
            "membership status. Call this before recommending, so you never suggest "
            "something they are already in, and to answer 'am I in X?' questions. "
            "Also the way to get club ids for the student's own clubs."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        fn=_get_my_clubs,
    )
)

_register(
    Tool(
        name="search_events",
        description=(
            "Search published events in this student's college. Use upcoming_only to "
            "restrict to events that have not happened yet, and club_id to list one "
            "club's events. Call this for any question about what is happening, when, "
            "or where."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text search over event title.",
                },
                "club_id": {
                    "type": "integer",
                    "description": "Optional: only events hosted by this club.",
                },
                "upcoming_only": {
                    "type": "boolean",
                    "description": "Default true. Set false to include past events.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        fn=_search_events,
    )
)

_register(
    Tool(
        name="get_event",
        description=(
            "Fetch full detail for one event by id: description, venue, start and end "
            "time, capacity, seats left, and whether this student is already "
            "registered. Call this when the student asks about a specific event."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "The event's id, taken from an earlier tool result.",
                },
            },
            "required": ["event_id"],
            "additionalProperties": False,
        },
        fn=_get_event,
    )
)

_register(
    Tool(
        name="get_announcements",
        description=(
            "Read recent club announcements. Pass club_id to scope to one club - "
            "usually an id you got from get_my_clubs. Call this for 'what's new' or "
            "'any updates from my clubs' questions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "club_id": {
                    "type": "integer",
                    "description": "Optional: only announcements from this club.",
                },
                "limit": {
                    "type": "integer",
                    "description": "How many to return, maximum 20. Default 10.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        fn=_get_announcements,
    )
)


def anthropic_tool_schemas() -> list:
    """Every tool definition, in the shape the Messages API expects."""
    return [tool.to_anthropic_schema() for tool in REGISTRY.values()]


async def execute(
    name: str,
    arguments: dict,
    payload: dict,
    services: Services,
    allow_list: AllowList,
) -> Any:
    """
    Run one tool by name.

    Unknown names and unexpected exceptions both come back as an error dict
    rather than propagating, because the loop must always be able to answer a
    tool_use block with a matching tool_result - the API rejects the follow-up
    request otherwise.
    """
    tool = REGISTRY.get(name)
    if tool is None:
        return {"error": "No tool named " + str(name) + "."}

    try:
        return await tool.fn(payload, services, allow_list, **(arguments or {}))
    except TypeError as exc:
        return {"error": "Bad arguments for " + name + ": " + str(exc)}
    except Exception as exc:  # noqa: BLE001 - a tool must never kill the turn
        return {"error": "Tool " + name + " failed: " + str(exc)}
