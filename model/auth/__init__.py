"""Provider-agnostic identity layer for the UK Policy Sandbox (EPIC-005, v1.1).

Public API. The app and tests should import from ``model.auth`` rather than the
individual submodules. The design goal is that nothing outside this package
depends on a *concrete* backend: callers depend on :class:`AuthProvider` /
:class:`PasswordAuthProvider`, and :class:`LocalAuthProvider` is merely the first
implementation. See ``docs/identity.md`` for the rationale.
"""

from .email import ConsoleMailer, Mailer, SmtpMailer
from .local_provider import DEFAULT_RESET_TTL_SECONDS, LocalAuthProvider
from .password import hash_password, needs_rehash, verify_password
from .provider import AuthProvider, PasswordAuthProvider
from .session import (
    SESSION_KEY,
    current_session,
    current_user_id,
    is_authenticated,
    login,
    logout,
)
from .tokens import (
    RESET_TOKENS_SCHEMA_VERSION,
    JsonResetTokenStore,
    ResetToken,
    ResetTokenStore,
    hash_token,
)
from .types import (
    AuthError,
    AuthSession,
    InvalidCredentialsError,
    InvalidResetTokenError,
    User,
    UserExistsError,
    UserNotFoundError,
    UserStoreError,
    normalize_email,
)
from .user_store import AUTH_SCHEMA_VERSION, JsonUserStore, UserStore

__all__ = [
    # Types & errors
    "User",
    "AuthSession",
    "AuthError",
    "UserStoreError",
    "UserExistsError",
    "InvalidCredentialsError",
    "UserNotFoundError",
    "InvalidResetTokenError",
    "normalize_email",
    # Password utilities
    "hash_password",
    "verify_password",
    "needs_rehash",
    # Provider interfaces + local backend
    "AuthProvider",
    "PasswordAuthProvider",
    "LocalAuthProvider",
    # Storage
    "UserStore",
    "JsonUserStore",
    "AUTH_SCHEMA_VERSION",
    # Password reset (US-005)
    "ResetToken",
    "ResetTokenStore",
    "JsonResetTokenStore",
    "RESET_TOKENS_SCHEMA_VERSION",
    "hash_token",
    "DEFAULT_RESET_TTL_SECONDS",
    "Mailer",
    "ConsoleMailer",
    "SmtpMailer",
    # Session helpers
    "SESSION_KEY",
    "login",
    "logout",
    "current_session",
    "current_user_id",
    "is_authenticated",
]
