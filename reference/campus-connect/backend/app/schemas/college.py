from pydantic import BaseModel, Field, field_validator

EMAIL_SUFFIX_PATTERN = r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"

class CollegeOnboardingRequest(BaseModel):
    name: str = Field(..., min_length=5, max_length=100)
    email_suffix: str = Field(..., min_length=3, max_length=100, pattern=EMAIL_SUFFIX_PATTERN)
    description: str = Field(..., min_length=5, max_length=1000)

    @field_validator("email_suffix", mode="before")
    @classmethod
    def normalize_email_suffix(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

class CollegeOnboardingResponse(BaseModel):
    name: str
    slug: str
    email_suffix: str
    description: str
    message: str
