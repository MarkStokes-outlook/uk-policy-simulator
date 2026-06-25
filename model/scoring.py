"""Deterministic policy scoring for the UK Policy Sandbox (EPIC-003).

This module turns a scenario's engine inputs and fiscal result into a small set
of transparent, **deterministic** category scores (0-100) plus a single weighted
overall score. There is no AI and no randomness anywhere in this path: identical
inputs always yield identical scores.

Design principles (see ``docs/scoring.md`` and the roadmap's trust framework):

- **No black-box scoring.** Every outcome category is driven by a *published,
  signed contribution matrix* (:data:`CONTRIBUTIONS`) — points per £bn of each
  lever — so any score can be explained lever by lever.
- **Deterministic scores, subjective weights.** The category scores are
  deterministic, transparent and directionally defined ("how much does this
  advance the named dimension?"), but the contribution coefficients and
  complexity penalties are themselves human-curated model assumptions — not
  calibrated measurement. How much each dimension *matters* is never baked in
  here — it lives in configurable :class:`WeightingProfile` data
  (``weighting_profiles.yaml``). The platform deliberately ships several
  profiles and treats none as correct.
- **Uniform direction.** Every category is defined so that **100 is the more
  favourable end of that axis**. For Implementation Complexity that means
  100 = easy to deliver (low complexity), 0 = very complex.

These are transparent heuristics for exploration, not calibrated econometric
estimates. Fiscal Sustainability is the one category taken straight from the
engine (final-year deficit as a share of GDP); the rest are illustrative.

This module is Streamlit-free and depends only on the model package + PyYAML,
so it is independently unit-tested and reusable by any future API.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .fiscal_model import Baseline, FiscalResult
from .scenarios import INVESTMENT_LEVER_KEYS, REVENUE_LEVER_KEYS

# Bump when the on-disk weighting-profile schema changes shape. The loader
# refuses files whose ``schema_version`` it does not understand.
WEIGHTING_SCHEMA_VERSION = 1

# Canonical category keys, in display order. The contribution matrix, weighting
# profiles, the UI and the tests all agree on exactly this set.
SCORE_CATEGORIES: tuple[str, ...] = (
    "fiscal_sustainability",
    "economic_growth",
    "poverty_reduction",
    "housing_affordability",
    "nhs_demand_impact",
    "income_equality",
    "implementation_complexity",
)

CATEGORY_LABELS: dict[str, str] = {
    "fiscal_sustainability": "Fiscal Sustainability",
    "economic_growth": "Economic Growth",
    "poverty_reduction": "Poverty Reduction",
    "housing_affordability": "Housing Affordability",
    "nhs_demand_impact": "NHS Demand Impact",
    "income_equality": "Income Equality",
    "implementation_complexity": "Implementation Complexity",
}

# What "100" means on each axis, surfaced in the UI so the score direction is
# never ambiguous (especially for Implementation Complexity).
CATEGORY_DIRECTIONS: dict[str, str] = {
    "fiscal_sustainability": "100 = lower deficit as a share of GDP (more sustainable).",
    "economic_growth": "100 = stronger modelled growth/capacity effect.",
    "poverty_reduction": "100 = larger modelled reduction in poverty.",
    "housing_affordability": "100 = larger modelled improvement in housing affordability.",
    "nhs_demand_impact": "100 = larger modelled reduction in avoidable NHS demand.",
    "income_equality": "100 = more progressive net effect on income distribution.",
    "implementation_complexity": "100 = easy to deliver (low complexity); 0 = very complex.",
}

# The five "outcome" categories scored from the contribution matrix below. The
# remaining two are computed directly: Fiscal Sustainability from the engine's
# deficit/GDP, Implementation Complexity from the size/breadth of the change.
_MATRIX_CATEGORIES: tuple[str, ...] = (
    "economic_growth",
    "poverty_reduction",
    "housing_affordability",
    "nhs_demand_impact",
    "income_equality",
)

# Neutral midpoint for matrix-scored categories: a do-nothing scenario sits at
# 50 on each outcome axis, and levers move it up or down from there.
_OUTCOME_MIDPOINT = 50.0

# Published, signed contribution coefficients: score points per £bn/year of each
# lever, per outcome category. Positive advances the named dimension, negative
# works against it. These are illustrative, human-curated directional links —
# transparent on purpose so users can audit and challenge every one of them.
# Keys are the canonical lever keys from model.scenarios.
CONTRIBUTIONS: dict[str, dict[str, float]] = {
    "economic_growth": {
        "education_training": 0.45,
        "transport_energy": 0.40,
        "childcare": 0.35,
        "housing": 0.20,
        "nhs_prevention": 0.10,
        "social_care": 0.05,
        "welfare_floor": 0.05,
        "income_tax_ni": -0.15,
        "corporate": -0.20,
        "passive_income": -0.10,
        "wealth_property": -0.08,
        "carbon_windfall": -0.05,
        "anti_avoidance": 0.0,
    },
    "poverty_reduction": {
        "welfare_floor": 0.55,
        "childcare": 0.35,
        "housing": 0.25,
        "education_training": 0.15,
        "social_care": 0.15,
        "nhs_prevention": 0.10,
        "transport_energy": 0.05,
        "income_tax_ni": -0.05,
    },
    "housing_affordability": {
        "housing": 0.70,
        "wealth_property": 0.20,
        "transport_energy": 0.15,
    },
    "nhs_demand_impact": {
        "nhs_prevention": 0.55,
        "social_care": 0.45,
        "housing": 0.10,
        "childcare": 0.05,
        "education_training": 0.05,
    },
    "income_equality": {
        "welfare_floor": 0.45,
        "wealth_property": 0.30,
        "passive_income": 0.25,
        "childcare": 0.20,
        "income_tax_ni": 0.15,
        "corporate": 0.15,
        "anti_avoidance": 0.15,
        "education_training": 0.15,
        "social_care": 0.10,
        "housing": 0.10,
        "transport_energy": 0.05,
        "carbon_windfall": -0.05,
    },
}

# Fiscal Sustainability maps the engine's final-year deficit/GDP onto 0-100.
# A small surplus is the "fully sustainable" end; a large deficit is the "0" end.
FISCAL_SUSTAINABLE_PCT = -3.0   # deficit % GDP scoring 100 (i.e. a 3% surplus)
FISCAL_UNSUSTAINABLE_PCT = 9.0  # deficit % GDP scoring 0

# Implementation Complexity: start from 100 (do nothing is trivial) and subtract
# for the gross size of the change and the number of distinct active levers.
COMPLEXITY_PER_BN = 0.25         # points removed per £bn of gross |change|
COMPLEXITY_PER_ACTIVE_LEVER = 2.0  # points removed per lever moved off zero

_ALL_LEVER_KEYS: tuple[str, ...] = REVENUE_LEVER_KEYS + INVESTMENT_LEVER_KEYS


class ScoringError(Exception):
    """Raised when a weighting-profile file or definition is invalid.

    Messages name the offending profile/field where possible so they are
    actionable in the UI and in CI logs.
    """


@dataclass(frozen=True)
class CategoryScore:
    """A single deterministic category score on a 0-100 scale.

    ``rationale`` is a short, human-readable explanation of what drove the
    score. ``basis`` carries the underlying machine-readable detail (per-lever
    contributions or the source metric) so the UI can show a full breakdown.
    """

    key: str
    label: str
    score: float
    direction: str
    rationale: str
    basis: dict[str, float]


@dataclass(frozen=True)
class WeightingProfile:
    """A configurable set of category weights.

    Weights are stored as supplied and normalised at apply time, so they may be
    given as any positive numbers (e.g. 1..5 importance ratings or fractions).
    No profile is treated as objectively correct — that is a product principle.
    """

    id: str
    name: str
    summary: str
    weights: dict[str, float]


@dataclass(frozen=True)
class ScoreCard:
    """The full result of scoring a scenario under a weighting profile."""

    categories: dict[str, CategoryScore]
    profile: WeightingProfile
    overall: float


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp ``value`` into the ``[lo, hi]`` range."""
    return max(lo, min(hi, value))


