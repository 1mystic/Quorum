"""One text-completion interface, two backends: Anthropic and any
OpenAI-compatible endpoint, selected via settings.AI_PROVIDER."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("campus.agent")

ANTHROPIC = "anthropic"
OPENAI = "openai"


class ProviderError(RuntimeError):
    """The chosen provider could not serve this turn."""


@dataclass
class LLMReply:
    """One completion, plus enough metadata to see which backend produced it."""

    text: str
    provider: str
    model: str
    usage: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderChoice:
    name: str
    model: str
    api_key: str
    base_url: str = ""

    def __repr__(self) -> str:
        where = f", base_url={self.base_url!r}" if self.base_url else ""
        return f"ProviderChoice(name={self.name!r}, model={self.model!r}, api_key=<hidden>{where})"


def resolve() -> Optional[ProviderChoice]:
    """Which provider serves this turn, or None for the deterministic path."""
    mode = (settings.AI_PROVIDER or "auto").strip().lower()

    anthropic_key = (settings.ANTHROPIC_API_KEY or "").strip()
    openai_key = (settings.OPENAI_API_KEY or "").strip()

    def anthropic_choice() -> Optional[ProviderChoice]:
        if not anthropic_key:
            return None
        return ProviderChoice(ANTHROPIC, settings.ANTHROPIC_MODEL, anthropic_key)

    def openai_choice() -> Optional[ProviderChoice]:
        if not openai_key:
            return None
        return ProviderChoice(
            OPENAI,
            settings.OPENAI_MODEL,
            openai_key,
            (settings.OPENAI_BASE_URL or "").strip(),
        )

    if mode == "none":
        return None
    if mode == ANTHROPIC:
        return anthropic_choice()
    if mode == OPENAI:
        return openai_choice()

    if mode != "auto":
        logger.warning("unknown AI_PROVIDER %r, treating as auto", settings.AI_PROVIDER)

    return anthropic_choice() or openai_choice()


def describe() -> str:
    """Human-readable provider/model for logs and the API response."""
    choice = resolve()
    return f"{choice.name}:{choice.model}" if choice else "deterministic"


def normalize_history(messages: list) -> list:
    """Coerce a transcript into the shape both providers accept."""
    cleaned = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content})

    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)

    return cleaned


async def complete(
    system: str,
    messages: list,
    max_tokens: int,
    timeout_seconds: Optional[float] = None,
    temperature: Optional[float] = None,
    json_mode: bool = False,
) -> LLMReply:
    """Ask the configured provider for one completion."""
    choice = resolve()
    if choice is None:
        raise ProviderError("no LLM provider configured")

    history = normalize_history(messages)
    if not history:
        raise ProviderError("no conversation to send")

    deadline = timeout_seconds if timeout_seconds is not None else settings.AGENT_DEADLINE_SECONDS

    client = _client_for(choice)

    caller = _call_anthropic if choice.name == ANTHROPIC else _call_openai
    try:
        async with asyncio.timeout(deadline):
            return await caller(
                client, choice, system, history, max_tokens, temperature,
                json_mode, deadline,
            )
    except TimeoutError as exc:
        raise ProviderError(f"{choice.name} timed out after {deadline}s") from exc
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 - every provider failure degrades alike
        raise ProviderError(f"{choice.name} call failed: {exc}") from exc


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict:
    """Parse a JSON object out of a model reply."""
    match = _JSON_RE.search(text or "")
    if not match:
        raise ValueError("no JSON object in model reply")
    return json.loads(match.group(0))


async def warm_up(timeout_seconds: float = 20.0) -> None:
    """Pay the cold-start cost at boot instead of on a student's first question."""
    try:
        await complete(
            system="You are terse.",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            timeout_seconds=timeout_seconds,
        )
    except Exception:  # noqa: BLE001 - warmup must never block startup
        pass


_clients: dict = {}


def reset_clients() -> None:
    """Drop the cached clients. Tests use this after changing settings."""
    _clients.clear()


def _client_for(choice: ProviderChoice):
    key = (choice.name, choice.base_url)
    if key in _clients:
        return _clients[key]

    if choice.name == ANTHROPIC:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ProviderError("anthropic package is not installed") from exc
        client = AsyncAnthropic(api_key=choice.api_key, max_retries=0)
    else:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ProviderError("openai package is not installed") from exc
        client = AsyncOpenAI(
            api_key=choice.api_key,
            base_url=choice.base_url or None,
            max_retries=0,
        )

    _clients[key] = client
    return client


async def _call_anthropic(
    client, choice: ProviderChoice, system: str, history: list, max_tokens: int,
    temperature: Optional[float], json_mode: bool, deadline: float,
) -> LLMReply:
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = await client.with_options(timeout=deadline).messages.create(
        model=choice.model,
        max_tokens=max_tokens,
        system=system,
        messages=history,
        **kwargs,
    )

    return LLMReply(
        text=_text_from_anthropic(response),
        provider=choice.name,
        model=choice.model,
        usage=_usage_from_anthropic(getattr(response, "usage", None)),
    )


async def _call_openai(
    client, choice: ProviderChoice, system: str, history: list, max_tokens: int,
    temperature: Optional[float], json_mode: bool, deadline: float,
) -> LLMReply:
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.with_options(timeout=deadline).chat.completions.create(
        model=choice.model,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}] + history,
        **kwargs,
    )

    return LLMReply(
        text=_text_from_openai(response),
        provider=choice.name,
        model=choice.model,
        usage=_usage_from_openai(getattr(response, "usage", None)),
    )


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _text_from_anthropic(response) -> str:
    parts = []
    for block in _get(response, "content") or []:
        if _get(block, "type") == "text":
            text = _get(block, "text")
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _text_from_openai(response) -> str:
    choices = _get(response, "choices") or []
    if not choices:
        return ""
    message = _get(choices[0], "message")
    return (_get(message, "content") or "").strip()


def _read_int(usage, name: str) -> int:
    value = _get(usage, name)
    return int(value) if isinstance(value, (int, float)) else 0


def _usage_from_anthropic(usage) -> dict:
    if usage is None:
        return {}
    return {
        "input_tokens": _read_int(usage, "input_tokens"),
        "output_tokens": _read_int(usage, "output_tokens"),
        "cache_read_input_tokens": _read_int(usage, "cache_read_input_tokens"),
        "cache_creation_input_tokens": _read_int(usage, "cache_creation_input_tokens"),
    }


def _usage_from_openai(usage) -> dict:
    if usage is None:
        return {}
    return {
        "input_tokens": _read_int(usage, "prompt_tokens"),
        "output_tokens": _read_int(usage, "completion_tokens"),
    }
