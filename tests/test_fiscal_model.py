"""Deterministic unit tests for the fiscal model.

Run with: pytest
"""

import math
from pathlib import Path

import pytest

from model.fiscal_model import (
    AssumptionError,
    Baseline,
    BaselineError,
    FeedbackAssumptions,
    LeverError,
    compute_fiscal,
    load_baseline,
)

BASELINE_CSV = Path(__file__).resolve().parent.parent / "baseline.csv"


# Assumptions with all feedback switched OFF, for tests that only exercise the
# static (non-dynamic) calculations.
NO_FEEDBACK = FeedbackAssumptions(
    years=5,
    growth_baseline=0.0,
    revenue_feedback_rate=0.0,
    cost_reduction_rate=0.0,
    lag_years=0,
    implementation_quality=1.0,
    optimism_penalty=0.0,
)


def test_baseline_deficit_calculation():
    baseline = Baseline(receipts=1232.0, spending=1368.0, gdp=3054.0)
    assert baseline.deficit == 136.0


def test_load_baseline_reads_canonical_file():
    baseline = load_baseline(BASELINE_CSV)
    assert baseline.receipts == 1232.0
    assert baseline.spending == 1368.0
    assert baseline.gdp == 3054.0
    assert baseline.deficit == 136.0


def test_load_baseline_missing_file_raises():
    with pytest.raises(BaselineError, match="not found"):
        load_baseline("does-not-exist.csv")


def test_load_baseline_missing_metric_raises(tmp_path):
    bad = tmp_path / "baseline.csv"
    bad.write_text(
        "metric,value_bn,notes\n"
        "Total receipts,1232,x\n"
        "Total spending,1368,x\n",  # Implied GDP deliberately missing
        encoding="utf-8",
    )
    with pytest.raises(BaselineError, match="Implied GDP"):
        load_baseline(bad)


def test_load_baseline_non_numeric_raises(tmp_path):
    bad = tmp_path / "baseline.csv"
    bad.write_text(
        "metric,value_bn,notes\n"
        "Total receipts,not-a-number,x\n"
        "Total spending,1368,x\n"
        "Implied GDP,3054,x\n",
        encoding="utf-8",
    )
    with pytest.raises(BaselineError, match="Non-numeric"):
        load_baseline(bad)


def test_static_revenue_spending_deficit():
    baseline = Baseline(receipts=1000.0, spending=1200.0, gdp=5000.0)
    revenue_levers = {"a": 50.0, "b": 30.0}      # sums to 80
    investment_levers = {"x": 20.0}              # sums to 20

    result = compute_fiscal(baseline, revenue_levers, investment_levers, NO_FEEDBACK)

    assert result.revenue_static == 80.0
    assert result.investment_static == 20.0
    assert result.static_receipts == 1080.0
    assert result.static_spending == 1220.0
    assert result.static_deficit == 140.0


def test_feedback_lag_behaviour():
    # quality_adjusted_return = 1.0; investment = 100; revenue rate = 0.5.
    baseline = Baseline(receipts=0.0, spending=0.0, gdp=1000.0)
    assumptions = FeedbackAssumptions(
        years=4,
        growth_baseline=0.0,
        revenue_feedback_rate=0.5,
        cost_reduction_rate=0.0,
        lag_years=2,
        implementation_quality=1.0,
        optimism_penalty=0.0,
    )

    result = compute_fiscal(baseline, {}, {"build": 100.0}, assumptions)
    feedback = [row["Revenue feedback (£bn)"] for row in result.projection]

    # No feedback during the lag period (years 0, 1, 2).
    assert feedback[0] == 0.0
    assert feedback[1] == 0.0
    assert feedback[2] == 0.0
    # Then a linear ramp: year 3 = half, year 4 = full.
    assert feedback[3] == pytest.approx(25.0)   # 100 * 0.5 * 1.0 * 0.5
    assert feedback[4] == pytest.approx(50.0)   # 100 * 0.5 * 1.0 * 1.0


