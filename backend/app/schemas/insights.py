from datetime import datetime
from pydantic import BaseModel


class PackSummary(BaseModel):
    id: str
    name: str
    enabled: bool
    available: bool
    required_streams: list[str]
    streams_available: list[str]
    cadence: str
    services_ready: int = 0
    services_insufficient: int = 0
    services_blocked: int = 0
    last_computed_at: datetime | None = None
    reason: str | None = None


class PacksResponse(BaseModel):
    vertical: str
    packs: list[PackSummary]


class PackToggleRequest(BaseModel):
    enabled: bool


class PackToggleResponse(PackSummary):
    estimated_first_result_at: datetime | None = None


class InsightEnvelopeResponse(BaseModel):
    service: str
    pack: str
    scope: str
    evidence: dict
    computed_at: datetime | None
    stale_after: datetime | None
    is_stale: bool
    method_url: str


class InsightHealthResponse(BaseModel):
    total: int
    by_status: dict
    stale: int
    insufficient: int
    insufficient_services: list[dict]
    last_computed_at: datetime | None
