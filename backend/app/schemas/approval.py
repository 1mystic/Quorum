"""
Shared across the events/announcements/decisions review gate: draft ->
submitted -> tenant-admin approved/rejected -> live. One small request shape
so the three services do not each redeclare the same field.
"""
from pydantic import BaseModel, Field


class RejectContentRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)
