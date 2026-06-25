"""Tests for persistent saved models (EPIC-004 / v1.0).

Covers create/load/clone/delete, version history, persistence round-trips and
store validation. Uses a pinned clock and a tmp file so everything is
deterministic. Run with: pytest
"""

import itertools
from datetime import datetime, timezone

import pytest

from model.fiscal_model import FeedbackAssumptions
from model.scenarios import INVESTMENT_LEVER_KEYS, REVENUE_LEVER_KEYS
from model.saved_models import (
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

ASSUMPTIONS = FeedbackAssumptions(
    years=10,
    growth_baseline=0.035,
    revenue_feedback_rate=0.3,
    cost_reduction_rate=0.2,
    lag_years=2,
    implementation_quality=0.7,
    optimism_penalty=0.2,
)


def _rev(**overrides) -> dict:
    levers = {k: 0.0 for k in REVENUE_LEVER_KEYS}
    levers.update(overrides)
    return levers


def _inv(**overrides) -> dict:
    levers = {k: 0.0 for k in INVESTMENT_LEVER_KEYS}
    levers.update(overrides)
    return levers


def _clock(start=2026):
    """A deterministic, monotonically-increasing UTC clock."""
    counter = itertools.count()

    def now():
        n = next(counter)
        return datetime(start, 1, 1, 12, 0, n, tzinfo=timezone.utc)

    return now


def _store(tmp_path):
    return ModelStore(tmp_path / "saved_models.json", now=_clock())


# --- Empty store ----------------------------------------------------------

def test_empty_store_lists_nothing(tmp_path):
    store = _store(tmp_path)
    assert store.list_models() == []
    assert not (tmp_path / "saved_models.json").exists()


def test_get_missing_raises(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ModelStoreError, match="No saved model"):
        store.get("nope")


# --- Create / load --------------------------------------------------------

def test_create_persists_and_round_trips(tmp_path):
    store = _store(tmp_path)
    model = store.create("My Plan", _rev(wealth_property=20.0), _inv(housing=30.0), ASSUMPTIONS)
    assert isinstance(model, SavedModel)
    assert model.id == "my-plan"
    assert model.current.version == 1
    assert model.current.revenue_levers["wealth_property"] == 20.0
    assert model.current.investment_levers["housing"] == 30.0

    # A fresh store over the same file sees the persisted model.
    reloaded = ModelStore(tmp_path / "saved_models.json").get("my-plan")
    assert reloaded.name == "My Plan"
    assert reloaded.current.assumptions == ASSUMPTIONS


def test_duplicate_names_get_unique_ids(tmp_path):
    store = _store(tmp_path)
    a = store.create("Plan", _rev(), _inv(), ASSUMPTIONS)
    b = store.create("Plan", _rev(), _inv(), ASSUMPTIONS)
    c = store.create("Plan", _rev(), _inv(), ASSUMPTIONS)
    assert [a.id, b.id, c.id] == ["plan", "plan-2", "plan-3"]


def test_create_requires_name(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ModelStoreError, match="non-empty name"):
        store.create("  ", _rev(), _inv(), ASSUMPTIONS)


def test_create_validates_levers(tmp_path):
    store = _store(tmp_path)
    bad = _rev()
    del bad["corporate"]  # missing canonical key
    with pytest.raises(ModelStoreError, match="missing"):
        store.create("Bad", bad, _inv(), ASSUMPTIONS)


# --- Version history ------------------------------------------------------

def test_update_appends_version_and_keeps_history(tmp_path):
    store = _store(tmp_path)
    store.create("Plan", _rev(wealth_property=10.0), _inv(), ASSUMPTIONS, note="initial")
    updated = store.update("plan", _rev(wealth_property=25.0), _inv(housing=40.0), ASSUMPTIONS, note="bump")

    assert len(updated.versions) == 2
    assert updated.current.version == 2
    assert updated.current.note == "bump"
    assert updated.current.revenue_levers["wealth_property"] == 25.0
    # History is preserved: v1 still holds the original values.
    assert updated.versions[0].version == 1
    assert updated.versions[0].revenue_levers["wealth_property"] == 10.0
    # updated_at advances; created_at is stable.
    assert updated.updated_at >= updated.created_at
    assert updated.created_at == updated.versions[0].saved_at


def test_update_missing_raises(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ModelStoreError, match="No saved model"):
        store.update("ghost", _rev(), _inv(), ASSUMPTIONS)


# --- Clone ----------------------------------------------------------------

def test_clone_copies_current_version_into_new_model(tmp_path):
    store = _store(tmp_path)
    store.create("Original", _rev(corporate=15.0), _inv(nhs_prevention=20.0), ASSUMPTIONS)
    store.update("original", _rev(corporate=18.0), _inv(nhs_prevention=22.0), ASSUMPTIONS)

    clone = store.clone("original", "Original copy")
    assert clone.id == "original-copy"
    assert clone.current.version == 1  # clone starts a fresh history
    # Copies the *current* (v2) values, not the original v1.
    assert clone.current.revenue_levers["corporate"] == 18.0
    assert clone.current.investment_levers["nhs_prevention"] == 22.0
    assert "Cloned from 'Original'" in clone.current.note

    # Both models coexist.
    assert {m.id for m in store.list_models()} == {"original", "original-copy"}


def test_clone_missing_raises(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ModelStoreError, match="No saved model"):
        store.clone("ghost", "x")


# --- Delete ---------------------------------------------------------------

def test_delete_removes_model(tmp_path):
    store = _store(tmp_path)
    store.create("Keep", _rev(), _inv(), ASSUMPTIONS)
    store.create("Drop", _rev(), _inv(), ASSUMPTIONS)
    store.delete("drop")
    assert {m.id for m in store.list_models()} == {"keep"}
    with pytest.raises(ModelStoreError, match="No saved model"):
        store.get("drop")


def test_delete_missing_raises(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ModelStoreError, match="No saved model"):
        store.delete("ghost")


# --- Ordering -------------------------------------------------------------

def test_list_is_most_recently_updated_first(tmp_path):
    store = _store(tmp_path)
    store.create("First", _rev(), _inv(), ASSUMPTIONS)
    store.create("Second", _rev(), _inv(), ASSUMPTIONS)
    store.update("first", _rev(wealth_property=5.0), _inv(), ASSUMPTIONS)  # touch 'first' last
    ids = [m.id for m in store.list_models()]
    assert ids[0] == "first"


# --- Store-file validation ------------------------------------------------

def test_unsupported_schema_version_raises(tmp_path):
    p = tmp_path / "saved_models.json"
    p.write_text('{"schema_version": 999, "models": []}', encoding="utf-8")
    with pytest.raises(ModelStoreError, match="schema_version"):
        ModelStore(p).list_models()


def test_corrupt_json_raises(tmp_path):
    p = tmp_path / "saved_models.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ModelStoreError, match="parse"):
        ModelStore(p).list_models()


def _write_store_with_assumptions(tmp_path, **assumption_overrides):
    """Write a structurally-valid store whose assumptions can be tampered with."""
    import json

    assumptions = {
        "years": 10,
        "growth_baseline": 0.035,
        "revenue_feedback_rate": 0.3,
        "cost_reduction_rate": 0.2,
        "lag_years": 2,
        "implementation_quality": 0.7,
        "optimism_penalty": 0.2,
    }
    assumptions.update(assumption_overrides)
    doc = {
        "schema_version": SAVED_MODELS_SCHEMA_VERSION,
        "models": [
            {
                "id": "hand-edited",
                "name": "Hand edited",
                "created_at": "2026-01-01T12:00:00+00:00",
                "updated_at": "2026-01-01T12:00:00+00:00",
                "versions": [
                    {
                        "version": 1,
                        "saved_at": "2026-01-01T12:00:00+00:00",
                        "note": "",
                        "revenue_levers": _rev(),
                        "investment_levers": _inv(),
                        "assumptions": assumptions,
                    }
                ],
            }
        ],
    }
    p = tmp_path / "saved_models.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


@pytest.mark.parametrize(
    "field, value",
    [
        ("years", 10.5),       # fractional
        ("lag_years", 2.5),    # fractional
        ("years", True),       # boolean masquerading as int
        ("lag_years", False),  # boolean masquerading as int
    ],
)
def test_corrupt_store_rejects_non_integer_year_fields(tmp_path, field, value):
    p = _write_store_with_assumptions(tmp_path, **{field: value})
    with pytest.raises(ModelStoreError, match=f"'{field}' must be an integer"):
        ModelStore(p).list_models()


def test_hand_edited_store_with_valid_integers_still_loads(tmp_path):
    # Sanity check the helper isn't rejecting everything.
    p = _write_store_with_assumptions(tmp_path)
    models = ModelStore(p).list_models()
    assert models[0].current.assumptions.years == 10


def test_schema_version_is_written(tmp_path):
    import json

    store = _store(tmp_path)
    store.create("Plan", _rev(), _inv(), ASSUMPTIONS)
    doc = json.loads((tmp_path / "saved_models.json").read_text(encoding="utf-8"))
    assert doc["schema_version"] == SAVED_MODELS_SCHEMA_VERSION
    assert len(doc["models"]) == 1


# --- Ownership (EPIC-005) -------------------------------------------------

def test_create_without_owner_is_unowned(tmp_path):
    store = _store(tmp_path)
    model = store.create("Plan", _rev(), _inv(), ASSUMPTIONS)
    assert model.owner_user_id is None


def test_create_with_owner_persists_and_round_trips(tmp_path):
    store = _store(tmp_path)
    store.create("Owned", _rev(), _inv(), ASSUMPTIONS, owner_user_id="user-0001")
    reloaded = ModelStore(tmp_path / "saved_models.json").get("owned")
    assert reloaded.owner_user_id == "user-0001"


def test_update_preserves_owner(tmp_path):
    store = _store(tmp_path)
    store.create("Owned", _rev(), _inv(), ASSUMPTIONS, owner_user_id="user-0001")
    updated = store.update("owned", _rev(wealth_property=5.0), _inv(), ASSUMPTIONS)
    assert updated.owner_user_id == "user-0001"


def test_clone_inherits_owner_by_default_and_can_reassign(tmp_path):
    store = _store(tmp_path)
    store.create("Src", _rev(), _inv(), ASSUMPTIONS, owner_user_id="user-0001")
    inherited = store.clone("src", "Inherited copy")
    assert inherited.owner_user_id == "user-0001"
    reassigned = store.clone("src", "Reassigned copy", owner_user_id="user-0002")
    assert reassigned.owner_user_id == "user-0002"


def test_legacy_model_without_owner_key_loads_as_unowned(tmp_path):
    """A store file written before EPIC-005 omits owner_user_id entirely."""
    import json

    doc = {
        "schema_version": SAVED_MODELS_SCHEMA_VERSION,
        "models": [
            {
                "id": "legacy",
                "name": "Legacy",
                "created_at": "2026-01-01T12:00:00+00:00",
                "updated_at": "2026-01-01T12:00:00+00:00",
                # NOTE: no owner_user_id key at all
                "versions": [
                    {
                        "version": 1,
                        "saved_at": "2026-01-01T12:00:00+00:00",
                        "note": "",
                        "revenue_levers": _rev(),
                        "investment_levers": _inv(),
                        "assumptions": {
                            "years": 10,
                            "growth_baseline": 0.035,
                            "revenue_feedback_rate": 0.3,
                            "cost_reduction_rate": 0.2,
                            "lag_years": 2,
                            "implementation_quality": 0.7,
                            "optimism_penalty": 0.2,
                        },
                    }
                ],
            }
        ],
    }
    p = tmp_path / "saved_models.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    model = ModelStore(p).get("legacy")
    assert model.owner_user_id is None


def test_owner_user_id_must_be_string_or_null(tmp_path):
    import json

    doc = {
        "schema_version": SAVED_MODELS_SCHEMA_VERSION,
        "models": [
            {
                "id": "bad",
                "name": "Bad owner",
                "created_at": "2026-01-01T12:00:00+00:00",
                "updated_at": "2026-01-01T12:00:00+00:00",
                "owner_user_id": "   ",  # blank string is not a valid owner
                "versions": [
                    {
                        "version": 1,
                        "saved_at": "2026-01-01T12:00:00+00:00",
                        "note": "",
                        "revenue_levers": _rev(),
                        "investment_levers": _inv(),
                        "assumptions": {
                            "years": 10,
                            "growth_baseline": 0.035,
                            "revenue_feedback_rate": 0.3,
                            "cost_reduction_rate": 0.2,
                            "lag_years": 2,
                            "implementation_quality": 0.7,
                            "optimism_penalty": 0.2,
                        },
                    }
                ],
            }
        ],
    }
    p = tmp_path / "saved_models.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ModelStoreError, match="owner_user_id"):
        ModelStore(p).list_models()


# --- Ownership visibility filtering (EPIC-005 auth slice) -----------------

def _seed_mixed_owners(tmp_path):
    """A store with a legacy/unowned model and one per two distinct owners."""
    store = _store(tmp_path)
    store.create("Legacy", _rev(), _inv(), ASSUMPTIONS)  # owner None
    store.create("Alice plan", _rev(), _inv(), ASSUMPTIONS, owner_user_id="user-alice")
    store.create("Bob plan", _rev(), _inv(), ASSUMPTIONS, owner_user_id="user-bob")
    return store.list_models()


def test_filter_shows_owned_plus_legacy_for_a_user(tmp_path):
    models = _seed_mixed_owners(tmp_path)
    visible = {m.id for m in filter_visible_models(models, "user-alice")}
    assert visible == {"alice-plan", "legacy"}  # own + legacy, not Bob's


def test_filter_guest_sees_only_legacy(tmp_path):
    models = _seed_mixed_owners(tmp_path)
    visible = {m.id for m in filter_visible_models(models, None)}
    assert visible == {"legacy"}


def test_filter_can_exclude_legacy(tmp_path):
    models = _seed_mixed_owners(tmp_path)
    visible = {m.id for m in filter_visible_models(models, "user-alice", include_legacy=False)}
    assert visible == {"alice-plan"}
    # A guest with legacy excluded sees nothing.
    assert filter_visible_models(models, None, include_legacy=False) == []


# --- Ownership authorisation policy (EPIC-005) ----------------------------

def _model(owner):
    """A minimal SavedModel carrying just the owner — enough for authz tests."""
    v = ModelVersion(
        version=1,
        saved_at="2026-01-01T12:00:00+00:00",
        note="",
        revenue_levers=_rev(),
        investment_levers=_inv(),
        assumptions=ASSUMPTIONS,
    )
    return SavedModel(
        id="m",
        name="M",
        created_at="2026-01-01T12:00:00+00:00",
        updated_at="2026-01-01T12:00:00+00:00",
        versions=(v,),
        owner_user_id=owner,
    )


def test_owner_may_mutate_own_model():
    m = _model("user-alice")
    assert can_mutate(m, "user-alice") is True
    authorize_mutation(m, "user-alice")  # does not raise


def test_other_user_may_not_mutate():
    m = _model("user-alice")
    assert can_mutate(m, "user-bob") is False
    with pytest.raises(ModelAuthorizationError, match="belongs to another user"):
        authorize_mutation(m, "user-bob")


def test_guest_may_not_mutate_owned_model():
    m = _model("user-alice")
    assert can_mutate(m, None) is False
    with pytest.raises(ModelAuthorizationError, match="belongs to another user"):
        authorize_mutation(m, None)


def test_legacy_model_is_read_only_for_everyone():
    m = _model(None)
    assert can_mutate(m, None) is False
    assert can_mutate(m, "user-alice") is False
    for actor in (None, "user-alice"):
        with pytest.raises(ModelAuthorizationError, match="read-only"):
            authorize_mutation(m, actor)


def test_authorization_error_is_a_store_error():
    # Defence in depth: any `except ModelStoreError` path catches authz failures.
    assert issubclass(ModelAuthorizationError, ModelStoreError)


# --- Authorisation enforced over a real store (app-path shape) ------------

def test_store_mutation_denied_for_non_owner_then_allowed_for_owner(tmp_path):
    store = _store(tmp_path)
    store.create("Alice plan", _rev(), _inv(), ASSUMPTIONS, owner_user_id="user-alice")

    # Bob and a guest are refused before any store mutation happens.
    target = store.get("alice-plan")
    with pytest.raises(ModelAuthorizationError):
        authorize_mutation(target, "user-bob")
    with pytest.raises(ModelAuthorizationError):
        authorize_mutation(target, None)

    # The model is untouched (still a single version) after refused attempts.
    assert len(store.get("alice-plan").versions) == 1

    # The owner is authorised and the mutation goes through.
    authorize_mutation(store.get("alice-plan"), "user-alice")
    updated = store.update("alice-plan", _rev(wealth_property=5.0), _inv(), ASSUMPTIONS)
    assert len(updated.versions) == 2
    assert updated.owner_user_id == "user-alice"
