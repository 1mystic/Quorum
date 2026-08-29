"""
Tests for the mocked LLM client. These confirm the mock honours the same
contract the real Haiku client must: call_finder returns strict JSON scoped
to the candidates in the prompt, call_chat grounds its reply in the
AVAILABLE block using [[group:ID]] / [[event:ID]] tags.
"""
import json

from app.agent.llm_client import call_chat, call_finder


def test_call_finder_returns_json_for_every_candidate_in_prompt():
    prompt = (
        "CANDIDATES:\n"
        "- group_id=1 | Robotics Group | Technology | We build robots\n"
        "- group_id=2 | Poetry Society | Literature | Weekly readings\n"
    )
    raw = call_finder(prompt, candidate_hash="1,2")
    parsed = json.loads(raw)

    assert {item["group_id"] for item in parsed} == {1, 2}
    assert all(item["reason"] for item in parsed)


def test_call_finder_is_cached_for_the_same_prompt_and_hash():
    prompt = "CANDIDATES:\n- group_id=1 | Robotics Group | Technology | We build robots\n"
    assert call_finder(prompt, candidate_hash="1") == call_finder(prompt, candidate_hash="1")


def test_call_chat_references_a_group_from_available_block():
    system = (
        "AVAILABLE:\n"
        "[[group:1]] Robotics Group (Technology) - We build robots\n"
    )
    reply = call_chat(system, history=[{"role": "user", "content": "robots?"}])
    assert "[[group:1]]" in reply


def test_call_chat_falls_back_gracefully_with_nothing_available():
    reply = call_chat("AVAILABLE:\n(no groups or public events available yet)\n", history=[])
    assert "[[" not in reply
