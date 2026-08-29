"""
The five grounding gates, and the allow-list they are built on.

The whole safety argument of this module is that a wrong answer should be
*unreachable*, not merely detected afterwards. A classifier that inspects
output and asks "does this look like a hallucination?" can be fooled. An
allow-list that never gives the model a club it may not name cannot.

    Gate 1  Tool-return allow-list   (here)
    Gate 2  College scoping          (every service call takes payload, which
                                      resolves the caller's own college - a
                                      tool has no college_id parameter to abuse)
    Gate 3  Entity-id resolution     (here, reusing recommender.resolve_entities)
    Gate 4  Email scrubbing          (here, reusing recommender.scrub_emails)
    Gate 5  Read-only tool surface   (tools.py calls only .list()/.get()/
                                      .my_clubs()/.feed() - no write method
                                      is reachable from the registry)

Gates 3 and 4 are deliberately thin wrappers over the v1 implementations in
agent/recommender.py. Those functions are already covered by the existing
test suite, and rewriting working security code to make it look new would be
a poor trade.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.agent import recommender as R


@dataclass
class AllowList:
    """
    Gate 1: every entity the tools actually returned during this turn.

    The model may name an entity only if a tool put it here first. Nothing
    else in the system is permitted to add to it - in particular the model's
    own output never does, which is the point.
    """

    # (kind, id) -> display name, e.g. ("club", 3) -> "Robotics & Automation"
    entities: dict = field(default_factory=dict)

    def add(self, kind: str, entity_id, name: str) -> None:
        """Record one entity a tool returned."""
        if entity_id is None or not name:
            return
        try:
            key = (kind, int(entity_id))
        except (TypeError, ValueError):
            return
        self.entities[key] = str(name)

    def add_many(self, kind: str, rows: list, id_field: str, name_field: str) -> None:
        """Record every entity in a list of API rows."""
        for row in rows:
            if isinstance(row, dict):
                self.add(kind, row.get(id_field), row.get(name_field))

    def contains(self, kind: str, entity_id) -> bool:
        try:
            return (kind, int(entity_id)) in self.entities
        except (TypeError, ValueError):
            return False

    def as_map(self) -> dict:
        """The shape recommender.resolve_entities() expects."""
        return dict(self.entities)

    @property
    def size(self) -> int:
        return len(self.entities)


def apply_output_gates(text: str, allow_list: AllowList) -> tuple:
    """
    Run gates 1, 3 and 4 over one piece of model output.

    Returns (clean_text, unknown_refs). unknown_refs is non-empty only when
    the model referenced an entity no tool returned, which is exactly the
    signal worth logging and alerting on - it means either a prompt problem
    or a genuine hallucination attempt.
    """
    if not text:
        return "", []

    # Gate 3 (which enforces gate 1: resolution only succeeds for entities
    # the allow-list holds; anything else becomes "that option").
    clean, unknown = R.resolve_entities(text, allow_list.as_map())

    # Gate 4.
    clean = R.scrub_emails(clean)

    # Defence in depth: stop the model echoing a raw candidate block back as
    # prose, which would leak the internal listing format to the student.
    clean = R.strip_echoed_listing(clean)

    return clean.strip(), unknown


def redact_for_model(rows: list, allowed_fields: list) -> list:
    """
    Project API rows down to the fields the model is allowed to see.

    The upstream API already omits emails from club and event payloads, but
    relying on a remote service's response shape for a safety property is
    fragile - it could gain a field in a future release and we would never
    notice. Whitelisting fields here means new upstream fields are invisible
    to the model until someone deliberately adds them.
    """
    projected = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = {}
        for field_name in allowed_fields:
            if field_name in row and row[field_name] is not None:
                item[field_name] = row[field_name]
        if item:
            projected.append(item)
    return projected
