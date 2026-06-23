"""Core fiscal calculations for the UK Policy Sandbox.

This module is intentionally free of Streamlit and (mostly) pandas so it can be
unit-tested in isolation. The Streamlit layer (``app.py``) is responsible only
for collecting control values and rendering the results returned here.

Feedback model (be honest about what this does):
- Feedback is modelled as an *annual* effect proportional to the *current
  annual investment level*, not as a cumulative capital stock.
- It is linearly ramped in after the configured ``lag_years``.
- It is therefore NOT lifecycle / capital-stock modelling.

TODO: replace the flat annual-investment feedback with cumulative
capital-stock / lifecycle modelling (depreciation, compounding returns on the
accumulated stock rather than the current-year flow).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

# Metric names that MUST be present in baseline.csv for the app to run.
REQUIRED_METRICS = ("Total receipts", "Total spending", "Implied GDP")


class BaselineError(Exception):
    """Raised when the baseline data file is missing or invalid."""


@dataclass(frozen=True)
class Baseline:
    """Canonical baseline fiscal values, all in £bn/year."""

    receipts: float
    spending: float
    gdp: float

    @property
    def deficit(self) -> float:
        """Baseline deficit = spending - receipts."""
        return self.spending - self.receipts


@dataclass(frozen=True)
class FeedbackAssumptions:
    """Dynamic feedback assumptions.

    Rates are expressed as fractions (e.g. 0.35 for 35%), NOT percentages.
    """

    years: int
    growth_baseline: float          # fractional nominal GDP growth, e.g. 0.035
    revenue_feedback_rate: float    # fraction of investment returned as receipts
    cost_reduction_rate: float      # fraction of investment returned as lower spend
    lag_years: int
    implementation_quality: float   # fraction, 0..1
    optimism_penalty: float         # fraction, 0..1


@dataclass(frozen=True)
class FiscalResult:
    """Result of a fiscal computation.

    ``projection`` is a list of per-year dicts (year 0 .. years inclusive).
    The Streamlit layer wraps this in a pandas DataFrame for display; keeping
    it as plain data here means the model has no hard pandas dependency.
    """

    revenue_static: float
    investment_static: float
    static_receipts: float
    static_spending: float
    static_deficit: float
    projection: list[dict]


def load_baseline(path) -> Baseline:
    """Load and validate the canonical baseline from a CSV file.

    The CSV must have ``metric`` and ``value_bn`` columns and must contain all
    of :data:`REQUIRED_METRICS`. Any problem raises :class:`BaselineError` with
    a human-readable message suitable for surfacing in the UI.
    """

    p = Path(path)
    if not p.exists():
        raise BaselineError(f"Baseline file not found: {p}")

    values: dict[str, float] = {}
    try:
        with p.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            if "metric" not in fieldnames or "value_bn" not in fieldnames:
                raise BaselineError(
                    "Baseline file must have 'metric' and 'value_bn' columns "
                    f"(found: {fieldnames})."
                )
            for row in reader:
                metric = (row.get("metric") or "").strip()
                raw = (row.get("value_bn") or "").strip()
                if not metric:
                    continue
                try:
                    values[metric] = float(raw)
                except ValueError as exc:
                    raise BaselineError(
                        f"Non-numeric value for metric '{metric}': {raw!r}."
                    ) from exc
    except BaselineError:
        raise
    except OSError as exc:
        raise BaselineError(f"Could not read baseline file '{p}': {exc}") from exc

    missing = [m for m in REQUIRED_METRICS if m not in values]
    if missing:
        raise BaselineError(
            "Baseline file is missing required metric(s): " + ", ".join(missing) + "."
        )

    return Baseline(
        receipts=values["Total receipts"],
        spending=values["Total spending"],
        gdp=values["Implied GDP"],
    )


def compute_fiscal(
    baseline: Baseline,
    revenue_levers: Mapping[str, float],
    investment_levers: Mapping[str, float],
    assumptions: FeedbackAssumptions,
) -> FiscalResult:
    """Compute static figures and the dynamic projection.

    Parameters
    ----------
    baseline:
        Canonical baseline fiscal values.
    revenue_levers:
        Mapping of lever name -> £bn revenue change (summed).
    investment_levers:
        Mapping of lever name -> £bn investment/spend change (summed).
    assumptions:
        Dynamic feedback assumptions (rates as fractions).
    """

    revenue_static = float(sum(revenue_levers.values()))
    investment_static = float(sum(investment_levers.values()))

    static_receipts = baseline.receipts + revenue_static
    static_spending = baseline.spending + investment_static
    static_deficit = static_spending - static_receipts

    # The "productive" investment that drives feedback is the new annual spend.
    investment_productive = investment_static
    quality_adjusted_return = assumptions.implementation_quality * (
        1 - assumptions.optimism_penalty
    )

    years = assumptions.years
    lag_years = assumptions.lag_years

    rows: list[dict] = []
    for year in range(0, years + 1):
        gdp = baseline.gdp * ((1 + assumptions.growth_baseline) ** year)

        # Feedback is zero until the lag elapses, then ramps linearly to 1.0.
        if year <= lag_years:
            lag_factor = 0.0
        else:
            lag_factor = min(1.0, (year - lag_years) / max(1, years - lag_years))

        annual_revenue_feedback = (
            investment_productive
            * assumptions.revenue_feedback_rate
            * quality_adjusted_return
            * lag_factor
        )
        annual_cost_reduction = (
            investment_productive
            * assumptions.cost_reduction_rate
            * quality_adjusted_return
            * lag_factor
        )

        receipts = static_receipts + annual_revenue_feedback
        spending = static_spending - annual_cost_reduction
        deficit = spending - receipts

        rows.append(
            {
                "Year": year,
                "GDP (£bn)": gdp,
                "Receipts (£bn)": receipts,
                "Spending (£bn)": spending,
                "Deficit (£bn)": deficit,
                "Deficit % GDP": deficit / gdp * 100,
                "Revenue feedback (£bn)": annual_revenue_feedback,
                "Cost reduction (£bn)": annual_cost_reduction,
            }
        )

    return FiscalResult(
        revenue_static=revenue_static,
        investment_static=investment_static,
        static_receipts=static_receipts,
        static_spending=static_spending,
        static_deficit=static_deficit,
        projection=rows,
    )
