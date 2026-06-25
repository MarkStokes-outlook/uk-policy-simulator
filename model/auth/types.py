"""Core identity types for the auth layer (EPIC-005, v1.1 foundation).

This module defines the *domain* vocabulary for identity — a user record, a
lightweight authenticated session principal, the error hierarchy and email
normalisation. It is deliberately free of any concrete backend (no Streamlit,
no storage, no hashing) so that every auth provider — local, OIDC/Authentik,
Google, Microsoft, GitHub — speaks the same language.

Key design rule: the canonical identifier is the internal ``user_id``, never the
email address. Emails change; ``user_id`` must not. See ``docs/identity.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class AuthError(Exception):
    """Base class for all auth-layer errors.

    Subclasses are written so the UI/app layer can distinguish *why* an
    operation failed without inspecting message strings.
    """


class UserStoreError(AuthError):
    """Raised when the user store or a stored user record is invalid.

    Mirrors :class:`model.saved_models.ModelStoreError`: messages name the
    offending field/user wherever possible so failures are actionable in CI.
    """


class UserExistsError(AuthError):
    """Raised on registration when the email is already in use."""


class InvalidCredentialsError(AuthError):
    """Raised when authentication fails.

    Intentionally does **not** distinguish "no such user" from "wrong password"
    so the provider cannot be used as an account-enumeration oracle.
    """


class UserNotFoundError(AuthError):
    """Raised when a lookup by ``user_id`` finds nothing."""


def normalize_email(email: str) -> str:
    """Return a canonical form of ``email`` for storage and lookup.

    Lower-cased and stripped. This is the form used as the local provider's
    login key and for uniqueness checks, so the *same* address always resolves
    to the *same* account regardless of casing/whitespace.
    """
    if not isinstance(email, str):
        raise UserStoreError(f"Email must be a string (got {email!r}).")
    return email.strip().lower()


@dataclass(frozen=True)
class User:
    """A stored identity record, backend-independent.

    ``user_id`` is the canonical, immutable internal key. ``password_hash`` is
    populated only for password-based providers (it is ``None`` for federated
    providers such as OIDC). ``provider`` / ``provider_subject`` record which
    backend owns the identity and that backend's own identifier for the user
    (for local auth the subject is the normalised email; for OIDC it is the
    ``sub`` claim).
    """

    user_id: str
    email: str
    display_name: str
    created_at: str
    updated_at: str
    provider: str
    provider_subject: str
    is_active: bool = True
    password_hash: str | None = None


@dataclass(frozen=True)
class AuthSession:
    """The principal placed in front-end session state after authentication.

    Deliberately a *projection* of :class:`User` that carries no secret
    material — never the ``password_hash``. This is the only identity object the
    UI layer needs to know "who is logged in".
    """

    user_id: str
    email: str
    display_name: str
    provider: str

    @classmethod
    def from_user(cls, user: User) -> "AuthSession":
        """Build a session principal from a stored :class:`User`."""
        return cls(
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            provider=user.provider,
        )
