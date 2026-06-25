"""Provider-agnostic auth interfaces (EPIC-005, v1.1 foundation).

The application depends on these *protocols*, never on a concrete backend. This
is what keeps us from being locked into Streamlit-local auth: a future
OIDC/Authentik, Google, Microsoft or GitHub provider implements the same
:class:`AuthProvider` surface and the rest of the platform is unchanged.

Two protocols, because not all providers authenticate the same way:

- :class:`AuthProvider` — the universal surface every backend shares (identify a
  user by canonical ``user_id``, report its provider name).
- :class:`PasswordAuthProvider` — adds password registration/authentication. The
  local backend implements this. A federated provider would instead implement a
  redirect/callback protocol (an ``OIDCAuthProvider`` defined when that work
  lands), still satisfying :class:`AuthProvider`.

Splitting them avoids forcing a single ``authenticate()`` signature onto two
fundamentally different flows (password vs. authorization-code).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import AuthSession, User


@runtime_checkable
class AuthProvider(Protocol):
    """The minimal surface shared by every identity backend."""

    @property
    def provider_name(self) -> str:
        """Stable key for this backend, e.g. ``"local"``, ``"oidc"``, ``"google"``."""
        ...

    def get_user(self, user_id: str) -> User | None:
        """Resolve a stored user by canonical ``user_id``, or ``None``."""
        ...


@runtime_checkable
class PasswordAuthProvider(AuthProvider, Protocol):
    """An :class:`AuthProvider` that authenticates with an email + password."""

    def register(
        self, email: str, password: str, display_name: str | None = None
    ) -> User:
        """Create a new user and return the stored record.

        Raises :class:`model.auth.types.UserExistsError` if the email is taken.
        """
        ...

    def authenticate(self, email: str, password: str) -> AuthSession:
        """Verify credentials and return a session principal.

        Raises :class:`model.auth.types.InvalidCredentialsError` on any failure
        (unknown email, wrong password or inactive account) without revealing
        which, to avoid account enumeration.
        """
        ...

    def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> User:
        """Change a user's password, verifying ``current_password`` first.

        Raises :class:`model.auth.types.InvalidCredentialsError` if the current
        password is wrong.
        """
        ...

    def update_profile(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        email: str | None = None,
    ) -> User:
        """Edit a user's profile fields, leaving the canonical ``user_id`` intact."""
        ...
