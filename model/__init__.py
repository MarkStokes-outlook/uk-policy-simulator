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
from .saved_models import (
    SAVED_MODELS_SCHEMA_VERSION,
    ModelAuthorizationError,
    ModelStore,
    ModelStoreError,
    ModelVersion,
    SavedModel,
    authorize_mutation,
    can_mutate,
    filter_visible_models,
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
    # Saved models (EPIC-004)
    "SAVED_MODELS_SCHEMA_VERSION",
    "ModelStore",
    "ModelStoreError",
    "ModelVersion",
    "SavedModel",
    "filter_visible_models",
    # Ownership authorisation (EPIC-005)
    "ModelAuthorizationError",
    "can_mutate",
    "authorize_mutation",
]