def test_deficit_percentage_of_gdp():
    baseline = Baseline(receipts=400.0, spending=500.0, gdp=1000.0)
    result = compute_fiscal(baseline, {}, {}, NO_FEEDBACK)

    year0 = result.projection[0]
    assert year0["Deficit (£bn)"] == 100.0
    assert year0["Deficit % GDP"] == pytest.approx(10.0)


def test_default_scenario_does_not_regress():
    """Lock in the output of the app's default slider positions."""
    baseline = Baseline(receipts=1232.0, spending=1368.0, gdp=3054.0)

    revenue_levers = {
        "income_tax_ni_reform": 0.0,
        "wealth_tax_reform": 35.0,
        "passive_income_reform": 20.0,
        "corporate_tax_reform": 10.0,
        "carbon_resource_tax": 15.0,
        "anti_avoidance": 8.0,
    }
    investment_levers = {
        "childcare": 20.0,
        "social_care": 20.0,
        "housing": 35.0,
        "nhs_prevention": 15.0,
        "education_training": 15.0,
        "welfare_floor": 15.0,
        "transport_energy": 25.0,
    }
    assumptions = FeedbackAssumptions(
        years=15,
        growth_baseline=0.035,
        revenue_feedback_rate=0.35,
        cost_reduction_rate=0.20,
        lag_years=3,
        implementation_quality=0.70,
        optimism_penalty=0.15,
    )

    result = compute_fiscal(baseline, revenue_levers, investment_levers, assumptions)

    # Static figures.
    assert result.revenue_static == 88.0
    assert result.investment_static == 145.0
    assert result.static_receipts == 1320.0
    assert result.static_spending == 1513.0
    assert result.static_deficit == 193.0

    # Projection shape: years 0..15 inclusive.
    assert len(result.projection) == 16

    # Final-year dynamic figures (lag fully ramped at year 15).
    # quality_adjusted_return = 0.70 * (1 - 0.15) = 0.595
    last = result.projection[-1]
    assert last["Revenue feedback (£bn)"] == pytest.approx(30.19625)  # 145*0.35*0.595
    assert last["Cost reduction (£bn)"] == pytest.approx(17.255)      # 145*0.20*0.595
    assert last["Deficit (£bn)"] == pytest.approx(145.54875)
    assert last["GDP (£bn)"] == pytest.approx(3054.0 * (1.035 ** 15))


def test_compute_is_idempotent():
    """Identical inputs always produce identical outputs (US-005 AC4)."""
    baseline = Baseline(receipts=1232.0, spending=1368.0, gdp=3054.0)
    assumptions = FeedbackAssumptions(
        years=10, growth_baseline=0.03, revenue_feedback_rate=0.4,
        cost_reduction_rate=0.25, lag_years=2,
        implementation_quality=0.8, optimism_penalty=0.1,
    )
    levers = {"a": 12.0, "b": -3.0}
    first = compute_fiscal(baseline, levers, {"x": 40.0}, assumptions)
    second = compute_fiscal(baseline, levers, {"x": 40.0}, assumptions)
    assert first == second


# --- Input validation (US-007 AC3) ---------------------------------------

def _assumptions(**overrides):
    base = dict(
        years=15, growth_baseline=0.035, revenue_feedback_rate=0.35,
        cost_reduction_rate=0.20, lag_years=3,
        implementation_quality=0.70, optimism_penalty=0.15,
    )
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "overrides, match",
    [
        ({"years": 0}, "years"),
        ({"lag_years": -1}, "lag_years"),
        ({"growth_baseline": -1.0}, "growth_baseline"),   # 1 + g would be 0
        ({"growth_baseline": 1.5}, "growth_baseline"),
        ({"revenue_feedback_rate": 1.5}, "revenue_feedback_rate"),
        ({"revenue_feedback_rate": -0.1}, "revenue_feedback_rate"),
        ({"cost_reduction_rate": 2.0}, "cost_reduction_rate"),
        ({"implementation_quality": 4.0}, "implementation_quality"),
        ({"optimism_penalty": 2.0}, "optimism_penalty"),
        ({"optimism_penalty": -0.5}, "optimism_penalty"),
    ],
)
def test_assumptions_reject_out_of_range(overrides, match):
    with pytest.raises(AssumptionError, match=match):
        FeedbackAssumptions(**_assumptions(**overrides))


