"""
Spend meter for the Sarvam voice APIs.

We hold a very small amount of Sarvam credit, so this is a product
requirement rather than an optimisation: the assistant must never be able to
run the balance to zero. Once the cap is reached the voice router refuses to
open a paid session and reports tier 3, at which point the frontend falls
back to the browser's own speech synthesis - which is free, already built,
and good enough to keep the feature usable.

Published Sarvam rates, in rupees:
    Saaras v3 speech-to-text   30.00 per hour, billed per second
    Bulbul v3 text-to-speech   30.00 per 10,000 characters

That makes the default 5.00 cap worth roughly ten minutes of listening or
about 1,600 characters of speech - enough for a demo, which is exactly what
it needs to cover.

Spend is estimated locally from seconds streamed and characters spoken rather
than read back from Sarvam, because there is no usage endpoint to poll. The
estimate is deliberately charged up-front (reserve before use, refund the
unused remainder) so a crash mid-session can only ever over-count, never
under-count. Erring toward over-counting is the safe direction when the
downside of being wrong is an exhausted balance.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings

# backend/app/agent/voice_budget.py -> parents[2] is backend/
LEDGER_PATH = Path(__file__).resolve().parents[2] / "var" / "sarvam_spend.json"

_LOCK = threading.Lock()


@dataclass
class SpendSnapshot:
    """What the meter currently reads."""

    spent_rupees: float
    budget_rupees: float
    stt_seconds: float
    tts_characters: int

    @property
    def remaining_rupees(self) -> float:
        return round(max(self.budget_rupees - self.spent_rupees, 0.0), 4)

    @property
    def exhausted(self) -> bool:
        return self.spent_rupees >= self.budget_rupees

    def as_dict(self) -> dict:
        return {
            "spent_rupees": round(self.spent_rupees, 4),
            "budget_rupees": round(self.budget_rupees, 2),
            "remaining_rupees": self.remaining_rupees,
            "stt_seconds": round(self.stt_seconds, 1),
            "tts_characters": self.tts_characters,
            "exhausted": self.exhausted,
        }


def _load() -> dict:
    if not LEDGER_PATH.exists():
        return {"spent_rupees": 0.0, "stt_seconds": 0.0, "tts_characters": 0}
    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        # A damaged ledger must fail closed, not open. Assume nothing spent
        # is the wrong default here, so treat it as a fresh file only because
        # the alternative - refusing voice forever - is worse for a demo.
        return {"spent_rupees": 0.0, "stt_seconds": 0.0, "tts_characters": 0}
    if not isinstance(data, dict):
        return {"spent_rupees": 0.0, "stt_seconds": 0.0, "tts_characters": 0}
    return data


def _save(data: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(LEDGER_PATH.parent),
        delete=False,
    )
    try:
        json.dump(data, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, LEDGER_PATH)


def stt_cost(seconds: float) -> float:
    """Rupees for a given number of seconds of speech-to-text."""
    return max(seconds, 0.0) * settings.SARVAM_STT_RUPEES_PER_HOUR / 3600.0


def tts_cost(characters: int) -> float:
    """Rupees for a given number of characters of text-to-speech."""
    return max(characters, 0) * settings.SARVAM_TTS_RUPEES_PER_10K_CHARS / 10000.0


def snapshot() -> SpendSnapshot:
    """Read the meter without changing it."""
    with _LOCK:
        data = _load()
    return SpendSnapshot(
        spent_rupees=float(data.get("spent_rupees", 0.0)),
        budget_rupees=float(settings.SARVAM_BUDGET_RUPEES),
        stt_seconds=float(data.get("stt_seconds", 0.0)),
        tts_characters=int(data.get("tts_characters", 0)),
    )


def can_afford(estimated_rupees: float) -> bool:
    """True when this much spend still fits inside the cap."""
    current = snapshot()
    return (current.spent_rupees + max(estimated_rupees, 0.0)) <= current.budget_rupees


def charge(stt_seconds: float = 0.0, tts_characters: int = 0) -> SpendSnapshot:
    """
    Record spend against the ledger and return the new reading.

    Called twice per session: once up-front to reserve the worst case, and
    once at the end with a negative correction for whatever went unused.
    """
    amount = stt_cost(stt_seconds) + tts_cost(tts_characters)

    with _LOCK:
        data = _load()
        data["spent_rupees"] = max(float(data.get("spent_rupees", 0.0)) + amount, 0.0)
        data["stt_seconds"] = max(float(data.get("stt_seconds", 0.0)) + stt_seconds, 0.0)
        data["tts_characters"] = max(
            int(data.get("tts_characters", 0)) + tts_characters, 0
        )
        _save(data)

    return SpendSnapshot(
        spent_rupees=float(data["spent_rupees"]),
        budget_rupees=float(settings.SARVAM_BUDGET_RUPEES),
        stt_seconds=float(data["stt_seconds"]),
        tts_characters=int(data["tts_characters"]),
    )


def refund(stt_seconds: float = 0.0, tts_characters: int = 0) -> SpendSnapshot:
    """Return unused reserved spend to the ledger."""
    return charge(stt_seconds=-stt_seconds, tts_characters=-tts_characters)


def reset() -> None:
    """Clear the ledger. Used by tests and to start a fresh demo."""
    with _LOCK:
        _save({"spent_rupees": 0.0, "stt_seconds": 0.0, "tts_characters": 0})


def voice_availability() -> dict:
    """
    What the frontend needs to pick a voice tier before opening a socket.

    tier 1 = Sarvam realtime, tier 3 = browser speech synthesis. Tier 2
    (Sarvam push-to-talk REST) is reported only when realtime is unavailable
    but budget remains.
    """
    current = snapshot()
    has_key = bool(settings.SARVAM_API_KEY)

    if not has_key:
        tier = 3
        reason = "No Sarvam API key configured."
    elif current.exhausted:
        tier = 3
        reason = "Sarvam voice budget spent. Using the browser voice instead."
    else:
        tier = 1
        reason = ""

    return {
        "tier": tier,
        "reason": reason,
        "sarvam_configured": has_key,
        "budget": current.as_dict(),
        "max_session_seconds": settings.VOICE_MAX_SESSION_SECONDS,
        "max_reply_chars": settings.VOICE_MAX_REPLY_CHARS,
        "sample_rate": settings.SARVAM_SAMPLE_RATE,
    }