def _scale_inverse(value: float, best: float, worst: float) -> float:
    """Map ``value`` onto 0-100 where ``best`` -> 100 and ``worst`` -> 0.

    Used for "lower is better" metrics such as deficit/GDP. The result is
    clamped, so values beyond the reference band saturate at 0 or 100.
    """
    if worst == best:  # pragma: no cover - guarded by module constants
        return 50.0
    frac = (worst - value) / (worst - best)
    return _clamp(frac * 100.0)


def _active_levers(levers: Mapping[str, float]) -> int:
    """Count levers moved off zero (the engine's 'do nothing' position)."""
    return sum(1 for v in levers.values() if abs(v) > 1e-9)


def _outcome_score(category: str, levers: Mapping[str, float]) -> CategoryScore:
    """Score one matrix-driven outcome category from the contribution matrix."""
    coeffs = CONTRIBUTIONS[category]
    contributions: dict[str, float] = {}
    total = 0.0
    for key, value in levers.items():
        coeff = coeffs.get(key, 0.0)
        if coeff and abs(value) > 1e-9:
            delta = coeff * value
            contributions[key] = delta
            total += delta

    raw = _OUTCOME_MIDPOINT + total
    score = _clamp(raw)

    if contributions:
        top = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        drivers = ", ".join(f"{k} ({v:+.1f})" for k, v in top)
        rationale = (
            f"{total:+.1f} from neutral (50) on the published contribution matrix; "
            f"main drivers: {drivers}."
        )
    else:
        rationale = "No active levers contribute to this category; neutral (50)."

    return CategoryScore(
        key=category,
        label=CATEGORY_LABELS[category],
        score=score,
        direction=CATEGORY_DIRECTIONS[category],
        rationale=rationale,
        basis=contributions,
    )


