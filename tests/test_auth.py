"""Tests for the identity layer foundation (EPIC-005, v1.1).

Covers password hashing, the file-backed user store, the local auth provider,
the framework-agnostic session helpers, and saved-model ownership. Uses a pinned
clock and deterministic id factory (mirroring test_saved_models.py) so behaviour
is reproducible. Run with: pytest
"""

import itertools
from datetime import datetime, timezone

import pytest

from model.auth import (
    AUTH_SCHEMA_VERSION,
    AuthSession,
    InvalidCredentialsError,
    JsonUserStore,
    LocalAuthProvider,
    User,
    UserExistsError,
    UserStoreError,
    current_session,
    current_user_id,
    hash_password,
    is_authenticated,
    login,
    logout,
    needs_rehash,
    normalize_email,
    verify_password,
)


# --- Deterministic helpers ------------------------------------------------

def _clock(start=2026):
    """A deterministic, monotonically-increasing UTC clock."""
    counter = itertools.count()

    def now():
        n = next(counter)
        return datetime(start, 1, 1, 12, 0, n, tzinfo=timezone.utc)

    return now


def _ids(prefix="user"):
    """A deterministic id factory yielding user-0001, user-0002, ..."""
    counter = itertools.count(1)
    return lambda: f"{prefix}-{next(counter):04d}"


def _provider(tmp_path):
    store = JsonUserStore(tmp_path / "users.json")
    return LocalAuthProvider(store, now=_clock(), id_factory=_ids())


# --- Password hashing -----------------------------------------------------

def test_hash_is_not_plaintext_and_is_salted():
    h1 = hash_password("correct horse battery staple")
    h2 = hash_password("correct horse battery staple")
    assert "correct horse battery staple" not in h1
    assert h1.startswith("$argon2")
    # Per-hash random salt => same password hashes differently.
    assert h1 != h2


def test_verify_accepts_correct_and_rejects_wrong():
    h = hash_password("s3cret-pa55")
    assert verify_password(h, "s3cret-pa55") is True
    assert verify_password(h, "wrong") is False
    assert verify_password(h, "") is False


def test_verify_rejects_garbage_hash_without_raising():
    assert verify_password("not-a-real-hash", "whatever") is False


def test_hash_rejects_empty_password():
    with pytest.raises(ValueError):
        hash_password("")


def test_needs_rehash_false_for_current_params():
    assert needs_rehash(hash_password("abc123")) is False
    assert needs_rehash("garbage") is True


# --- Email normalisation --------------------------------------------------

def test_normalize_email_lowercases_and_strips():
    assert normalize_email("  Alice@Example.COM ") == "alice@example.com"


# --- User store -----------------------------------------------------------

def test_empty_store_returns_none(tmp_path):
    store = JsonUserStore(tmp_path / "users.json")
    assert store.get_by_id("nope") is None
    assert store.get_by_email("nobody@example.com") is None
    assert store.list_users() == []
    assert not (tmp_path / "users.json").exists()


def test_store_add_get_round_trip(tmp_path):
    path = tmp_path / "users.json"
    store = JsonUserStore(path)
    user = User(
        user_id="u-1",
        email="bob@example.com",
        display_name="Bob",
        created_at="2026-01-01T12:00:00+00:00",
        updated_at="2026-01-01T12:00:00+00:00",
        provider="local",
        provider_subject="bob@example.com",
        is_active=True,
        password_hash=hash_password("hunter2"),
    )
    store.add(user)

    # A fresh store over the same file sees the persisted user.
    reloaded = JsonUserStore(path)
    assert reloaded.get_by_id("u-1") == user
    # Email lookup is case-insensitive.
    assert reloaded.get_by_email("BOB@EXAMPLE.COM").user_id == "u-1"


def test_store_rejects_duplicate_id_and_email(tmp_path):
    store = JsonUserStore(tmp_path / "users.json")
    base = dict(
        display_name="X",
        created_at="2026-01-01T12:00:00+00:00",
        updated_at="2026-01-01T12:00:00+00:00",
        provider="local",
        provider_subject="x",
        password_hash="h",
    )
    store.add(User(user_id="u-1", email="a@example.com", **base))
    with pytest.raises(UserStoreError, match="already exists"):
        store.add(User(user_id="u-1", email="other@example.com", **base))
    with pytest.raises(UserStoreError, match="already registered"):
        store.add(User(user_id="u-2", email="A@EXAMPLE.COM", **base))


def test_store_unsupported_schema_version_raises(tmp_path):
    p = tmp_path / "users.json"
    p.write_text('{"schema_version": 999, "users": []}', encoding="utf-8")
    with pytest.raises(UserStoreError, match="schema_version"):
        JsonUserStore(p).list_users()


def test_store_writes_schema_version(tmp_path):
    import json

    path = tmp_path / "users.json"
    provider = LocalAuthProvider(JsonUserStore(path), now=_clock(), id_factory=_ids())
    provider.register("a@example.com", "pw-123456")
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["schema_version"] == AUTH_SCHEMA_VERSION
    assert len(doc["users"]) == 1


# --- Local provider: registration ----------------------------------------

def test_register_creates_user_with_stable_internal_id(tmp_path):
    provider = _provider(tmp_path)
    user = provider.register("Alice@Example.com", "pw-12345678", display_name="Alice")

    # user_id is the canonical key and is NOT the email.
    assert user.user_id == "user-0001"
    assert user.user_id != user.email
    assert user.email == "alice@example.com"  # normalised
    assert user.display_name == "Alice"
    assert user.provider == "local"
    assert user.provider_subject == "alice@example.com"
    assert user.is_active is True
    # Password is stored hashed, never in plaintext.
    assert user.password_hash and user.password_hash != "pw-12345678"
    assert verify_password(user.password_hash, "pw-12345678") is True


