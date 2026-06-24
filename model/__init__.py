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
]
