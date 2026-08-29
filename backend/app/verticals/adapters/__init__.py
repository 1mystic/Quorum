"""
Vertical adapters: the only code in the platform that knows domain words.

`docs/DATA_SPINE.md` section 9. An adapter turns ORM rows into canonical stream
atoms, so that "complaint", "issue", "case" and "ticket" all become
`RequestEvent` before any statistic sees them. Nothing in `app/stats/` imports
from here, and nothing here is imported by `app/stats/`.
"""
from app.verticals.adapters.base import (
    BaseAdapter,
    PortedSchemaAdapter,
    VerticalAdapter,
)
from app.verticals.adapters.campus_club import CampusClubAdapter
from app.verticals.adapters.rwa_society import RwaSocietyAdapter

ADAPTERS: dict[str, type[PortedSchemaAdapter]] = {
    RwaSocietyAdapter.vertical_id: RwaSocietyAdapter,
    CampusClubAdapter.vertical_id: CampusClubAdapter,
}


def get_adapter(vertical_id: str) -> PortedSchemaAdapter:
    """A fresh adapter per call: the unmapped-value counters are per run, not global."""
    return ADAPTERS[vertical_id]()


__all__ = [
    "ADAPTERS",
    "BaseAdapter",
    "CampusClubAdapter",
    "PortedSchemaAdapter",
    "RwaSocietyAdapter",
    "VerticalAdapter",
    "get_adapter",
]
