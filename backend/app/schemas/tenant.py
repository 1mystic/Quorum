from pydantic import BaseModel, Field, field_validator

SLUG_PATTERN = r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"

class TenantOnboardingRequest(BaseModel):
    name: str = Field(..., min_length=5, max_length=100)
    slug: str = Field(..., min_length=3, max_length=100, pattern=SLUG_PATTERN)
    vertical: str = Field(..., min_length=2, max_length=50)
    description: str = Field(..., min_length=5, max_length=1000)

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

class TenantOnboardingResponse(BaseModel):
    name: str
    slug: str
    vertical: str
    description: str
    message: str


class TenantInfoResponse(BaseModel):
    """What every authenticated tenant member needs to render the shell of
    the app (name, vertical manifest to load, which Insight Packs are on)."""
    name: str
    slug: str
    vertical: str
    description: str | None
    enabled_packs: list[str]
    timezone: str
