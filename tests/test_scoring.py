"""Tests for deterministic scoring (EPIC-003).

Covers the scoring engine (categories, ranges, determinism, monotonicity,
baseline neutrality), the weighted overall, and weighting-profile loading and
validation. Run with: pytest
"""

import math
import textwrap
from pathlib import Path

import pytest

from model.fiscal_model import Baseline, FeedbackAssumptions, compute_fiscal
from model.scenarios import (
    INVESTMENT_LEVER_KEYS,
    REVENUE_LEVER_KEYS,
    load_scenarios,
)
from model.scoring import (
    CONTRIBUTIONS,
    SCORE_CATEGORIES,
    WEIGHTING_SCHEMA_VERSION,
    ScoringError,
    WeightingProfile,
    build_scorecard,
    load_weighting_profiles,
    score_categories,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEIGHTING_YAML = REPO_ROOT / "weighting_profiles.yaml"
SCENARIOS_YAML = REPO_ROOT / "scenarios.yaml"

EXPECTED_PROFILE_IDS = {
    "balanced",
    "fiscal_conservative",
    "social_democratic",
    "green_investment",
    "libertarian",
}


# --- Helpers -------------------------------------------------------------

BASELINE = Baseline(receipts=1100.0, spending=1230.0, gdp=2700.0)
ASSUMPTIONS = FeedbackAssumptions(
    years=10,
    growth_baseline=0.035,
    revenue_feedback_rate=0.3,
    cost_reduction_rate=0.2,
    lag_years=2,
    implementation_quality=0.7,
    optimism_penalty=0.2,
)


def _zero_levers() -> tuple[dict, dict]:
    rev = {k: 0.0 for k in REVENUE_LEVER_KEYS}
    inv = {k: 0.0 for k in INVESTMENT_LEVER_KEYS}
    return rev, inv


def _score(rev: dict, inv: dict):
    result = compute_fiscal(BASELINE, rev, inv, ASSUMPTIONS)
    return score_categories(BASELINE, result, rev, inv)


# --- Category structure and ranges ---------------------------------------

def test_all_seven_categories_present_and_ordered():
    rev, inv = _zero_levers()
    scores = _score(rev, inv)
    assert tuple(scores) == SCORE_CATEGORIES
    assert len(scores) == 7


def test_scores_within_range_for_extreme_inputs():
    rev = {k: 100.0 for k in REVENUE_LEVER_KEYS}
    inv = {k: 100.0 for k in INVESTMENT_LEVER_KEYS}
    scores = _score(rev, inv)
    for cat in scores.values():
        assert 0.0 <= cat.score <= 100.0
        assert cat.label
        assert cat.direction
        assert cat.rationale


def test_scoring_is_deterministic():
    rev, inv = _zero_levers()
    inv["housing"] = 40.0
    inv["welfare_floor"] = 25.0
    first = _score(rev, inv)
    second = _score(rev, inv)
    assert {k: v.score for k, v in first.items()} == {
        k: v.score for k, v in second.items()
    }


# --- Baseline neutrality --------------------------------------------------

def test_zero_levers_give_neutral_outcome_categories():
    rev, inv = _zero_levers()
    scores = _score(rev, inv)
    for cat in (
        "economic_growth",
        "poverty_reduction",
        "housing_affordability",
        "nhs_demand_impact",
        "income_equality",
    ):
        assert scores[cat].score == 50.0
        assert scores[cat].basis == {}


def test_zero_levers_give_max_simplicity():
    rev, inv = _zero_levers()
    scores = _score(rev, inv)
    # Doing nothing is trivial to implement -> complexity score is 100.
    assert scores["implementation_complexity"].score == 100.0


def test_fiscal_sustainability_tracks_deficit():
    # A revenue rise should not lower the fiscal sustainability score vs baseline.
    rev, inv = _zero_levers()
    base_scores = _score(rev, inv)
    rev["income_tax_ni"] = 50.0
    better = _score(rev, inv)
    assert better["fiscal_sustainability"].score >= base_scores["fiscal_sustainability"].score


# --- Monotonicity / directional sanity -----------------------------------

def test_welfare_raises_poverty_reduction():
    rev, inv = _zero_levers()
    low = _score(rev, inv)["poverty_reduction"].score
    inv["welfare_floor"] = 30.0
    high = _score(rev, inv)["poverty_reduction"].score
    assert high > low


def test_housing_raises_housing_affordability():
    rev, inv = _zero_levers()
    low = _score(rev, inv)["housing_affordability"].score
    inv["housing"] = 40.0
    high = _score(rev, inv)["housing_affordability"].score
    assert high > low


def test_bigger_programme_is_more_complex():
    rev, inv = _zero_levers()
    inv["housing"] = 20.0
    small = _score(rev, inv)["implementation_complexity"].score
    inv["housing"] = 90.0
    inv["nhs_prevention"] = 40.0
    big = _score(rev, inv)["implementation_complexity"].score
    assert big < small


def test_outcome_basis_explains_contributions():
    rev, inv = _zero_levers()
    inv["welfare_floor"] = 20.0
    poverty = _score(rev, inv)["poverty_reduction"]
    assert "welfare_floor" in poverty.basis
    expected = CONTRIBUTIONS["poverty_reduction"]["welfare_floor"] * 20.0
    assert poverty.basis["welfare_floor"] == pytest.approx(expected)


# --- Weighted overall -----------------------------------------------------

def test_balanced_overall_is_mean_of_categories():
    profiles = load_weighting_profiles(WEIGHTING_YAML)
    rev, inv = _zero_levers()
    inv["housing"] = 30.0
    scores = _score(rev, inv)
    card = build_scorecard(scores, profiles["balanced"])
    mean = sum(s.score for s in scores.values()) / len(scores)
    assert card.overall == pytest.approx(mean)
    assert 0.0 <= card.overall <= 100.0


def test_profiles_change_the_overall():
    profiles = load_weighting_profiles(WEIGHTING_YAML)
    rev, inv = _zero_levers()
    inv["welfare_floor"] = 40.0  # helps poverty/equality, costs fiscal+complexity
    scores = _score(rev, inv)
    social = build_scorecard(scores, profiles["social_democratic"]).overall
    libertarian = build_scorecard(scores, profiles["libertarian"]).overall
    assert social != libertarian


def test_build_scorecard_rejects_zero_weights():
    rev, inv = _zero_levers()
    scores = _score(rev, inv)
    profile = WeightingProfile(
        id="empty",
        name="Empty",
        summary="all zero",
        weights={c: 0.0 for c in SCORE_CATEGORIES},
    )
    with pytest.raises(ScoringError):
        build_scorecard(scores, profile)


def _full_weights(**overrides) -> dict:
    weights = {c: 1.0 for c in SCORE_CATEGORIES}
    weights.update(overrides)
    return weights


@pytest.mark.parametrize(
    "weights, match",
    [
        # Missing a category (manually built, not via the validated loader).
        ({c: 1.0 for c in SCORE_CATEGORIES if c != "income_equality"}, "missing"),
        # Negative weight that would otherwise pass because the sum stays positive.
        (_full_weights(income_equality=-1.0), ">= 0"),
        # Non-finite weight.
        (_full_weights(economic_growth=float("inf")), "finite"),
        # Unknown category key.
        ({**_full_weights(), "made_up": 1.0}, "unknown"),
    ],
)
def test_build_scorecard_rejects_invalid_manual_profiles(weights, match):
    rev, inv = _zero_levers()
    scores = _score(rev, inv)
    profile = WeightingProfile(id="manual", name="Manual", summary="x", weights=weights)
    with pytest.raises(ScoringError, match=match):
        build_scorecard(scores, profile)


# --- Weighting-profile loading -------------------------------------------

def test_canonical_weighting_file_loads_all_profiles():
    profiles = load_weighting_profiles(WEIGHTING_YAML)
    assert set(profiles) == EXPECTED_PROFILE_IDS
    for profile in profiles.values():
        assert set(profile.weights) == set(SCORE_CATEGORIES)
        assert all(w >= 0 for w in profile.weights.values())
        assert sum(profile.weights.values()) > 0
        assert profile.name and profile.summary


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "weights.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_missing_file_raises():
    with pytest.raises(ScoringError, match="not found"):
        load_weighting_profiles(Path("/no/such/weights.yaml"))


def test_unsupported_schema_version_raises(tmp_path):
    p = _write(tmp_path, """
        schema_version: 999
        profiles: []
    """)
    with pytest.raises(ScoringError, match="schema_version"):
        load_weighting_profiles(p)


def test_missing_weight_category_raises(tmp_path):
    p = _write(tmp_path, """
        schema_version: 1
        profiles:
          - id: broken
            name: Broken
            summary: missing a category
            weights:
              fiscal_sustainability: 1
              economic_growth: 1
              poverty_reduction: 1
              housing_affordability: 1
              nhs_demand_impact: 1
              income_equality: 1
    """)
    with pytest.raises(ScoringError, match="missing"):
        load_weighting_profiles(p)


def test_negative_weight_raises(tmp_path):
    p = _write(tmp_path, """
        schema_version: 1
        profiles:
          - id: broken
            name: Broken
            summary: negative weight
            weights:
              fiscal_sustainability: -1
              economic_growth: 1
              poverty_reduction: 1
              housing_affordability: 1
              nhs_demand_impact: 1
              income_equality: 1
              implementation_complexity: 1
    """)
    with pytest.raises(ScoringError, match=">= 0"):
        load_weighting_profiles(p)


def test_duplicate_profile_id_raises(tmp_path):
    profile = """
          - id: dup
            name: Dup
            summary: duplicate id
            weights:
              fiscal_sustainability: 1
              economic_growth: 1
              poverty_reduction: 1
              housing_affordability: 1
              nhs_demand_impact: 1
              income_equality: 1
              implementation_complexity: 1
    """
    p = _write(tmp_path, "schema_version: 1\nprofiles:\n" + profile + profile)
    with pytest.raises(ScoringError, match="Duplicate"):
        load_weighting_profiles(p)


# --- Scenario presets all score cleanly ----------------------------------

def test_all_presets_score_within_range():
    scenarios = load_scenarios(SCENARIOS_YAML)
    profiles = load_weighting_profiles(WEIGHTING_YAML)
    for scenario in scenarios.values():
        result = compute_fiscal(
            BASELINE, scenario.revenue_levers, scenario.investment_levers,
            scenario.assumptions,
        )
        scores = score_categories(
            BASELINE, result, scenario.revenue_levers, scenario.investment_levers
        )
        for cat in scores.values():
            assert 0.0 <= cat.score <= 100.0
        for profile in profiles.values():
            card = build_scorecard(scores, profile)
            assert 0.0 <= card.overall <= 100.0
            assert all(math.isfinite(s.score) for s in card.categories.values())
