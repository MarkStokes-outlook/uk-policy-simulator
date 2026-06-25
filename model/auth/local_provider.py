"""Local (email + password) auth provider (EPIC-005, v1.1 foundation).

The first concrete backend behind :class:`model.auth.provider.PasswordAuthProvider`.
It owns *policy* (registration rules, credential checks, id minting) and delegates
*storage* to a :class:`model.auth.user_store.UserStore` and *hashing* to
:mod:`model.auth.password`. It has no Streamlit dependency.

Determinism (matching the project's house style): the clock and the ``user_id``
factory are both injectable, so tests can pin time and ids. By default ``user_id``
is a random UUID hex — a stable internal key that is **independent of the email**,
so a user can change their email without changing identity.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from . import password as password_utils
from .provider import PasswordAuthProvider
from .types import (
    AuthError,
    AuthSession,
    InvalidCredentialsError,
    User,
    UserExistsError,
    UserNotFoundError,
    normalize_email,
)
from .user_store import UserStore


class LocalAuthProvider(PasswordAuthProvider):
    """Email/password identity backed by a :class:`UserStore`."""

    provider_name = "local"

    def __init__(
        self,
        store: UserStore,
        *,
        now: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        hash_password: Callable[[str], str] | None = None,
        verify_password: Callable[[str, str], bool] | None = None,
    ) -> None:
        self._store = store
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._hash = hash_password or password_utils.hash_password
        self._verify = verify_password or password_utils.verify_password

    def _timestamp(self) -> str:
        return self._now().replace(microsecond=0).isoformat()

    # --- AuthProvider -----------------------------------------------------

    def get_user(self, user_id: str) -> User | None:
        return self._store.get_by_id(user_id)

    # --- PasswordAuthProvider --------------------------------------------

    def register(
        self, email: str, password: str, display_name: str | None = None
    ) -> User:
        """Register a new local user. Email must be unused; password is hashed."""
        normalised = normalize_email(email)
        if normalised == "":
            raise UserExistsError("A valid email is required to register.")
        if not isinstance(password, str) or password == "":
            # Mirrors hash_password's contract; surfaced as a domain error.
            raise InvalidCredentialsError("A non-empty password is required.")
        if self._store.get_by_email(normalised) is not None:
            raise UserExistsError(f"Email '{normalised}' is already registered.")

        ts = self._timestamp()
        name = (display_name or "").strip() or normalised
        user = User(
            user_id=self._id_factory(),
            email=normalised,
            display_name=name,
            created_at=ts,
            updated_at=ts,
            provider=self.provider_name,
            # For local auth the provider's own subject is the login email; for
            # OIDC this would be the IdP's `sub`. The canonical key stays user_id.
            provider_subject=normalised,
            is_active=True,
            password_hash=self._hash(password),
        )
        self._store.add(user)
        return user

    def authenticate(self, email: str, password: str) -> AuthSession:
        """Verify email + password and return a session principal.

        Always raises the same :class:`InvalidCredentialsError` for unknown
        email, wrong password or inactive account.
        """
        user = self._store.get_by_email(normalize_email(email))
        # Verify against the stored hash when present; for a missing user we still
        # fall through to a uniform failure (no fast-path that leaks existence).
        hash_to_check = user.password_hash if (user and user.password_hash) else None
        password_ok = hash_to_check is not None and self._verify(hash_to_check, password)
        if user is None or not password_ok or not user.is_active:
            raise InvalidCredentialsError("Invalid email or password.")
        return AuthSession.from_user(user)

    # --- account self-management (US-006, US-007) ------------------------

    def _get_or_raise(self, user_id: str) -> User:
        user = self._store.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"No user with id '{user_id}'.")
        return user

    def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> User:
        """Change a user's password after verifying the current one (US-006).

        The change requires the correct ``current_password`` (raising
        :class:`InvalidCredentialsError` otherwise) and the ``new_password`` is
        validated and Argon2id-hashed. The user's canonical ``user_id`` and all
        other fields are unchanged; ``updated_at`` advances.
        """
        user = self._get_or_raise(user_id)
        if not user.password_hash or not self._verify(user.password_hash, current_password):
            raise InvalidCredentialsError("Current password is incorrect.")
        if not isinstance(new_password, str) or new_password == "":
            raise AuthError("A new password is required.")
        updated = dataclasses.replace(
            user,
            password_hash=self._hash(new_password),
            updated_at=self._timestamp(),
        )
        self._store.update(updated)
        return updated

    def update_profile(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        email: str | None = None,
    ) -> User:
        """Edit a user's profile fields (US-007).

        Only the fields passed are changed. Email is normalised and must remain
        unique (the store raises on a clash); changing it does **not** change the
        canonical ``user_id`` — that is the whole point of keeping the internal id
        independent of the login identifier. For the local provider the
        ``provider_subject`` tracks the (normalised) email.
        """
        user = self._get_or_raise(user_id)
        changes: dict[str, object] = {}
        if display_name is not None:
            name = display_name.strip()
            if name == "":
                raise AuthError("Display name cannot be empty.")
            changes["display_name"] = name
        if email is not None:
            normalised = normalize_email(email)
            if normalised == "":
                raise AuthError("A valid email is required.")
            changes["email"] = normalised
            changes["provider_subject"] = normalised
        if not changes:
            return user
        changes["updated_at"] = self._timestamp()
        updated = dataclasses.replace(user, **changes)
        self._store.update(updated)  # raises if the new email collides
        return updated
