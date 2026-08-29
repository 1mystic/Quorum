from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    club_id: int
    name: str
    image_url: str | None
    category: str
    score: int
    events_held: int
    new_members: int
    issues_resolved: int
    attendance_rate: float
    attendance_bonus: int