def test_assumptions_accept_valid_bounds():
    # Boundary values are valid: rates/quality/penalty at 0 and 1, growth at +1.
    FeedbackAssumptions(**_assumptions(
        revenue_feedback_rate=0.0, cost_reduction_rate=1.0,
        implementation_quality=1.0, optimism_penalty=0.0,
        growth_baseline=1.0, lag_years=0, years=1,
    ))


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"receipts": 1000.0, "spending": 1200.0, "gdp": 0.0}, "GDP"),
        ({"receipts": 1000.0, "spending": 1200.0, "gdp": -5.0}, "GDP"),
        ({"receipts": -1.0, "spending": 1200.0, "gdp": 3000.0}, "receipts"),
        ({"receipts": 1000.0, "spending": -1.0, "gdp": 3000.0}, "spending"),
    ],
)
def test_baseline_rejects_invalid_values(kwargs, match):
    with pytest.raises(BaselineError, match=match):
        Baseline(**kwargs)


# --- Non-finite input validation (Codex review, v0.2) --------------------

@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", ["receipts", "spending", "gdp"])
def test_baseline_rejects_non_finite(field, bad):
    kwargs = {"receipts": 1000.0, "spending": 1200.0, "gdp": 3000.0}
    kwargs[field] = bad
    with pytest.raises(BaselineError, match="finite"):
        Baseline(**kwargs)


@pytest.mark.parametrize("token", ["inf", "-inf", "nan", "Infinity", "NaN"])
def test_load_baseline_non_finite_raises(tmp_path, token):
    bad = tmp_path / "baseline.csv"
    bad.write_text(
        "metric,value_bn,notes\n"
        f"Total receipts,{token},x\n"
        "Total spending,1368,x\n"
        "Implied GDP,3054,x\n",
        encoding="utf-8",
    )
    with pytest.raises(BaselineError, match="Non-finite"):
        load_baseline(bad)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_compute_fiscal_rejects_non_finite_revenue_lever(bad):
    baseline = Baseline(receipts=1000.0, spending=1200.0, gdp=5000.0)
    with pytest.raises(LeverError, match="finite"):
        compute_fiscal(baseline, {"bad": bad}, {}, NO_FEEDBACK)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_compute_fiscal_rejects_non_finite_investment_lever(bad):
    baseline = Baseline(receipts=1000.0, spending=1200.0, gdp=5000.0)
    with pytest.raises(LeverError, match="finite"):
        compute_fiscal(baseline, {}, {"bad": bad}, NO_FEEDBACK)


def test_compute_fiscal_rejects_non_numeric_lever():
    baseline = Baseline(receipts=1000.0, spending=1200.0, gdp=5000.0)
    with pytest.raises(LeverError, match="numeric"):
        compute_fiscal(baseline, {"bad": "lots"}, {}, NO_FEEDBACK)  # type: ignore[dict-item]


def test_compute_fiscal_output_is_all_finite():
    """A valid run must never emit a non-finite figure into the projection/CSV."""
    baseline = Baseline(receipts=1232.0, spending=1368.0, gdp=3054.0)
    result = compute_fiscal(
        baseline, {"a": 50.0}, {"x": 40.0}, NO_FEEDBACK
    )
    for row in result.projection:
        for key, value in row.items():
            assert math.isfinite(value), f"non-finite {key}={value}"
