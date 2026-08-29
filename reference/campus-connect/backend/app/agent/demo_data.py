"""
The offline demo tier: a seeded campus the AI can talk about when the real one
is out of reach.

Why this exists. Every tool in tools.py reads through ClubService/EventService/
AnnouncementService, which read through Postgres. When the database is
unreachable - no network at a demo, Neon's free tier asleep, a laptop with no
DATABASE_URL - the agent has nothing to ground on, and an assistant that cannot
name a single real club is worse than no assistant. So instead of failing the
turn, we swap the three services for the stand-ins below, which answer the same
read methods with the same pydantic response models over an in-memory campus.

The stand-ins are deliberately *not* a mock in the testing sense. They apply the
same filtering, searching and scoping the real services apply, so the agent's
behaviour - which tool it picks, how it chains calls, what the grounding gates
let through - is identical on both tiers. Only the data underneath changes.

Two rules keep this honest:

1. Every response built here is a real schema object (ClubListItem,
   EventDetailResponse, ...), so if a schema changes, this file fails loudly
   rather than drifting into a shape the frontend no longer understands.
2. The API response carries degraded=true whenever this tier served the turn,
   and the reply text says so. Demo data is never presented as live data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.agent.tools import Services
from app.exceptions import ClubNotFoundError, EventNotFoundError
from app.models import (
    AnnouncementCategory,
    ClubStatus,
    ClubType,
    EventStatus,
    MembershipRole,
    MembershipStatus,
)
from app.schemas import (
    AnnouncementItem,
    ClubDetailResponse,
    ClubHeadInfo,
    ClubLinkSchema,
    ClubListItem,
    EventDetailResponse,
    EventListItem,
    MyClubItem,
)

_NOW = datetime.now(timezone.utc)


def _days(offset: int) -> datetime:
    return _NOW + timedelta(days=offset)


# ---------------------------------------------------------------------------
# The seed campus
#
# Eight clubs across the categories a real college actually has, with member
# counts spread widely enough that the recommender's popularity prior visibly
# does something, and descriptions rich enough that keyword scoring has real
# text to work against. Two of them are joined by the demo student, so
# get_my_clubs returns something and "don't recommend what I'm already in"
# is demonstrable.
# ---------------------------------------------------------------------------

_CLUBS = [
    {
        "id": 1,
        "name": "Robotics & Automation Society",
        "category": "Technology",
        "type": ClubType.OFFICIAL,
        "member_count": 84,
        "head_name": "Ananya Rao",
        "description": (
            "Build autonomous robots, line followers and drones. We run a hardware lab "
            "with 3D printers and microcontrollers, compete in national robotics "
            "championships, and teach embedded C and ROS to first-years."
        ),
        "links": [("Website", "https://example.edu/robotics")],
    },
    {
        "id": 2,
        "name": "Coding Club",
        "category": "Technology",
        "type": ClubType.OFFICIAL,
        "member_count": 156,
        "head_name": "Rahul Menon",
        "description": (
            "Competitive programming, weekly algorithm contests and open-source sprints. "
            "Beginner tracks in Python and C++, plus interview preparation circles for "
            "data structures, system design and machine learning."
        ),
        "links": [("GitHub", "https://example.edu/coding")],
    },
    {
        "id": 3,
        "name": "Fine Arts Collective",
        "category": "Arts",
        "type": ClubType.OFFICIAL,
        "member_count": 62,
        "head_name": "Ishita Sharma",
        "description": (
            "Painting, sketching, digital illustration and campus murals. Open studio "
            "every weekend, annual exhibition, and workshops on watercolour and "
            "character design for complete beginners."
        ),
        "links": [],
    },
    {
        "id": 4,
        "name": "Music Society",
        "category": "Arts",
        "type": ClubType.OFFICIAL,
        "member_count": 98,
        "head_name": "Kabir Nair",
        "description": (
            "Western and Indian classical ensembles, an a cappella group and a rock band. "
            "Jam rooms with drums, keyboard and guitars, plus vocal training and "
            "performances at every campus festival."
        ),
        "links": [],
    },
    {
        "id": 5,
        "name": "Football Club",
        "category": "Sports",
        "type": ClubType.OFFICIAL,
        "member_count": 71,
        "head_name": "Arjun Pillai",
        "description": (
            "Men's and women's teams with structured training four evenings a week, "
            "inter-college league fixtures, and a casual weekend side for anyone who "
            "just wants to play without trials."
        ),
        "links": [],
    },
    {
        "id": 6,
        "name": "Entrepreneurship Cell",
        "category": "Business",
        "type": ClubType.OFFICIAL,
        "member_count": 110,
        "head_name": "Sneha Iyer",
        "description": (
            "Startup incubation, pitch practice and founder office hours. We run an "
            "annual business plan competition, connect students to angel investors, and "
            "hold sessions on product, growth marketing and fundraising."
        ),
        "links": [("Site", "https://example.edu/ecell")],
    },
    {
        "id": 7,
        "name": "Photography Circle",
        "category": "Arts",
        "type": ClubType.UNOFFICIAL,
        "member_count": 45,
        "head_name": "Meera Krishnan",
        "description": (
            "Street, portrait and astrophotography walks around the city. Camera and "
            "lens library for members, monthly photo critiques, and hands-on Lightroom "
            "and colour grading workshops."
        ),
        "links": [],
    },
    {
        "id": 8,
        "name": "Debate & Literary Society",
        "category": "Literature",
        "type": ClubType.OFFICIAL,
        "member_count": 53,
        "head_name": "Vikram Desai",
        "description": (
            "Parliamentary debate, MUN delegations, creative writing circles and the "
            "campus literary magazine. Weekly practice rounds and public speaking "
            "coaching for anyone nervous about a stage."
        ),
        "links": [],
    },
]

# The demo student's own memberships, keyed by club id.
_MY_MEMBERSHIPS = {
    2: (MembershipRole.MEMBER, MembershipStatus.APPROVED, _days(-120)),
    7: (MembershipRole.LEADER, MembershipStatus.APPROVED, _days(-300)),
}

_EVENTS = [
    {
        "id": 101,
        "club_id": 1,
        "title": "RoboWars Intra-College Championship",
        "venue": "Central Workshop, Block C",
        "starts_at": _days(6),
        "ends_at": _days(6) + timedelta(hours=6),
        "capacity": 120,
        "registration_count": 87,
        "description": (
            "Teams of three build a combat robot within a 15 kg limit and fight in a "
            "knockout bracket. Components provided; soldering and basic wiring "
            "experience recommended but not required."
        ),
    },
    {
        "id": 102,
        "club_id": 2,
        "title": "48-Hour Hackathon: Build for Campus",
        "venue": "Innovation Lab, Library Annexe",
        "starts_at": _days(13),
        "ends_at": _days(15),
        "capacity": 200,
        "registration_count": 164,
        "description": (
            "Two days building anything that improves student life on campus. Mentors "
            "from industry, free meals through the night, and prizes for best use of an "
            "AI API and best accessibility work."
        ),
    },
    {
        "id": 103,
        "club_id": 4,
        "title": "Unplugged: Acoustic Night",
        "venue": "Open Air Theatre",
        "starts_at": _days(3),
        "ends_at": _days(3) + timedelta(hours=3),
        "capacity": None,
        "registration_count": 210,
        "description": (
            "An evening of acoustic sets from student musicians. Open mic slots in the "
            "second half - bring an instrument or just sing, no audition needed."
        ),
    },
    {
        "id": 104,
        "club_id": 6,
        "title": "Pitch Deck Clinic with Alumni Founders",
        "venue": "Seminar Hall 2",
        "starts_at": _days(9),
        "ends_at": _days(9) + timedelta(hours=3),
        "capacity": 60,
        "registration_count": 41,
        "description": (
            "Bring a deck at any stage and get line-by-line feedback from three alumni "
            "founders who have raised seed rounds. Ten teams get a full slot; everyone "
            "else joins the group critique."
        ),
    },
    {
        "id": 105,
        "club_id": 7,
        "title": "Night Sky Photo Walk",
        "venue": "Meet at North Gate",
        "starts_at": _days(2),
        "ends_at": _days(2) + timedelta(hours=5),
        "capacity": 25,
        "registration_count": 25,
        "description": (
            "Astrophotography basics under a dark sky an hour out of the city. Tripods "
            "provided, transport arranged. Long exposure and stacking walkthrough on "
            "location."
        ),
    },
    {
        "id": 106,
        "club_id": 5,
        "title": "Inter-Department Football League: Opening Fixture",
        "venue": "Main Ground",
        "starts_at": _days(-4),
        "ends_at": _days(-4) + timedelta(hours=2),
        "capacity": None,
        "registration_count": 340,
        "description": (
            "Opening match of the departmental league season. Free entry for spectators; "
            "squad lists close a week before kickoff."
        ),
    },
]

_ANNOUNCEMENTS = [
    {
        "id": 201,
        "club_id": 2,
        "title": "Hackathon team registration closes Friday",
        "body": (
            "Teams of up to four. Register at the Coding Club desk or through the events "
            "page. Solo entrants will be matched into teams on the first morning."
        ),
        "category": AnnouncementCategory.EVENT_UPDATE,
        "is_pinned": True,
        "created_at": _days(-1),
    },
    {
        "id": 202,
        "club_id": 7,
        "title": "Camera library now open to all members",
        "body": (
            "Two DSLRs and a wide-angle lens are available to borrow for up to three "
            "days. Sign out through the club leader; deposit waived for members."
        ),
        "category": AnnouncementCategory.RESOURCE,
        "is_pinned": False,
        "created_at": _days(-3),
    },
    {
        "id": 203,
        "club_id": 1,
        "title": "Workshop lab timings extended",
        "body": (
            "The hardware lab is now open until 9pm on weekdays through the RoboWars "
            "build period. Bring your ID card for after-hours access."
        ),
        "category": AnnouncementCategory.GENERAL,
        "is_pinned": False,
        "created_at": _days(-5),
    },
    {
        "id": 204,
        "club_id": 6,
        "title": "E-Cell team places second at the national B-plan finals",
        "body": (
            "Congratulations to the team for a runner-up finish and a cash prize at the "
            "national business plan competition. Full write-up on the club page."
        ),
        "category": AnnouncementCategory.ACHIEVEMENT,
        "is_pinned": False,
        "created_at": _days(-8),
    },
    {
        "id": 205,
        "club_id": 4,
        "title": "Jam room booking moves online",
        "body": (
            "Slots are now booked through the club page instead of the noticeboard. "
            "Two-hour maximum per booking so everyone gets time."
        ),
        "category": AnnouncementCategory.GENERAL,
        "is_pinned": False,
        "created_at": _days(-11),
    },
]

_CLUB_NAMES = {club["id"]: club["name"] for club in _CLUBS}
_CLUB_HEADS = {club["id"]: club["head_name"] for club in _CLUBS}


def _matches(text_fields: list, query: str | None) -> bool:
    if not query:
        return True
    needle = query.strip().lower()
    return any(needle in (field or "").lower() for field in text_fields)


def _seats_left(capacity, registered: int):
    return None if capacity is None else max(capacity - registered, 0)


def _club_list_item(club: dict) -> ClubListItem:
    return ClubListItem(
        id=club["id"],
        name=club["name"],
        description=club["description"],
        category=club["category"],
        type=club["type"],
        status=ClubStatus.ACTIVE,
        image_url=None,
        member_count=club["member_count"],
        head_name=club["head_name"],
        created_at=_days(-365),
        links=[],
    )


def _event_list_item(event: dict) -> EventListItem:
    return EventListItem(
        id=event["id"],
        club_id=event["club_id"],
        club_name=_CLUB_NAMES[event["club_id"]],
        title=event["title"],
        description=event.get("description", ""),
        venue=event["venue"],
        starts_at=event["starts_at"],
        ends_at=event["ends_at"],
        capacity=event["capacity"],
        registration_count=event["registration_count"],
        seats_left=_seats_left(event["capacity"], event["registration_count"]),
        status=EventStatus.PUBLISHED,
        image_url=None,
        created_at=_days(-30),
        results_declared=event.get("results_declared", False),
    )


# ---------------------------------------------------------------------------
# Service stand-ins
#
# Same method names, same parameters, same return types as the real services.
# tools.py cannot tell the difference, which is the whole point - the agent
# exercises one code path regardless of which tier is serving it.
# ---------------------------------------------------------------------------


class DemoClubService:
    async def list(self, payload: dict, status=None, search: str | None = None,
                   category: str | None = None, type=None) -> list[ClubListItem]:
        rows = _CLUBS
        if search:
            rows = [c for c in rows if _matches([c["name"], c["description"], c["category"]], search)]
        if category:
            rows = [c for c in rows if c["category"].lower() == category.strip().lower()]
        if type is not None:
            rows = [c for c in rows if c["type"] == type]
        return [_club_list_item(club) for club in rows]

    async def get(self, payload: dict, club_id: int) -> ClubDetailResponse:
        club = next((c for c in _CLUBS if c["id"] == club_id), None)
        if club is None:
            raise ClubNotFoundError()
        return ClubDetailResponse(
            id=club["id"],
            name=club["name"],
            description=club["description"],
            category=club["category"],
            type=club["type"],
            status=ClubStatus.ACTIVE,
            image_url=None,
            member_count=club["member_count"],
            created_at=_days(-365),
            links=[ClubLinkSchema(label=label, url=url) for label, url in club["links"]],
            # Contact fields stay None here exactly as they do for a student
            # caller against the real service.
            head=ClubHeadInfo(student_id=club["id"] * 10, full_name=club["head_name"]),
        )

    async def my_clubs(self, payload: dict, role=None, status=None) -> list[MyClubItem]:
        items = []
        for club in _CLUBS:
            membership = _MY_MEMBERSHIPS.get(club["id"])
            if membership is None:
                continue
            membership_role, membership_status, joined_at = membership
            if role is not None and membership_role != role:
                continue
            items.append(
                MyClubItem(
                    **_club_list_item(club).model_dump(),
                    membership_id=club["id"] * 100,
                    membership_role=membership_role,
                    membership_status=membership_status,
                    joined_at=joined_at,
                )
            )
        return items


class DemoEventService:
    async def list(self, payload: dict, status=None, club_id: int | None = None,
                   search: str | None = None, upcoming_only: bool = False) -> list[EventListItem]:
        rows = _EVENTS
        if club_id is not None:
            rows = [e for e in rows if e["club_id"] == club_id]
        if search:
            rows = [e for e in rows if _matches([e["title"], e["description"]], search)]
        if upcoming_only:
            rows = [e for e in rows if e["starts_at"] > _NOW]
        rows = sorted(rows, key=lambda e: e["starts_at"])
        return [_event_list_item(event) for event in rows]

    async def get(self, payload: dict, event_id: int) -> EventDetailResponse:
        event = next((e for e in _EVENTS if e["id"] == event_id), None)
        if event is None:
            raise EventNotFoundError()
        # description now comes through the list-item dump, since EventListItem
        # carries it too - passing it again here would be a duplicate keyword.
        return EventDetailResponse(
            **_event_list_item(event).model_dump(),
            is_registered=False,
            my_registration_id=None,
        )


class DemoAnnouncementService:
    async def feed(self, payload: dict, club_id: int | None = None, category=None,
                   search: str | None = None, limit: int = 50, offset: int = 0) -> list[AnnouncementItem]:
        rows = _ANNOUNCEMENTS
        if club_id is not None:
            rows = [a for a in rows if a["club_id"] == club_id]
        if category is not None:
            rows = [a for a in rows if a["category"] == category]
        if search:
            rows = [a for a in rows if _matches([a["title"], a["body"]], search)]
        rows = sorted(rows, key=lambda a: (not a["is_pinned"], -a["created_at"].timestamp()))
        rows = rows[offset:offset + limit]
        return [
            AnnouncementItem(
                id=a["id"],
                club_id=a["club_id"],
                club_name=_CLUB_NAMES[a["club_id"]],
                author_id=a["club_id"] * 10,
                author_name=_CLUB_HEADS[a["club_id"]],
                title=a["title"],
                body=a["body"],
                category=a["category"],
                is_pinned=a["is_pinned"],
                unread=False,
                created_at=a["created_at"],
            )
            for a in rows
        ]


class DemoStudentService:
    """
    Stand-in profile for the demo campus.

    Deliberately empty rather than invented: the demo student has not
    onboarded, so recommendations rank on the question they typed. Putting
    fake interests here would quietly change what the sample campus
    recommends and make the demo unrepresentative.
    """

    async def my_profile(self, payload: dict):
        return SimpleNamespace(interests=[], branch=None, year=None)


# Kept as a private alias so resolve_services can name it without exporting a
# second public symbol for the same thing.
_DemoStudentService = DemoStudentService


def build_demo_services() -> Services:
    return Services(
        club=DemoClubService(),
        event=DemoEventService(),
        announcement=DemoAnnouncementService(),
        student=DemoStudentService(),
    )


async def resolve_services(payload: dict, club_service, event_service, announcement_service,
                           student_service=None):
    """
    Pick the tier that serves this turn, and say which one it was.

    Returns (services, offline). One cheap probe - list this college's clubs -
    decides it, because that call is the common ancestor of nearly every tool
    and it fails in exactly the ways we care about:

      * the connection raises          -> database unreachable, go offline
      * the caller has no college/student row -> nothing to ground on, go offline
      * it succeeds but returns zero clubs    -> a live but unseeded college,
        which would make every answer "I couldn't find anything" and demo as a
        broken feature rather than an empty one

    The last case is a judgement call worth being explicit about: we prefer a
    clearly-labelled demo campus over a technically-correct empty one. The
    label is what keeps it honest - degraded=true rides on the response and the
    reply text says the data is sample data.
    """
    try:
        clubs = await club_service.list(payload)
    except Exception:  # noqa: BLE001 - any failure here means "cannot ground", tier down
        return build_demo_services(), True

    if not clubs:
        return build_demo_services(), True

    return (
        Services(
            club=club_service,
            event=event_service,
            announcement=announcement_service,
            student=student_service or _DemoStudentService(),
        ),
        False,
    )
