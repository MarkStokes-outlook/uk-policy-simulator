"""Scenario presets for the UK Policy Sandbox (EPIC-002).

A *scenario* is a named, reusable bundle of engine inputs: a value for every
revenue lever, every investment lever and every feedback assumption. Presets let
a user start from a coherent policy position rather than blank sliders.

This module is intentionally free of Streamlit (and only depends on the model
package + PyYAML) so it can be unit-tested and used by any future API. It maps
cleanly onto :func:`model.fiscal_model.compute_fiscal` inputs:

- ``revenue_levers`` / ``investment_levers`` are ``{key: £bn/year}`` mappings.
- ``assumptions`` is a fully-validated :class:`FeedbackAssumptions`.

Scenario *values are illustrative and human-curated*. They are reference points
for exploration, not endorsements or predictions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .fiscal_model import AssumptionError, FeedbackAssumptions

# Bump when the on-disk scenario schema changes shape. The loader refuses files
# whose ``schema_version`` it does not understand, so presets and code can never
# drift silently.
SCENARIO_SCHEMA_VERSION = 1

# Canonical lever keys. scenarios.yaml, the loader and the UI all agree on these
# identifiers; a preset MUST set exactly this set (no missing, no unknown keys).
REVENUE_LEVER_KEYS: tuple[str, ...] = (
    "income_tax_ni",
    "wealth_property",
    "passive_income",
    "corporate",
    "carbon_windfall",
    "anti_avoidance",
)

INVESTMENT_LEVER_KEYS: tuple[str, ...] = (
    "childcare",
    "social_care",
    "housing",
    "nhs_prevention",
    "education_training",
    "welfare_floor",
    "transport_energy",
)

# Assumption keys, in the order FeedbackAssumptions expects them.
ASSUMPTION_KEYS: tuple[str, ...] = (
    "years",
    "growth_baseline",
    "revenue_feedback_rate",
    "cost_reduction_rate",
    "lag_years",
    "implementation_quality",
    "optimism_penalty",
)


class ScenarioError(Exception):
    """Raised when a scenario file or scenario definition is invalid.

    Messages are written to be actionable in the UI and in CI logs: they name
    the offending scenario and field wherever possible.
    """


@dataclass(frozen=True)
class Scenario:
    """A validated, ready-to-run policy preset.

    ``revenue_levers`` and ``investment_levers`` are complete mappings keyed by
    :data:`REVENUE_LEVER_KEYS` / :data:`INVESTMENT_LEVER_KEYS`. ``assumptions``
    is already range-validated by :class:`FeedbackAssumptions`.
    """

    id: str
    name: str
    summary: str
    revenue_levers: dict[str, float]
    investment_levers: dict[str, float]
    assumptions: FeedbackAssumptions


def _require(condition: bool, message: str) -> None:
    """Raise :class:`ScenarioError` with ``message`` unless ``condition`` holds."""
    if not condition:
        raise ScenarioError(message)


def _coerce_levers(
    raw: Any, expected_keys: tuple[str, ...], kind: str, scenario_id: str
) -> dict[str, float]:
    """Validate a lever block against ``expected_keys`` and return finite floats."""
    _require(
        isinstance(raw, dict),
        f"Scenario '{scenario_id}': '{kind}_levers' must be a mapping.",
    )
    keys = set(raw)
    expected = set(expected_keys)
    missing = sorted(expected - keys)
    unknown = sorted(keys - expected)
    _require(
        not missing,
        f"Scenario '{scenario_id}': {kind} levers missing: {', '.join(missing)}.",
    )
    _require(
        not unknown,
        f"Scenario '{scenario_id}': unknown {kind} levers: {', '.join(unknown)}.",
    )

    levers: dict[str, float] = {}
    for key in expected_keys:
        value = raw[key]
        _require(
            isinstance(value, (int, float)) and not isinstance(value, bool),
            f"Scenario '{scenario_id}': {kind} lever '{key}' must be numeric "
            f"(got {value!r}).",
        )
        _require(
            math.isfinite(value),
            f"Scenario '{scenario_id}': {kind} lever '{key}' must be finite "
            f"(got {value}).",
        )
        levers[key] = float(value)
    return levers


def _coerce_assumptions(raw: Any, scenario_id: str) -> FeedbackAssumptions:
    """Validate the assumptions block and build a :class:`FeedbackAssumptions`."""
    _require(
        isinstance(raw, dict),
        f"Scenario '{scenario_id}': 'assumptions' must be a mapping.",
    )
    keys = set(raw)
    expected = set(ASSUMPTION_KEYS)
    missing = sorted(expected - keys)
    unknown = sorted(keys - expected)
    _require(
        not missing,
        f"Scenario '{scenario_id}': assumptions missing: {', '.join(missing)}.",
    )
    _require(
        not unknown,
        f"Scenario '{scenario_id}': unknown assumptions: {', '.join(unknown)}.",
    )

    # years / lag_years are integers; everything else is a finite fraction. We
    # check finiteness here so a nan/inf fails with scenario context rather than
    # surfacing as an opaque range error from FeedbackAssumptions.
    for key in ("growth_baseline", "revenue_feedback_rate", "cost_reduction_rate",
                "implementation_quality", "optimism_penalty"):
        value = raw[key]
        _require(
            isinstance(value, (int, float)) and not isinstance(value, bool),
            f"Scenario '{scenario_id}': assumption '{key}' must be numeric "
            f"(got {value!r}).",
        )
        _require(
            math.isfinite(value),
            f"Scenario '{scenario_id}': assumption '{key}' must be finite "
            f"(got {value}).",
        )
    for key in ("years", "lag_years"):
        _require(
            isinstance(raw[key], int) and not isinstance(raw[key], bool),
            f"Scenario '{scenario_id}': assumption '{key}' must be an integer "
            f"(got {raw[key]!r}).",
        )

    try:
        return FeedbackAssumptions(
            years=raw["years"],
            growth_baseline=float(raw["growth_baseline"]),
            revenue_feedback_rate=float(raw["revenue_feedback_rate"]),
            cost_reduction_rate=float(raw["cost_reduction_rate"]),
            lag_years=raw["lag_years"],
            implementation_quality=float(raw["implementation_quality"]),
            optimism_penalty=float(raw["optimism_penalty"]),
        )
    except AssumptionError as exc:
        # Re-wrap with scenario context so the UI/CI knows which preset is bad.
        raise ScenarioError(
            f"Scenario '{scenario_id}': invalid assumption — {exc}"
        ) from exc


def _coerce_scenario(raw: Any) -> Scenario:
    """Validate a single scenario mapping and return a :class:`Scenario`."""
    _require(isinstance(raw, dict), "Each scenario must be a mapping.")
    for field in ("id", "name", "summary"):
        value = raw.get(field)
        _require(
            isinstance(value, str) and value.strip() != "",
            f"Scenario is missing a non-empty '{field}' string.",
        )
    scenario_id = raw["id"]

    return Scenario(
        id=scenario_id,
        name=raw["name"],
        summary=raw["summary"].strip(),
        revenue_levers=_coerce_levers(
            raw.get("revenue_levers"), REVENUE_LEVER_KEYS, "revenue", scenario_id
        ),
        investment_levers=_coerce_levers(
            raw.get("investment_levers"), INVESTMENT_LEVER_KEYS, "investment", scenario_id
        ),
        assumptions=_coerce_assumptions(raw.get("assumptions"), scenario_id),
    )


def load_scenarios(path) -> dict[str, Scenario]:
    """Load, validate and return all scenarios keyed by id (insertion order).

    Any problem — missing file, malformed YAML, unsupported schema version,
    missing/extra levers, out-of-range assumptions, duplicate ids — raises
    :class:`ScenarioError` with a human-readable, actionable message.
    """
    p = Path(path)
    if not p.exists():
        raise ScenarioError(f"Scenario file not found: {p}")

    try:
        with p.open(encoding="utf-8") as f:
            doc = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ScenarioError(f"Could not parse scenario file '{p}': {exc}") from exc
    except OSError as exc:
        raise ScenarioError(f"Could not read scenario file '{p}': {exc}") from exc

    _require(isinstance(doc, dict), f"Scenario file '{p}' must be a YAML mapping.")

    version = doc.get("schema_version")
    _require(
        version == SCENARIO_SCHEMA_VERSION,
        f"Unsupported scenario schema_version {version!r} in '{p}' "
        f"(this build supports {SCENARIO_SCHEMA_VERSION}).",
    )

    raw_scenarios = doc.get("scenarios")
    _require(
        isinstance(raw_scenarios, list) and len(raw_scenarios) > 0,
        f"Scenario file '{p}' must contain a non-empty 'scenarios' list.",
    )

    scenarios: dict[str, Scenario] = {}
    for raw in raw_scenarios:
        scenario = _coerce_scenario(raw)
        _require(
            scenario.id not in scenarios,
            f"Duplicate scenario id '{scenario.id}' in '{p}'.",
        )
        scenarios[scenario.id] = scenario

    return scenarios
