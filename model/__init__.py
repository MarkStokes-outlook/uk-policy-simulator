"""Fiscal modelling package for the UK Policy Sandbox."""

from .fiscal_model import (
    AssumptionError,
    Baseline,
    BaselineError,
    FeedbackAssumptions,
    FiscalResult,
    LeverError,
    REQUIRED_METRICS,
    compute_fiscal,
    load_baseline,
)
from .scenarios import (
    INVESTMENT_LEVER_KEYS,
    REVENUE_LEVER_KEYS,
    SCENARIO_SCHEMA_VERSION,
    Scenario,
    ScenarioError,
    load_scenarios,
)
from .scoring import (
    CATEGORY_DIRECTIONS,
    CATEGORY_LABELS,
    CONTRIBUTIONS,
    SCORE_CATEGORIES,
    WEIGHTING_SCHEMA_VERSION,
    CategoryScore,
    ScoreCard,
    ScoringError,
    WeightingProfile,
    build_scorecard,
    load_weighting_profiles,
    score_categories,
)

__all__ = [
    "AssumptionError",
    "Baseline",
    "BaselineError",
    "FeedbackAssumptions",
    "FiscalResult",
    "LeverError",
    "REQUIRED_METRICS",
    "compute_fiscal",
    "load_baseline",
    # Scenario presets (EPIC-002)
    "INVESTMENT_LEVER_KEYS",
    "REVENUE_LEVER_KEYS",
    "SCENARIO_SCHEMA_VERSION",
    "Scenario",
    "ScenarioError",
    "load_scenarios",
    # Deterministic scoring (EPIC-003)
    "CATEGORY_DIRECTIONS",
    "CATEGORY_LABELS",
    "CONTRIBUTIONS",
    "SCORE_CATEGORIES",
    "WEIGHTING_SCHEMA_VERSION",
    "CategoryScore",
    "ScoreCard",
    "ScoringError",
    "WeightingProfile",
    "build_scorecard",
    "load_weighting_profiles",
    "score_categories",
]
