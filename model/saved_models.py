"""Persistent saved policy models for the UK Policy Sandbox (EPIC-004 / v1.0).

A *saved model* is a user-created, named bundle of engine inputs (every revenue
lever, every investment lever and the feedback assumptions) that persists across
sessions, together with a **version history**: each update appends a new version
rather than overwriting, so a user can see how a proposal evolved.

This module is intentionally free of Streamlit. It persists to a single JSON
file with a versioned schema and is independently unit-tested. The store is the
v1.0 building block for "persistent policy proposals"; multi-user identity and
sharing come later in the roadmap and are deliberately out of scope here.

Determinism / testability:
- All timestamps come from an injectable ``now`` callable (defaulting to UTC
  wall-clock), so tests can pin time and assert exact serialisation.
- Model ids are human-readable slugs derived from the name, with a numeric
  suffix on collision — no random uuids — so a given sequence of operations is
  reproducible.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .fiscal_model import AssumptionError, FeedbackAssumptions
from .scenarios import (
    ASSUMPTION_KEYS,
    INVESTMENT_LEVER_KEYS,
    REVENUE_LEVER_KEYS,
)

# Bump when the on-disk saved-models schema changes shape. The store refuses
# files whose ``schema_version`` it does not understand.
SAVED_MODELS_SCHEMA_VERSION = 1


class ModelStoreError(Exception):
    """Raised when the saved-models store or a model definition is invalid.

    Messages are written to be actionable in the UI and CI: they name the
    offending model/field wherever possible.
    """


@dataclass(frozen=True)
class ModelVersion:
    """One immutable snapshot of a saved model's engine inputs.

    ``revenue_levers`` / ``investment_levers`` are complete mappings keyed by the
    canonical lever keys; ``assumptions`` is a range-validated
    :class:`FeedbackAssumptions`.
    """

    version: int
    saved_at: str
    note: str
    revenue_levers: dict[str, float]
    investment_levers: dict[str, float]
    assumptions: FeedbackAssumptions


@dataclass(frozen=True)
class SavedModel:
    """A named, persistent policy model with full version history.

    ``versions`` is ordered oldest-first; :attr:`current` is the latest.
    """

    id: str
    name: str
    created_at: str
    updated_at: str
    versions: tuple[ModelVersion, ...]

    @property
    def current(self) -> ModelVersion:
        """The most recent version (the live state of this model)."""
        return self.versions[-1]


def _require(condition: bool, message: str) -> None:
    """Raise :class:`ModelStoreError` with ``message`` unless ``condition`` holds."""
    if not condition:
        raise ModelStoreError(message)


def _slugify(name: str) -> str:
    """Turn a model name into a filesystem/url-friendly id stem."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "model"


def _validate_levers(
    raw: Mapping[str, float], expected_keys: tuple[str, ...], kind: str, model_id: str
) -> dict[str, float]:
    """Validate a lever block against ``expected_keys`` and return finite floats."""
    _require(
        isinstance(raw, Mapping),
        f"Model '{model_id}': '{kind}_levers' must be a mapping.",
    )
    keys = set(raw)
    expected = set(expected_keys)
    missing = sorted(expected - keys)
    unknown = sorted(keys - expected)
    _require(not missing, f"Model '{model_id}': {kind} levers missing: {', '.join(missing)}.")
    _require(not unknown, f"Model '{model_id}': unknown {kind} levers: {', '.join(unknown)}.")

    levers: dict[str, float] = {}
    for key in expected_keys:
        value = raw[key]
        _require(
            isinstance(value, (int, float)) and not isinstance(value, bool),
            f"Model '{model_id}': {kind} lever '{key}' must be numeric (got {value!r}).",
        )
        _require(
            math.isfinite(value),
            f"Model '{model_id}': {kind} lever '{key}' must be finite (got {value}).",
        )
        levers[key] = float(value)
    return levers


def _assumptions_to_dict(assumptions: FeedbackAssumptions) -> dict[str, Any]:
    """Serialise assumptions to a plain dict keyed by :data:`ASSUMPTION_KEYS`."""
    return {key: getattr(assumptions, key) for key in ASSUMPTION_KEYS}