def test_register_defaults_display_name_to_email(tmp_path):
    provider = _provider(tmp_path)
    user = provider.register("noname@example.com", "pw-12345678")
    assert user.display_name == "noname@example.com"


def test_register_duplicate_email_raises(tmp_path):
    provider = _provider(tmp_path)
    provider.register("dup@example.com", "pw-12345678")
    with pytest.raises(UserExistsError, match="already registered"):
        provider.register("DUP@example.com", "different-pw")  # case-insensitive clash


def test_register_requires_password(tmp_path):
    provider = _provider(tmp_path)
    with pytest.raises(InvalidCredentialsError):
        provider.register("x@example.com", "")


# --- Local provider: authentication ---------------------------------------

def test_authenticate_success_returns_session(tmp_path):
    provider = _provider(tmp_path)
    registered = provider.register("alice@example.com", "pw-12345678")
    session = provider.authenticate("ALICE@example.com", "pw-12345678")

    assert isinstance(session, AuthSession)
    assert session.user_id == registered.user_id
    assert session.email == "alice@example.com"
    assert session.provider == "local"
    # The session principal must never carry the password hash.
    assert not hasattr(session, "password_hash")


def test_authenticate_wrong_password_raises(tmp_path):
    provider = _provider(tmp_path)
    provider.register("alice@example.com", "pw-12345678")
    with pytest.raises(InvalidCredentialsError):
        provider.authenticate("alice@example.com", "nope")


def test_authenticate_unknown_email_raises_same_error(tmp_path):
    provider = _provider(tmp_path)
    with pytest.raises(InvalidCredentialsError):
        provider.authenticate("ghost@example.com", "whatever")


def test_authenticate_inactive_user_raises(tmp_path):
    import dataclasses

    path = tmp_path / "users.json"
    store = JsonUserStore(path)
    provider = LocalAuthProvider(store, now=_clock(), id_factory=_ids())
    user = provider.register("alice@example.com", "pw-12345678")
    store.update(dataclasses.replace(user, is_active=False))

    with pytest.raises(InvalidCredentialsError):
        provider.authenticate("alice@example.com", "pw-12345678")


def test_get_user_round_trips(tmp_path):
    provider = _provider(tmp_path)
    user = provider.register("alice@example.com", "pw-12345678")
    assert provider.get_user(user.user_id).email == "alice@example.com"
    assert provider.get_user("missing") is None


# --- Session helpers (framework-agnostic) ---------------------------------

def test_session_login_current_logout_with_plain_dict():
    # A plain dict stands in for st.session_state (a MutableMapping). No Streamlit.
    state: dict = {}
    assert is_authenticated(state) is False
    assert current_session(state) is None
    assert current_user_id(state) is None

    session = AuthSession(user_id="u-1", email="a@example.com", display_name="A", provider="local")
    login(state, session)
    assert is_authenticated(state) is True
    assert current_session(state) == session
    assert current_user_id(state) == "u-1"

    logout(state)
    assert is_authenticated(state) is False
    assert current_user_id(state) is None
    logout(state)  # idempotent


def test_login_rejects_non_session():
    with pytest.raises(TypeError):
        login({}, "not-a-session")


# --- Save-stamping + filtering integration --------------------------------
# Exercises the exact path app.py uses (session helpers -> current_user_id ->
# store.create(owner_user_id=...) -> filter_visible_models) with a plain dict
# standing in for st.session_state, so the wiring is covered without Streamlit.

def test_signed_in_save_is_stamped_and_filtered_to_owner(tmp_path):
    from model.fiscal_model import FeedbackAssumptions
    from model.saved_models import ModelStore, filter_visible_models
    from model.scenarios import INVESTMENT_LEVER_KEYS, REVENUE_LEVER_KEYS

    rev = {k: 0.0 for k in REVENUE_LEVER_KEYS}
    inv = {k: 0.0 for k in INVESTMENT_LEVER_KEYS}
    assumptions = FeedbackAssumptions(
        years=10,
        growth_baseline=0.035,
        revenue_feedback_rate=0.3,
        cost_reduction_rate=0.2,
        lag_years=2,
        implementation_quality=0.7,
        optimism_penalty=0.2,
    )
    store = ModelStore(tmp_path / "saved_models.json")

    # A guest save (no session) is unowned/legacy.
    guest_state: dict = {}
    store.create("Guest plan", rev, inv, assumptions, owner_user_id=current_user_id(guest_state))

    # An authenticated save is stamped with the user's canonical id.
    provider = _provider(tmp_path)
    user = provider.register("alice@example.com", "pw-12345678")
    state: dict = {}
    login(state, provider.authenticate("alice@example.com", "pw-12345678"))
    store.create("Alice plan", rev, inv, assumptions, owner_user_id=current_user_id(state))

    by_id = {m.id: m for m in store.list_models()}
    assert by_id["guest-plan"].owner_user_id is None
    assert by_id["alice-plan"].owner_user_id == user.user_id

    # Alice sees her model + the legacy guest model; a guest sees only legacy.
    alice_visible = {m.id for m in filter_visible_models(store.list_models(), current_user_id(state))}
    guest_visible = {m.id for m in filter_visible_models(store.list_models(), current_user_id(guest_state))}
    assert alice_visible == {"alice-plan", "guest-plan"}
    assert guest_visible == {"guest-plan"}
