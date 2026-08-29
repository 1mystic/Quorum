"""
pytest suite for the deterministic recommender core.

Runnable with no schema, no network, no LLM. Run from backend/ with:
uv run pytest tests/test_recommender.py -q

Covers the test-design tables: scoring, selection/fallbacks, JSON validation,
chat entity grounding, and privacy (no email leakage).
"""
import pytest

from app.agent.recommender import (
    normalize_tokens, score_group, score_event, select_recommendations,
    validate_finder_json, resolve_entities, scrub_emails,
)


# --- fixtures / builders ----------------------------------------------------
def group(id, name, category, desc, score=0, leader="Lead", tags=None):
    return {"id": id, "name": name, "category": category, "description": desc,
            "activity_score": score, "leader_name": leader, "tags": tags or []}


def event(id, title, desc, group_name="Some Group", leader="Lead"):
    # Shaped to the schema's events table (no visibility flag - the discovery
    # layer already scopes to discoverable, upcoming events).
    return {"id": id, "title": title, "description": desc,
            "group_id": 1, "venue": "", "group_name": group_name, "leader_name": leader}


def prof(interests=None, hobbies=None, reason="", branch="cse", year=2):
    return {"interests": interests or [], "hobbies": hobbies or [],
            "reason": reason, "branch": branch, "year": year}


ROBO = group(1, "Robotics Group", "Technology", "We build robots and drones", score=100)
POET = group(2, "Poetry Society", "Literature", "Weekly poetry readings", score=10)
ASTRO = group(3, "Astronomy Group", "Science", "Stargazing and telescopes", score=40)


# --- tokenisation -----------------------------------------------------------
def test_stopwords_and_short_tokens_removed():
    assert normalize_tokens("I want to join a group for robotics") == {"robotics"}


# --- score_group -------------------------------------------------------------
class TestScoreGroup:
    def test_exact_interest_match_scores_high(self):
        assert score_group(prof(interests=["robotics", "drones"]), ROBO, 100) >= 0.5

    def test_no_overlap_below_threshold(self):
        assert score_group(prof(interests=["poetry"]), ROBO, 100) < 0.30

    def test_deterministic(self):
        p = prof(interests=["robotics"])
        assert score_group(p, ROBO, 100) == score_group(p, ROBO, 100)

    def test_score_bounded(self):
        s = score_group(prof(interests=["robotics", "drones", "technology", "build"]), ROBO, 100)
        assert 0.0 <= s <= 1.0

    def test_popularity_breaks_ties(self):
        a = group(10, "A", "Science", "astronomy stars", score=90)
        b = group(11, "B", "Science", "astronomy stars", score=5)
        p = prof(interests=["astronomy", "stars"])
        assert score_group(p, a, 90) > score_group(p, b, 90)

    def test_empty_interests_still_ranks_via_branch_and_pop(self):
        # branch cse -> technology matches Robotics, plus popularity prior
        assert score_group(prof(interests=[], branch="cse"), ROBO, 100) > 0.0


# --- score_event ------------------------------------------------------------
def test_event_interest_match():
    e = event(5, "Astro Night", "stargazing telescopes astronomy")
    assert score_event(prof(interests=["astronomy", "stargazing"]), e) >= 0.25


# --- select_recommendations -------------------------------------------------
class TestSelect:
    def test_groups_first_when_match(self):
        out = select_recommendations(prof(interests=["robotics"]), [ROBO, POET], [])
        assert out["kind"] == "groups"
        assert out["items"][0]["id"] == 1

    def test_event_fallback_when_no_group(self):
        e = event(5, "Astro Night", "stargazing telescopes astronomy")
        out = select_recommendations(prof(interests=["astronomy", "stargazing"]), [POET], [e])
        assert out["kind"] == "event_fallback"
        assert "organiser" in out["message"].lower()

    def test_event_fallback_never_exposes_email(self):
        e = event(5, "Astro Night", "astronomy stars", leader="Asha")
        out = select_recommendations(prof(interests=["astronomy", "stars"]), [POET], [e])
        assert "@" not in out["message"]

    def test_irrelevant_event_not_surfaced(self):
        # An event that shares nothing with the member's interests is not
        # promoted; with no group match either, we fall back to popularity.
        e = event(6, "Chess Meetup", "board games and chess strategy")
        out = select_recommendations(prof(interests=["astronomy", "stars"]), [POET], [e])
        assert out["kind"] == "popularity"

    def test_popularity_when_nothing_matches(self):
        out = select_recommendations(prof(interests=["knitting"]), [ROBO, POET, ASTRO], [])
        assert out["kind"] == "popularity"
        assert out["items"][0]["id"] == 1  # highest activity_score


# --- validate_finder_json ---------------------------------------------------
class TestFinderJson:
    allowed = {1, 2, 3}

    def test_valid_array(self):
        raw = '[{"group_id":1,"reason":"builds robots"}]'
        assert validate_finder_json(raw, self.allowed) == [{"group_id": 1, "reason": "builds robots"}]

    def test_strips_code_fences(self):
        raw = '```json\n[{"group_id":2,"reason":"poetry"}]\n```'
        assert validate_finder_json(raw, self.allowed)[0]["group_id"] == 2

    def test_drops_hallucinated_id(self):
        raw = '[{"group_id":99,"reason":"nope"},{"group_id":1,"reason":"ok"}]'
        assert [o["group_id"] for o in validate_finder_json(raw, self.allowed)] == [1]

    def test_malformed_raises(self):
        with pytest.raises(Exception):
            validate_finder_json("Sure! here you go", self.allowed)

    def test_empty_array_ok(self):
        assert validate_finder_json("[]", self.allowed) == []

    def test_dedupes(self):
        raw = '[{"group_id":1,"reason":"a"},{"group_id":1,"reason":"b"}]'
        assert len(validate_finder_json(raw, self.allowed)) == 1


# --- chat grounding + privacy ----------------------------------------------
class TestChatGrounding:
    amap = {("group", 1): "Robotics Group", ("event", 5): "Astro Night"}

    def test_known_entity_resolved(self):
        text, unknown = resolve_entities("Try [[group:1]] today", self.amap)
        assert text == "Try Robotics Group today"
        assert unknown == []

    def test_unknown_entity_not_surfaced(self):
        text, unknown = resolve_entities("Check [[group:77]]", self.amap)
        assert "77" not in text
        assert "that option" in text
        assert unknown == [("group", 77)]

    def test_plain_text_passthrough(self):
        text, unknown = resolve_entities("No groups match your interest.", self.amap)
        assert text == "No groups match your interest."
        assert unknown == []

    def test_email_scrubbed(self):
        assert "@" not in scrub_emails("contact lead@knit.ac.in please")