def _assumptions_from_dict(raw: Any, model_id: str) -> FeedbackAssumptions:
    """Validate an assumptions block and build a :class:`FeedbackAssumptions`."""
    _require(isinstance(raw, dict), f"Model '{model_id}': 'assumptions' must be a mapping.")
    missing = sorted(set(ASSUMPTION_KEYS) - set(raw))
    unknown = sorted(set(raw) - set(ASSUMPTION_KEYS))
    _require(not missing, f"Model '{model_id}': assumptions missing: {', '.join(missing)}.")
    _require(not unknown, f"Model '{model_id}': unknown assumptions: {', '.join(unknown)}.")
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
    except (AssumptionError, TypeError, ValueError) as exc:
        raise ModelStoreError(f"Model '{model_id}': invalid assumptions — {exc}") from exc


def _version_to_dict(v: ModelVersion) -> dict[str, Any]:
    return {
        "version": v.version,
        "saved_at": v.saved_at,
        "note": v.note,
        "revenue_levers": dict(v.revenue_levers),
        "investment_levers": dict(v.investment_levers),
        "assumptions": _assumptions_to_dict(v.assumptions),
    }


def _version_from_dict(raw: Any, model_id: str) -> ModelVersion:
    _require(isinstance(raw, dict), f"Model '{model_id}': each version must be a mapping.")
    version = raw.get("version")
    _require(
        isinstance(version, int) and not isinstance(version, bool) and version >= 1,
        f"Model '{model_id}': version number must be a positive integer (got {version!r}).",
    )
    saved_at = raw.get("saved_at")
    _require(
        isinstance(saved_at, str) and saved_at != "",
        f"Model '{model_id}': version {version} missing 'saved_at'.",
    )
    note = raw.get("note", "")
    _require(isinstance(note, str), f"Model '{model_id}': version {version} 'note' must be a string.")
    return ModelVersion(
        version=version,
        saved_at=saved_at,
        note=note,
        revenue_levers=_validate_levers(
            raw.get("revenue_levers", {}), REVENUE_LEVER_KEYS, "revenue", model_id
        ),
        investment_levers=_validate_levers(
            raw.get("investment_levers", {}), INVESTMENT_LEVER_KEYS, "investment", model_id
        ),
        assumptions=_assumptions_from_dict(raw.get("assumptions"), model_id),
    )


def _model_from_dict(raw: Any) -> SavedModel:
    _require(isinstance(raw, dict), "Each saved model must be a mapping.")
    model_id = raw.get("id")
    _require(
        isinstance(model_id, str) and model_id.strip() != "",
        "Saved model is missing a non-empty 'id'.",
    )
    name = raw.get("name")
    _require(
        isinstance(name, str) and name.strip() != "",
        f"Model '{model_id}': missing a non-empty 'name'.",
    )
    for field in ("created_at", "updated_at"):
        value = raw.get(field)
        _require(
            isinstance(value, str) and value != "",
            f"Model '{model_id}': missing '{field}'.",
        )
    raw_versions = raw.get("versions")
    _require(
        isinstance(raw_versions, list) and len(raw_versions) > 0,
        f"Model '{model_id}': must have a non-empty 'versions' list.",
    )
    versions = tuple(_version_from_dict(v, model_id) for v in raw_versions)
    return SavedModel(
        id=model_id,
        name=name,
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        versions=versions,
    )


def _model_to_dict(m: SavedModel) -> dict[str, Any]:
    return {
        "id": m.id,
        "name": m.name,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
        "versions": [_version_to_dict(v) for v in m.versions],
    }


