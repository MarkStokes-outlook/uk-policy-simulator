"""Tests for scenario presets (EPIC-002).

Covers the loader (US-002), validation (US-003) and round-trip execution
(US-007). Run with: pytest
"""

import math
import textwrap
from pathlib import Path

import pytest

from model.fiscal_model import Baseline, compute_fiscal, load_baseline
from model.scenarios import (
    INVESTMENT_LEVER_KEYS,
    REVENUE_LEVER_KEYS,
    SCENARIO_SCHEMA_VERSION,
    Scenario,
    ScenarioError,
    load_scenarios,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_YAML = REPO_ROOT / "scenarios.yaml"
BASELINE_CSV = REPO_ROOT / "baseline.csv"

EXPECTED_IDS = {
    "baseline",
    "fairness_swap",
    "social_investment",
    "deficit_repair",
    "universal_basic_services",
    "ubi_experiment",
    "austerity_trap",
}


# --- Loading the canonical file ------------------------------------------

def test_canonical_file_loads_all_seven():
    scenarios = load_scenarios(SCENARIOS_YAML)
    assert set(scenarios) == EXPECTED_IDS
    assert len(scenarios) == 7


def test_loaded_scenarios_are_typed_and_complete():
    scenarios = load_scenarios(SCENARIOS_YAML)
    for scenario in scenarios.values():
        assert isinstance(scenario, Scenario)
        assert set(scenario.revenue_levers) == set(REVENUE_LEVER_KEYS)
        assert set(scenario.investment_levers) == set(INVESTMENT_LEVER_KEYS)
        # assumptions is a FeedbackAssumptions, already range-validated.
        assert scenario.summary  # non-empty, neutral framing lives in YAML
        assert scenario.name


def test_baseline_preset_is_all_zero_levers():
    scenarios = load_scenarios(SCENARIOS_YAML)
    baseline = scenarios["baseline"]
    assert all(v == 0 for v in baseline.revenue_levers.values())
    assert all(v == 0 for v in baseline.investment_levers.values())


# --- Round-trip execution (US-007) ---------------------------------------

@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_IDS))
def test_scenario_runs_and_produces_finite_output(scenario_id):
    scenarios = load_scenarios(SCENARIOS_YAML)
    baseline = load_baseline(BASELINE_CSV)
    scenario = scenarios[scenario_id]

    result = compute_fiscal(
        baseline,
        scenario.revenue_levers,
        scenario.investment_levers,
        scenario.assumptions,
    )

    # Shape: years 0..N inclusive.
    assert len(result.projection) == scenario.assumptions.years + 1
    # Every emitted figure must be finite.
    for row in result.projection:
        for key, value in row.items():
            assert math.isfinite(value), f"{scenario_id}: non-finite {key}={value}"


# --- Validation / error handling (US-002, US-003) ------------------------

def _write(tmp_path, body: str) -> Path:
    p = tmp_path / "scenarios.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


_VALID_LEVERS = textwrap.dedent(
    """\
        revenue_levers: {income_tax_ni: 0, wealth_property: 0, passive_income: 0,
          corporate: 0, carbon_windfall: 0, anti_avoidance: 0}
        investment_levers: {childcare: 0, social_care: 0, housing: 0,
          nhs_prevention: 0, education_training: 0, welfare_floor: 0,
          transport_energy: 0}
        assumptions: {years: 10, growth_baseline: 0.03, revenue_feedback_rate: 0.3,
          cost_reduction_rate: 0.2, lag_years: 2, implementation_quality: 0.7,
          optimism_penalty: 0.1}
    """
)


def test_missing_file_raises():
    with pytest.raises(ScenarioError, match="not found"):
        load_scenarios("does-not-exist.yaml")


def test_bad_yaml_raises(tmp_path):
    p = _write(tmp_path, "schema_version: 1\nscenarios: [unclosed\n")
    with pytest.raises(ScenarioError, match="parse"):
        load_scenarios(p)


def test_unsupported_schema_version_raises(tmp_path):
    p = _write(
        tmp_path,
        f"schema_version: {SCENARIO_SCHEMA_VERSION + 1}\n"
        "scenarios:\n"
        "  - id: x\n    name: X\n    summary: s\n" + textwrap.indent(_VALID_LEVERS, "    "),
    )
    with pytest.raises(ScenarioError, match="schema_version"):
        load_scenarios(p)


def test_empty_scenarios_list_raises(tmp_path):
    p = _write(tmp_path, "schema_version: 1\nscenarios: []\n")
    with pytest.raises(ScenarioError, match="non-empty"):
        load_scenarios(p)


def test_missing_lever_raises(tmp_path):
    p = _write(
        tmp_path,
        """\
        schema_version: 1
        scenarios:
          - id: x
            name: X
            summary: s
            revenue_levers: {income_tax_ni: 0}
            investment_levers: {childcare: 0, social_care: 0, housing: 0,
              nhs_prevention: 0, education_training: 0, welfare_floor: 0,
              transport_energy: 0}
            assumptions: {years: 10, growth_baseline: 0.03,
              revenue_feedback_rate: 0.3, cost_reduction_rate: 0.2, lag_years: 2,
              implementation_quality: 0.7, optimism_penalty: 0.1}
        """,
    )
    with pytest.raises(ScenarioError, match="revenue levers missing"):
        load_scenarios(p)


def test_unknown_lever_raises(tmp_path):
    body = _VALID_LEVERS.replace(
        "anti_avoidance: 0}", "anti_avoidance: 0, mystery_tax: 5}"
    )
    p = _write(
        tmp_path,
        "schema_version: 1\nscenarios:\n  - id: x\n    name: X\n    summary: s\n"
        + textwrap.indent(body, "    "),
    )
    with pytest.raises(ScenarioError, match="unknown revenue levers"):
        load_scenarios(p)


def test_non_finite_lever_raises(tmp_path):
    body = _VALID_LEVERS.replace("income_tax_ni: 0", "income_tax_ni: .inf")
    p = _write(
        tmp_path,
        "schema_version: 1\nscenarios:\n  - id: x\n    name: X\n    summary: s\n"
        + textwrap.indent(body, "    "),
    )
    with pytest.raises(ScenarioError, match="finite"):
        load_scenarios(p)


def test_out_of_range_assumption_raises(tmp_path):
    body = _VALID_LEVERS.replace("revenue_feedback_rate: 0.3", "revenue_feedback_rate: 1.5")
    p = _write(
        tmp_path,
        "schema_version: 1\nscenarios:\n  - id: x\n    name: X\n    summary: s\n"
        + textwrap.indent(body, "    "),
    )
    with pytest.raises(ScenarioError, match="revenue_feedback_rate"):
        load_scenarios(p)


def test_duplicate_id_raises(tmp_path):
    one = "  - id: dup\n    name: A\n    summary: s\n" + textwrap.indent(_VALID_LEVERS, "    ")
    two = "  - id: dup\n    name: B\n    summary: s\n" + textwrap.indent(_VALID_LEVERS, "    ")
    p = _write(tmp_path, "schema_version: 1\nscenarios:\n" + one + two)
    with pytest.raises(ScenarioError, match="Duplicate scenario id"):
        load_scenarios(p)


def test_missing_summary_raises(tmp_path):
    p = _write(
        tmp_path,
        "schema_version: 1\nscenarios:\n  - id: x\n    name: X\n"
        + textwrap.indent(_VALID_LEVERS, "    "),
    )
    with pytest.raises(ScenarioError, match="summary"):
        load_scenarios(p)
