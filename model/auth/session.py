"""Framework-agnostic session helpers (EPIC-005, v1.1 foundation).

These helpers manage "who is logged in" inside an arbitrary mutable mapping. The
app passes Streamlit's ``st.session_state`` (which behaves like a
``MutableMapping``), but this module imports **no Streamlit** — keeping all
framework coupling in the UI layer, per the slice's architecture rules. Streamlit
is a temporary, single-process host for multi-user behaviour; isolating it here
means the auth domain survives whatever replaces it.

Only the :class:`AuthSession` principal is stored — never a password hash or the
full :class:`User` record.
"""

from __future__ import annotations

from typing import MutableMapping

from .types import AuthSession

# The single key under which the current principal is stored. Namespaced to avoid
# clashing with the app's own ``st.session_state`` entries.
SESSION_KEY = "auth_session"


def login(state: MutableMapping, session: AuthSession) -> None:
    """Record ``session`` as the current authenticated principal in ``state``."""
    if not isinstance(session, AuthSession):
        raise TypeError("login() expects an AuthSession.")
    state[SESSION_KEY] = session


def logout(state: MutableMapping) -> None:
    """Clear any authenticated principal from ``state`` (idempotent)."""
    state.pop(SESSION_KEY, None)


def current_session(state: MutableMapping) -> AuthSession | None:
    """Return the current :class:`AuthSession`, or ``None`` if not authenticated."""
    session = state.get(SESSION_KEY)
    return session if isinstance(session, AuthSession) else None


def current_user_id(state: MutableMapping) -> str | None:
    """Return the canonical ``user_id`` of the current user, or ``None``.

    This is the value to stamp onto owned resources (e.g. a saved model's
    ``owner_user_id``).
    """
    session = current_session(state)
    return session.user_id if session is not None else None


def is_authenticated(state: MutableMapping) -> bool:
    """Return ``True`` iff ``state`` holds a valid authenticated principal."""
    return current_session(state) is not None