class ModelStore:
    """File-backed CRUD store for saved policy models with version history.

    All mutating operations persist immediately to the backing JSON file. The
    store is single-process/local by design (multi-user comes later); concurrent
    writers are out of scope for v1.0.
    """

    def __init__(self, path, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self._now = now or (lambda: datetime.now(timezone.utc))

    # --- persistence ------------------------------------------------------

    def _timestamp(self) -> str:
        return self._now().replace(microsecond=0).isoformat()

    def _read(self) -> dict[str, SavedModel]:
        """Load and validate all models keyed by id (insertion order).

        A missing file is treated as an empty store. Any structural problem
        raises :class:`ModelStoreError`.
        """
        if not self.path.exists():
            return {}
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ModelStoreError(f"Could not parse saved-models file '{self.path}': {exc}") from exc
        except OSError as exc:
            raise ModelStoreError(f"Could not read saved-models file '{self.path}': {exc}") from exc

        _require(isinstance(doc, dict), f"Saved-models file '{self.path}' must be a JSON object.")
        version = doc.get("schema_version")
        _require(
            version == SAVED_MODELS_SCHEMA_VERSION,
            f"Unsupported saved-models schema_version {version!r} in '{self.path}' "
            f"(this build supports {SAVED_MODELS_SCHEMA_VERSION}).",
        )
        raw_models = doc.get("models", [])
        _require(isinstance(raw_models, list), f"Saved-models file '{self.path}': 'models' must be a list.")

        models: dict[str, SavedModel] = {}
        for raw in raw_models:
            model = _model_from_dict(raw)
            _require(model.id not in models, f"Duplicate model id '{model.id}' in '{self.path}'.")
            models[model.id] = model
        return models

    def _write(self, models: Mapping[str, SavedModel]) -> None:
        doc = {
            "schema_version": SAVED_MODELS_SCHEMA_VERSION,
            "models": [_model_to_dict(m) for m in models.values()],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically-ish via a temp file then replace, so a crash mid-write
        # cannot truncate an existing store.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def _unique_id(self, name: str, existing: Mapping[str, SavedModel]) -> str:
        stem = _slugify(name)
        if stem not in existing:
            return stem
        n = 2
        while f"{stem}-{n}" in existing:
            n += 1
        return f"{stem}-{n}"

    # --- reads ------------------------------------------------------------

    def list_models(self) -> list[SavedModel]:
        """Return all saved models, most-recently-updated first."""
        models = self._read()
        return sorted(models.values(), key=lambda m: m.updated_at, reverse=True)

    def get(self, model_id: str) -> SavedModel:
        """Return one model by id, or raise :class:`ModelStoreError`."""
        models = self._read()
        _require(model_id in models, f"No saved model with id '{model_id}'.")
        return models[model_id]

    # --- mutations --------------------------------------------------------

    def create(
        self,
        name: str,
        revenue_levers: Mapping[str, float],
        investment_levers: Mapping[str, float],
        assumptions: FeedbackAssumptions,
        note: str = "",
    ) -> SavedModel:
        """Create a new saved model at version 1 and persist it."""
        _require(
            isinstance(name, str) and name.strip() != "",
            "A saved model needs a non-empty name.",
        )
        models = self._read()
        model_id = self._unique_id(name, models)
        ts = self._timestamp()
        version = ModelVersion(
            version=1,
            saved_at=ts,
            note=note,
            revenue_levers=_validate_levers(revenue_levers, REVENUE_LEVER_KEYS, "revenue", model_id),
            investment_levers=_validate_levers(
                investment_levers, INVESTMENT_LEVER_KEYS, "investment", model_id
            ),
            assumptions=assumptions,
        )
        model = SavedModel(
            id=model_id, name=name.strip(), created_at=ts, updated_at=ts, versions=(version,)
        )
        models[model_id] = model
        self._write(models)
        return model

    def update(
        self,
        model_id: str,
        revenue_levers: Mapping[str, float],
        investment_levers: Mapping[str, float],
        assumptions: FeedbackAssumptions,
        note: str = "",
    ) -> SavedModel:
        """Append a new version to an existing model and persist it."""
        models = self._read()
        _require(model_id in models, f"No saved model with id '{model_id}'.")
        existing = models[model_id]
        ts = self._timestamp()
        new_version = ModelVersion(
            version=existing.current.version + 1,
            saved_at=ts,
            note=note,
            revenue_levers=_validate_levers(revenue_levers, REVENUE_LEVER_KEYS, "revenue", model_id),
            investment_levers=_validate_levers(
                investment_levers, INVESTMENT_LEVER_KEYS, "investment", model_id
            ),
            assumptions=assumptions,
        )
        updated = SavedModel(
            id=existing.id,
            name=existing.name,
            created_at=existing.created_at,
            updated_at=ts,
            versions=existing.versions + (new_version,),
        )
        models[model_id] = updated
        self._write(models)
        return updated

    def clone(self, model_id: str, new_name: str, note: str = "") -> SavedModel:
        """Copy a model's current version into a brand-new model at version 1."""
        _require(
            isinstance(new_name, str) and new_name.strip() != "",
            "A cloned model needs a non-empty name.",
        )
        source = self.get(model_id)
        cur = source.current
        return self.create(
            new_name,
            cur.revenue_levers,
            cur.investment_levers,
            cur.assumptions,
            note=note or f"Cloned from '{source.name}' (v{cur.version}).",
        )

    def delete(self, model_id: str) -> None:
        """Delete a saved model and persist the change."""
        models = self._read()
        _require(model_id in models, f"No saved model with id '{model_id}'.")
        del models[model_id]
        self._write(models)
