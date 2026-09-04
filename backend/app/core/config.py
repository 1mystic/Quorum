"""
One place for every setting the backend reads.

Only DATABASE_URL, JWT_SECRET_KEY and FRONTEND_URL are genuinely required -
the app cannot run at all without a database, a way to sign tokens, and a
known frontend origin for CORS/password-reset links. Everything else below
them has a safe default and degrades gracefully when left unset:

- Empty AWS_*/S3_BUCKET_NAME: certificate upload falls back to storing the
  PDF bytes in Postgres itself (app/core/storage.py), never raises.
- Empty SMTP_HOST/etc: a send failure is caught and logged, never raised
  (app/core/mailer.py) - password-reset emails just do not arrive.
- TEST_DATABASE_URL is read only by the test harness (tests/conftest.py),
  never by the running app - it must not be required to boot in production.
- An empty ANTHROPIC_API_KEY means the AI module runs in deterministic mock
  mode. That is what the offline test suite relies on, and what keeps the
  assistant demoable with no network at all.
- An empty SARVAM_API_KEY means the voice router reports realtime voice as
  unavailable, and the frontend falls back to the browser's own narrator.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Core service configuration (required) --------------------------
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    FRONTEND_URL: str

    # Test-only, never read by the running app - see the module docstring.
    TEST_DATABASE_URL: str = ""

    # --- Certificate storage (optional) ----------------------------------
    AWS_REGION: str = ""
    S3_BUCKET_NAME: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    # Used only to build a download link for certificates that fell back to
    # Postgres storage because S3 upload failed (see Certificate.pdf_data).
    BACKEND_BASE_URL: str = "http://localhost:8000"

    # --- Outbound mail (optional) -----------------------------------------
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    MAIL_FROM: str = ""

    # --- Google OAuth ------------------------------------------------------
    GOOGLE_CLIENT_ID: str = ""

    # --- LLM provider selection -------------------------------------------
    AI_PROVIDER: str = "auto"

    # --- Claude ----------------------------------------------------------
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"

    # --- OpenAI-compatible ------------------------------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-nano"
    OPENAI_BASE_URL: str = ""

    # Timezone is a per-tenant setting (Tenant.timezone), not global - see
    # docs/GLOSSARY.md's COLLEGE_TIMEZONE -> TENANT_TIMEZONE row.

    # --- Sarvam AI (voice) ------------------------------------------------
    SARVAM_API_KEY: str = ""
    SARVAM_STT_MODEL: str = "saaras:v3-realtime"
    SARVAM_TTS_MODEL: str = "bulbul:v3"
    SARVAM_TTS_SPEAKER: str = "anushka"
    SARVAM_SAMPLE_RATE: int = 16000
    # The relay is I/O bound, but each open session still holds buffers and a
    # socket. Cap concurrency rather than memory on a 2 GB box.
    VOICE_MAX_CONCURRENT_SESSIONS: int = 3

    # --- Sarvam spend guard --------------------------------------------
    # We hold a very small amount of Sarvam credit, so the meter is a hard
    # product requirement rather than a nicety. agent/voice_budget.py
    # tracks estimated spend and the voice router refuses to open a paid
    # session once the cap is reached - at which point the frontend falls
    # back to the free browser narrator instead of failing.
    #
    # Published Sarvam rates (INR):
    #   Saaras v3 speech-to-text : 30.00 per hour, billed per second
    #   Bulbul v3 text-to-speech : 30.00 per 10,000 characters
    SARVAM_BUDGET_RUPEES: float = 5.0
    SARVAM_STT_RUPEES_PER_HOUR: float = 30.0
    SARVAM_TTS_RUPEES_PER_10K_CHARS: float = 30.0
    # Belt and braces on top of the rupee cap: bound any single session so one
    # stuck microphone cannot drain the whole budget.
    VOICE_MAX_SESSION_SECONDS: float = 90.0
    VOICE_MAX_REPLY_CHARS: int = 400

    # --- Agent loop budget ---------------------------------------------
    # Hard caps for the bounded tool-calling loop, described in
    # docs/AI_ARCHITECTURE_DECISIONS.md. Settings rather than constants so a
    # demo can tighten them without a code change.
    AGENT_MAX_ITERATIONS: int = 4
    AGENT_MAX_TOOL_CALLS: int = 6
    AGENT_MAX_INPUT_TOKENS: int = 12000
    AGENT_DEADLINE_SECONDS: float = 20.0
    AGENT_MAX_OUTPUT_TOKENS: int = 400

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