def _fiscal_sustainability_score(result: FiscalResult) -> CategoryScore:
    """Score fiscal sustainability from the engine's final-year deficit/GDP."""
    final = result.projection[-1]
    deficit_pct = float(final["Deficit % GDP"])
    score = _scale_inverse(
        deficit_pct, best=FISCAL_SUSTAINABLE_PCT, worst=FISCAL_UNSUSTAINABLE_PCT
    )
    rationale = (
        f"Final-year deficit is {deficit_pct:.1f}% of GDP "
        f"(scored on a band from {FISCAL_SUSTAINABLE_PCT:.0f}% = 100 to "
        f"{FISCAL_UNSUSTAINABLE_PCT:.0f}% = 0)."
    )
    return CategoryScore(
        key="fiscal_sustainability",
        label=CATEGORY_LABELS["fiscal_sustainability"],
        score=score,
        direction=CATEGORY_DIRECTIONS["fiscal_sustainability"],
        rationale=rationale,
        basis={"deficit_pct_gdp": deficit_pct},
    )


def _complexity_score(levers: Mapping[str, float]) -> CategoryScore:
    """Score deliverability: 100 = trivial, falling as the change grows/spreads."""
    gross = float(sum(abs(v) for v in levers.values()))
    active = _active_levers(levers)
    penalty = gross * COMPLEXITY_PER_BN + active * COMPLEXITY_PER_ACTIVE_LEVER
    score = _clamp(100.0 - penalty)
    rationale = (
        f"£{gross:,.0f}bn gross change across {active} active lever(s) "
        f"(−{gross * COMPLEXITY_PER_BN:.0f} for size, "
        f"−{active * COMPLEXITY_PER_ACTIVE_LEVER:.0f} for breadth)."
    )
    return CategoryScore(
        key="implementation_complexity",
        label=CATEGORY_LABELS["implementation_complexity"],
        score=score,
        direction=CATEGORY_DIRECTIONS["implementation_complexity"],
        rationale=rationale,
        basis={"gross_change_bn": gross, "active_levers": float(active)},
    )


def score_categories(
    baseline: Baseline,
    result: FiscalResult,
    revenue_levers: Mapping[str, float],
    investment_levers: Mapping[str, float],
) -> dict[str, CategoryScore]:
    """Compute all seven category scores for a scenario.

    Parameters
    ----------
    baseline:
        Canonical baseline (reserved for future ratio-based categories; kept in
        the signature so callers do not change when those land).
    result:
        The :class:`FiscalResult` from :func:`model.fiscal_model.compute_fiscal`
        for the same scenario — used for Fiscal Sustainability.
    revenue_levers, investment_levers:
        Lever values keyed by the *canonical* keys from ``model.scenarios``
        (e.g. ``"welfare_floor"``), in £bn/year. Unknown keys contribute nothing.

    Returns a dict keyed by :data:`SCORE_CATEGORIES`, in display order.
    """
    all_levers: dict[str, float] = {**dict(revenue_levers), **dict(investment_levers)}

    scores: dict[str, CategoryScore] = {}
    scores["fiscal_sustainability"] = _fiscal_sustainability_score(result)
    for category in _MATRIX_CATEGORIES:
        scores[category] = _outcome_score(category, all_levers)
    scores["implementation_complexity"] = _complexity_score(all_levers)

    # Return in canonical display order.
    return {key: scores[key] for key in SCORE_CATEGORIES}


