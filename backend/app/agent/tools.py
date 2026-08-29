"""
The read-only tool registry.

Seven tools, each a pure async function plus a JSON schema. Two properties
hold across the whole registry, and both are enforced structurally rather
than by review:

1. Nothing here mutates. Every tool calls a read method on GroupService,
   EventService or AnnouncementService - .list(), .get(), .my_groups(),
   .feed(). There is no .create()/.update()/.approve()/.join() in reach, so a
   prompt injection hidden in a group description has no lever to pull. That
   is grounding gate 5.

2. No tool takes an identity parameter. There is no tenant_id or user_id in
   any input_schema, and additionalProperties is false everywhere, so the
   model cannot request another member's or another tenant's data. Scope
   comes from `payload` - the JWT claims FastAPI already verified via
   Security(get_user_info, ...) - which every service reads to resolve the
   caller's own tenant and member record. That is grounding gate 2.

This calls the same GroupService/EventService/AnnouncementService every other
router uses, via the same DI pattern (see app/core/di.py). There is no HTTP
hop, no separate auth surface, and no duplicate copy of the group/event data -
earlier drafts of this module called the deployed API over HTTP because the
AI service's own database had no group/event tables yet. It does now, so this
version calls straight into the same process.

The registry shape here - name, description, input_schema, read_only, fn - is
deliberately the same shape MCP's tools/list and tools/call expect. We are not
shipping an MCP server (decision 4.5 in the architecture report explains why),
but structuring it this way keeps that door a short wrapper away.

recommend_groups is the notable entry: it wraps the v1 deterministic
recommender. The model does not take over ranking, it decides *when* ranking
should happen. The scoring itself stays pure Python with no network access.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from app.agent.grounding import AllowList, redact_for_model
from app.exceptions import AppException
from app.models import GroupType
from app.services import AnnouncementService, GroupService, EventService, MemberService
from app.agent import intent
from app.agent import recommender as R

# Fields the model is allowed to see. Anything a service adds to its response
# later is invisible until someone deliberately adds it here.
GROUP_FIELDS = [
    "id",
    "name",
    "category",
    "type",
    "description",
    "member_count",
    "head_name",
    "status",
]
GROUP_DETAIL_FIELDS = GROUP_FIELDS + ["links", "head"]
EVENT_FIELDS = [
    "id",
    "group_id",
    "group_name",
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
    "group_id",
    "group_name",
    "title",
    "body",
    "category",
    "is_pinned",
    "created_at",
]
# Group heads carry contact fields (email, roll_no, branch, year) that are only
# ever populated for campus admins - see GroupHeadInfo. This member-facing
# tool set never receives that populated version, but we still whitelist
# defensively rather than trust "the field happens to be None right now".
GROUP_HEAD_FIELDS = ["member_id", "full_name"]


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

    group: GroupService
    event: EventService
    announcement: AnnouncementService
    # Read-only, like the rest: the member's own saved profile, used to seed
    # recommendations before they have typed anything this session.
    member: MemberService


def _dump(items) -> list:
    """Pydantic response models -> plain dicts, JSON-safe (datetimes, enums)."""
    return [item.model_dump(mode="json") for item in items]


# Shape returned when the profile cannot be read. Scoring treats every field
# as absent, which is exactly how the module behaved before profiles existed.
_EMPTY_PROFILE = {"interests": [], "branch": "", "year": 0}


async def _saved_profile(payload: dict, services: Services) -> dict:
    """
    The member's stored interests, branch and year.

    A missing or unreadable profile is not an error here - it just means the
    member has not onboarded yet, and ranking falls back to the text they
    typed. Recommendations must never fail because a profile lookup did.
    """
    try:
        profile = await services.member.my_profile(payload)
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


async def _search_groups(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    group_type = kwargs.get("group_type")
    try:
        rows = await services.group.list(
            payload,
            search=kwargs.get("query"),
            category=kwargs.get("category"),
            type=GroupType(group_type) if group_type else None,
        )
    except AppException as exc:
        return {"error": exc.message}

    dumped = _dump(rows)
    allow_list.add_many("group", dumped, "id", "name")
    return {
        "count": len(dumped),
        "groups": redact_for_model(dumped, GROUP_FIELDS),
    }


async def _get_group(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    try:
        group = await services.group.get(payload, kwargs["group_id"])
    except AppException as exc:
        return {"error": exc.message}

    row = _dump_one(group)
    allow_list.add("group", row.get("id"), row.get("name"))
    if row.get("head"):
        row["head"] = {k: v for k, v in row["head"].items() if k in GROUP_HEAD_FIELDS}
    projected = redact_for_model([row], GROUP_DETAIL_FIELDS)
    return {"group": projected[0] if projected else {}}


async def _get_my_groups(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    try:
        rows = await services.group.my_groups(payload)
    except AppException as exc:
        return {"error": exc.message}

    dumped = _dump(rows)
    allow_list.add_many("group", dumped, "id", "name")
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
            group_id=kwargs.get("group_id"),
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
    if row.get("group_id") and row.get("group_name"):
        allow_list.add("group", row["group_id"], row["group_name"])
    projected = redact_for_model([row], EVENT_DETAIL_FIELDS)
    return {"event": projected[0] if projected else {}}


async def _get_announcements(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    try:
        rows = await services.announcement.feed(
            payload,
            group_id=kwargs.get("group_id"),
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
    """Does this event fall inside the campus-local window the member named?

    Compared in campus-local days, not UTC days - see intent.to_tenant_date
    for why those differ for evening events."""
    if not day_from and not day_to:
        return True
    day = intent.to_tenant_date(starts_at)
    if day is None:
        return False
    if day_from and day < day_from:
        return False
    if day_to and day > day_to:
        return False
    return True


async def _recommend_groups(payload: dict, services: Services, allow_list: AllowList, **kwargs) -> dict:
    """
    The deterministic recommender, exposed as a tool.

    Ranking authority stays in select_recommendations(). intent.extract_interest_signal
    reads the member's sentence first and hands over clean keywords, a real
    category, and a date window, and also decides the turn's shape:
    off_topic (scope gate), events, or no_match.
    """
    interest_text = (kwargs.get("interest_text") or "").strip()
    if not interest_text:
        return {"error": "interest_text is required and must not be empty."}

    # Three independent reads (groups, events, saved profile) used to run one
    # after another - each is a real network round trip to Neon, so that was
    # adding up before the model call had even started. None depends on the
    # others' result, so gather them instead.
    groups_result, events_result, saved = await asyncio.gather(
        services.group.list(payload),
        services.event.list(payload, upcoming_only=True),
        _saved_profile(payload, services),
        return_exceptions=True,
    )

    if isinstance(groups_result, AppException):
        return {"error": groups_result.message}
    if isinstance(groups_result, BaseException):
        raise groups_result
    groups = groups_result

    events = [] if isinstance(events_result, BaseException) else events_result

    # Shape the service rows into what the v1 recommender expects. It scores
    # on name/category/description/tags and an activity_score popularity
    # prior; member_count is the same signal GroupListItem already carries.
    scored_groups = [
        {
            "id": group.id,
            "name": group.name,
            "category": group.category,
            "description": group.description,
            # The schema has no tags column, so these are read back out of the
            # group's own name, category and description - see
            # recommender.derive_tags. Grounded by construction, and no
            # migration needed to ship the feature.
            "tags": R.derive_tags(
                {
                    "name": group.name,
                    "category": group.category,
                    "description": group.description,
                }
            ),
            "activity_score": group.member_count,
            "leader_name": group.head_name,
            # Passengers for GroupCard.vue - not read by score_group.
            "image_url": group.image_url,
            "member_count": group.member_count,
        }
        for group in groups
    ]

    scored_events = [
        {
            "id": event.id,
            "group_id": event.group_id,
            "title": event.title,
            "description": event.description,
            "group_name": event.group_name,
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

    categories = sorted({c.category for c in groups if c.category})
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
                "simply this tenant's upcoming events, not matches for any "
                "particular subject. If the member was asking about a specific "
                "group or topic and none of these belong to it, say so rather "
                "than presenting these as answers."
            )
        else:
            items, kind = [], "no_match"
            note = "No events matched what the member asked about."
    else:
        outcome = R.select_recommendations(profile, scored_groups, scored_events)
        # More than the three shown, since the caller splits into new vs.
        # already-joined and caps after that split.
        items = outcome.get("items", [])[:8]
        kind = outcome.get("kind", "groups")
        note = outcome.get("message", "")

        # Popularity fallback only stands when no topic was named at all.
        if kind == "popularity" and keywords:
            items, kind, note = [], "no_match", (
                "Nothing in this tenant's groups matched what the member asked about."
            )

    # Register whatever the ranker chose, so the model may name it.
    if kind in ("event_fallback", "events"):
        allow_list.add_many("event", items, "id", "title")
    else:
        allow_list.add_many("group", items, "id", "name")

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
        name="recommend_groups",
        description=(
            "Rank this tenant's groups against a member's stated interests using the "
            "deterministic Quorum recommender. Use this whenever the member "
            "describes what they enjoy or asks what they should join, rather than "
            "picking groups yourself. Falls back to relevant events, then to the most "
            "active groups, when nothing matches well."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "interest_text": {
                    "type": "string",
                    "description": "The member's interests in their own words.",
                },
                "previous_text": {
                    "type": "string",
                    "description": (
                        "The member's previous message, used only to resolve a "
                        "follow-up that names no topic of its own."
                    ),
                },
            },
            "required": ["interest_text"],
            "additionalProperties": False,
        },
        fn=_recommend_groups,
    )
)

_register(
    Tool(
        name="search_groups",
        description=(
            "Search active groups in this member's tenant by keyword, category or "
            "type. Use this to look up a group the member named, or to browse a "
            "category. For open-ended 'what should I join' questions prefer "
            "recommend_groups."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text search over group name and description.",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter, e.g. technology, arts, sports.",
                },
                "group_type": {
                    "type": "string",
                    "enum": ["OFFICIAL", "UNOFFICIAL"],
                    "description": "Optional group type filter.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        fn=_search_groups,
    )
)

_register(
    Tool(
        name="get_group",
        description=(
            "Fetch full detail for one group by id: description, member count, "
            "category, and who heads it. Call this after search_groups or "
            "recommend_groups when the member wants to know more about a specific group."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "integer",
                    "description": "The group's id, taken from an earlier tool result.",
                },
            },
            "required": ["group_id"],
            "additionalProperties": False,
        },
        fn=_get_group,
    )
)

_register(
    Tool(
        name="get_my_groups",
        description=(
            "List the groups this member has already joined, with their role and "
            "membership status. Call this before recommending, so you never suggest "
            "something they are already in, and to answer 'am I in X?' questions. "
            "Also the way to get group ids for the member's own groups."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        fn=_get_my_groups,
    )
)

_register(
    Tool(
        name="search_events",
        description=(
            "Search published events in this member's tenant. Use upcoming_only to "
            "restrict to events that have not happened yet, and group_id to list one "
            "group's events. Call this for any question about what is happening, when, "
            "or where."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text search over event title.",
                },
                "group_id": {
                    "type": "integer",
                    "description": "Optional: only events hosted by this group.",
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
            "time, capacity, seats left, and whether this member is already "
            "registered. Call this when the member asks about a specific event."
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
            "Read recent group announcements. Pass group_id to scope to one group - "
            "usually an id you got from get_my_groups. Call this for 'what's new' or "
            "'any updates from my groups' questions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "integer",
                    "description": "Optional: only announcements from this group.",
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
