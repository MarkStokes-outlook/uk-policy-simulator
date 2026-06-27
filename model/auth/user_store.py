"""User storage abstraction + file-backed JSON implementation (EPIC-005).

The store is split from the provider on purpose: :class:`UserStore` is a narrow
*repository* interface the provider depends on, and :class:`JsonUserStore` is the
first concrete backend. Swapping in SQLite/Postgres later means writing a new
class against :class:`UserStore` — no change to the provider or the app.

The JSON implementation mirrors :class:`model.saved_models.ModelStore`: a single
versioned JSON file, validate-on-read, atomic temp-file writes. The file holds
**password hashes** and is therefore user data/secrets — it is gitignored, never
committed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Protocol, runtime_checkable

from .types import User, UserStoreError, normalize_email

# Bump when the on-disk users schema changes shape; the store refuses files whose
# ``schema_version`` it does not understand (same contract as saved models).
AUTH_SCHEMA_VERSION = 1


@runtime_checkable
class UserStore(Protocol):
    """Repository interface over user records, keyed by canonical ``user_id``.

    A concrete store must keep ``user_id`` unique and resolve emails in their
    normalised form (see :func:`model.auth.types.normalize_email`).
    """

    def get_by_id(self, user_id: str) -> User | None:
        """Return the user with ``user_id``, or ``None``."""
        ...

    def get_by_email(self, email: str) -> User | None:
        """Return the user whose normalised email matches, or ``None``."""
        ...

    def add(self, user: User) -> None:
        """Persist a new user. Raise :class:`UserStoreError` on id/email clash."""
        ...

    def update(self, user: User) -> None:
        """Persist changes to an existing user (matched by ``user_id``)."""
        ...

    def list_users(self) -> list[User]:
        """Return all users (order unspecified)."""
        ...


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise UserStoreError(message)


def _user_to_dict(u: User) -> dict[str, object]:
    return {
        "user_id": u.user_id,
        "email": u.email,
        "display_name": u.display_name,
        "created_at": u.created_at,
        "updated_at": u.updated_at,
        "provider": u.provider,
        "provider_subject": u.provider_subject,
        "is_active": u.is_active,
        "password_hash": u.password_hash,
    }


def _user_from_dict(raw: object) -> User:
    _require(isinstance(raw, dict), "Each stored user must be a mapping.")
    assert isinstance(raw, dict)  # narrow for type-checkers after _require
    user_id = raw.get("user_id")
    _require(
        isinstance(user_id, str) and user_id.strip() != "",
        "Stored user is missing a non-empty 'user_id'.",
    )
    for field_name in ("email", "display_name", "created_at", "updated_at", "provider", "provider_subject"):
        value = raw.get(field_name)
        _require(
            isinstance(value, str) and value != "",
            f"User '{user_id}': missing '{field_name}'.",
        )
    is_active = raw.get("is_active", True)
    _require(
        isinstance(is_active, bool),
        f"User '{user_id}': 'is_active' must be a boolean (got {is_active!r}).",
    )
    password_hash = raw.get("password_hash")
    _require(
        password_hash is None or (isinstance(password_hash, str) and password_hash != ""),
        f"User '{user_id}': 'password_hash' must be a non-empty string or null.",
    )
    return User(
        user_id=raw["user_id"],
        email=raw["email"],
        display_name=raw["display_name"],
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        provider=raw["provider"],
        provider_subject=raw["provider_subject"],
        is_active=is_active,
        password_hash=password_hash,
    )


class JsonUserStore:
    """File-backed :class:`UserStore`, single-process/local by design.

    Concurrent writers are out of scope for this slice (same posture as the
    saved-models store). Emails are matched case-insensitively via their
    normalised form.
    """

    def __init__(self, path) -> None:
        self.path = Path(path)

    # --- persistence ------------------------------------------------------

    def _read(self) -> dict[str, User]:
        """Load and validate all users keyed by ``user_id`` (insertion order)."""
        if not self.path.exists():
            return {}
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UserStoreError(f"Could not parse users file '{self.path}': {exc}") from exc
        except OSError as exc:
            raise UserStoreError(f"Could not read users file '{self.path}': {exc}") from exc

        _require(isinstance(doc, dict), f"Users file '{self.path}' must be a JSON object.")
        version = doc.get("schema_version")
        _require(
            version == AUTH_SCHEMA_VERSION,
            f"Unsupported users schema_version {version!r} in '{self.path}' "
            f"(this build supports {AUTH_SCHEMA_VERSION}).",
        )
        raw_users = doc.get("users", [])
        _require(isinstance(raw_users, list), f"Users file '{self.path}': 'users' must be a list.")

        users: dict[str, User] = {}
        seen_emails: set[str] = set()
        for raw in raw_users:
            user = _user_from_dict(raw)
            _require(user.user_id not in users, f"Duplicate user_id '{user.user_id}' in '{self.path}'.")
            normalised = normalize_email(user.email)
            _require(
                normalised not in seen_emails,
                f"Duplicate email '{user.email}' in '{self.path}'.",
            )
            users[user.user_id] = user
            seen_emails.add(normalised)
        return users

    def _write(self, users: Mapping[str, User]) -> None:
        doc = {
            "schema_version": AUTH_SCHEMA_VERSION,
            "users": [_user_to_dict(u) for u in users.values()],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic-ish write (temp file + replace) so a crash mid-write cannot
        # truncate an existing user store.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    # --- reads ------------------------------------------------------------

    def get_by_id(self, user_id: str) -> User | None:
        return self._read().get(user_id)

    def get_by_email(self, email: str) -> User | None:
        target = normalize_email(email)
        for user in self._read().values():
            if normalize_email(user.email) == target:
                return user
        return None

    def list_users(self) -> list[User]:
        return list(self._read().values())

    # --- mutations --------------------------------------------------------

    def add(self, user: User) -> None:
        users = self._read()
        _require(user.user_id not in users, f"User id '{user.user_id}' already exists.")
        target = normalize_email(user.email)
        for existing in users.values():
            _require(
                normalize_email(existing.email) != target,
                f"Email '{user.email}' is already registered.",
            )
        users[user.user_id] = user
        self._write(users)

    def update(self, user: User) -> None:
        users = self._read()
        _require(user.user_id in users, f"No user with id '{user.user_id}'.")
        # Guard against an email change colliding with a different user.
        target = normalize_email(user.email)
        for other_id, existing in users.items():
            if other_id == user.user_id:
                continue
            _require(
                normalize_email(existing.email) != target,
                f"Email '{user.email}' is already registered.",
            )
        users[user.user_id] = user
        self._write(users)


def users_from_iterable(raw_users: Iterable[object]) -> list[User]:
    """Validate a sequence of raw user dicts — handy for tests/imports."""
    return [_user_from_dict(r) for r in raw_users]