def build_scorecard(
    categories: Mapping[str, CategoryScore], profile: WeightingProfile
) -> ScoreCard:
    """Combine category scores into a single weighted overall under ``profile``.

    Weights are normalised to sum to 1 across :data:`SCORE_CATEGORIES`; the
    overall is the resulting weighted average (still 0-100). A profile whose
    weights sum to zero is rejected as a :class:`ScoringError`.
    """
    missing = [c for c in SCORE_CATEGORIES if c not in categories]
    if missing:
        raise ScoringError(
            "Cannot build scorecard; missing category score(s): "
            + ", ".join(missing)
            + "."
        )

    # Validate the profile's weights through the same contract as the loader, so
    # a manually-constructed WeightingProfile cannot bypass validation. This
    # turns missing / unknown / non-numeric / non-finite / negative / zero-sum
    # weights into an actionable ScoringError instead of a raw KeyError or a
    # silently-accepted bad weight.
    weights = _coerce_weights(profile.weights, profile.id)

    total_weight = float(sum(weights[c] for c in SCORE_CATEGORIES))
    overall = sum(
        categories[c].score * weights[c] for c in SCORE_CATEGORIES
    ) / total_weight

    return ScoreCard(
        categories={c: categories[c] for c in SCORE_CATEGORIES},
        profile=profile,
        overall=_clamp(overall),
    )


# --- Weighting-profile loading (configurable, user-facing data) ----------

def _require(condition: bool, message: str) -> None:
    """Raise :class:`ScoringError` with ``message`` unless ``condition`` holds."""
    if not condition:
        raise ScoringError(message)


def _coerce_weights(raw: Any, profile_id: str) -> dict[str, float]:
    """Validate a weights block: every category present, positive and finite."""
    _require(
        isinstance(raw, dict),
        f"Weighting profile '{profile_id}': 'weights' must be a mapping.",
    )
    keys = set(raw)
    expected = set(SCORE_CATEGORIES)
    missing = sorted(expected - keys)
    unknown = sorted(keys - expected)
    _require(
        not missing,
        f"Weighting profile '{profile_id}': weights missing: {', '.join(missing)}.",
    )
    _require(
        not unknown,
        f"Weighting profile '{profile_id}': unknown weights: {', '.join(unknown)}.",
    )

    weights: dict[str, float] = {}
    for key in SCORE_CATEGORIES:
        value = raw[key]
        _require(
            isinstance(value, (int, float)) and not isinstance(value, bool),
            f"Weighting profile '{profile_id}': weight '{key}' must be numeric "
            f"(got {value!r}).",
        )
        _require(
            math.isfinite(value),
            f"Weighting profile '{profile_id}': weight '{key}' must be finite "
            f"(got {value}).",
        )
        _require(
            value >= 0,
            f"Weighting profile '{profile_id}': weight '{key}' must be >= 0 "
            f"(got {value}).",
        )
        weights[key] = float(value)

    _require(
        sum(weights.values()) > 0,
        f"Weighting profile '{profile_id}': weights must not all be zero.",
    )
    return weights


def _coerce_profile(raw: Any) -> WeightingProfile:
    """Validate a single weighting-profile mapping."""
    _require(isinstance(raw, dict), "Each weighting profile must be a mapping.")
    for field in ("id", "name", "summary"):
        value = raw.get(field)
        _require(
            isinstance(value, str) and value.strip() != "",
            f"Weighting profile is missing a non-empty '{field}' string.",
        )
    profile_id = raw["id"]
    return WeightingProfile(
        id=profile_id,
        name=raw["name"],
        summary=raw["summary"].strip(),
        weights=_coerce_weights(raw.get("weights"), profile_id),
    )


def load_weighting_profiles(path) -> dict[str, WeightingProfile]:
    """Load, validate and return all weighting profiles keyed by id.

    Any problem — missing file, malformed YAML, unsupported schema version,
    missing/extra/negative weights, duplicate ids — raises :class:`ScoringError`
    with a human-readable, actionable message.
    """
    p = Path(path)
    if not p.exists():
        raise ScoringError(f"Weighting profile file not found: {p}")

    try:
        with p.open(encoding="utf-8") as f:
            doc = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ScoringError(f"Could not parse weighting file '{p}': {exc}") from exc
    except OSError as exc:
        raise ScoringError(f"Could not read weighting file '{p}': {exc}") from exc

    _require(isinstance(doc, dict), f"Weighting file '{p}' must be a YAML mapping.")

    version = doc.get("schema_version")
    _require(
        version == WEIGHTING_SCHEMA_VERSION,
        f"Unsupported weighting schema_version {version!r} in '{p}' "
        f"(this build supports {WEIGHTING_SCHEMA_VERSION}).",
    )

    raw_profiles = doc.get("profiles")
    _require(
        isinstance(raw_profiles, list) and len(raw_profiles) > 0,
        f"Weighting file '{p}' must contain a non-empty 'profiles' list.",
    )

    profiles: dict[str, WeightingProfile] = {}
    for raw in raw_profiles:
        profile = _coerce_profile(raw)
        _require(
            profile.id not in profiles,
            f"Duplicate weighting profile id '{profile.id}' in '{p}'.",
        )
        profiles[profile.id] = profile

    return profiles
