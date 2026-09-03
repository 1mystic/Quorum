"""
Unit tests for the deterministic intent-extraction fallback
(app/agent/intent._mock_extract), used whenever no LLM provider is
configured or the provider call fails.

Runnable with no schema, no network, no LLM:
uv run pytest tests/unit/agent/ -q
"""
import pytest

from app.agent import intent


CATEGORIES = ["Technology", "Arts", "Sports", "Science", "Literature"]


@pytest.mark.asyncio
class TestMockExtractTopiclessPhrasings:
    """Genuinely topic-less, generic asks must come back with no keywords,
    so callers do not mistake filler ("popular", "happening", "week") for a
    stated subject and wrongly suppress a popularity/upcoming-events
    fallback."""

    async def test_anything_popular_has_no_keywords(self):
        signal = await intent.extract_interest_signal(
            "Anything popular I should know about?", CATEGORIES
        )
        assert signal["keywords"] == []
        assert signal["on_topic"] is True

    async def test_whats_happening_this_week_has_no_keywords(self):
        signal = await intent.extract_interest_signal(
            "what's happening this week", CATEGORIES
        )
        assert signal["keywords"] == []
        # "happening" is still recognised as event-language, just not a topic.
        assert signal["wants_events"] is True

    async def test_suggest_me_something_has_no_keywords(self):
        signal = await intent.extract_interest_signal(
            "suggest me something to join", CATEGORIES
        )
        assert signal["keywords"] == []


@pytest.mark.asyncio
class TestMockExtractTopicSpecificPhrasingsStillNarrow:
    """A genuinely named subject must still come through as a keyword - the
    fallback must not become so aggressive that it launders real topics into
    the topic-less bucket."""

    async def test_any_photography_groups_keeps_photography(self):
        signal = await intent.extract_interest_signal(
            "any photography groups?", CATEGORIES
        )
        assert signal["keywords"] == ["photography"]

    async def test_robotics_sentence_keeps_robotics(self):
        signal = await intent.extract_interest_signal(
            "I want to join a group for robotics", CATEGORIES
        )
        assert signal["keywords"] == ["robotics"]

    async def test_event_language_does_not_eat_a_real_topic(self):
        signal = await intent.extract_interest_signal(
            "any coding events this week", CATEGORIES
        )
        assert signal["keywords"] == ["coding"]
        assert signal["wants_events"] is True
