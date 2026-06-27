"""Password hashing utilities (EPIC-005, v1.1 foundation).

Thin wrappers over **argon2-cffi** — a vetted, memory-hard password hashing
library. We do **not** roll our own hashing or store plaintext: these functions
are the only sanctioned way to turn a password into a stored hash and to check
one. Argon2id (the library default) is the current OWASP-recommended choice.

The hashing parameters live with the library defaults intentionally: pinning the
``argon2-cffi`` version (see ``requirements.txt``) pins the defaults, and
:func:`needs_rehash` lets us transparently upgrade parameters on a future login
without a migration.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import (
    HashingError,
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

# A single, shared hasher with library-default (Argon2id) parameters. Reused so
# we don't pay construction cost per call; argon2 PasswordHasher is stateless and
# safe to share.
_DEFAULT_HASHER = PasswordHasher()


def hash_password(password: str, *, hasher: PasswordHasher | None = None) -> str:
    """Hash ``password`` with Argon2id and return an encoded hash string.

    The returned string embeds the algorithm, parameters and a per-hash random
    salt, so two calls with the same password yield *different* hashes. Raises
    :class:`ValueError` for an empty/non-string password and re-raises argon2's
    :class:`~argon2.exceptions.HashingError` on backend failure.
    """
    if not isinstance(password, str) or password == "":
        raise ValueError("Password must be a non-empty string.")
    return (hasher or _DEFAULT_HASHER).hash(password)


def verify_password(
    password_hash: str, password: str, *, hasher: PasswordHasher | None = None
) -> bool:
    """Return ``True`` iff ``password`` matches ``password_hash``.

    A wrong password, a malformed/corrupt hash, or an empty input all return
    ``False`` rather than raising — callers decide what an authentication
    failure means. Use :func:`needs_rehash` after a successful verify to detect
    when the stored hash should be upgraded.
    """
    if not isinstance(password_hash, str) or not isinstance(password, str):
        return False
    try:
        return (hasher or _DEFAULT_HASHER).verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError, HashingError):
        return False


def needs_rehash(password_hash: str, *, hasher: PasswordHasher | None = None) -> bool:
    """Return ``True`` if ``password_hash`` was made with outdated parameters.

    Lets a future login re-hash a still-valid password under stronger settings
    without forcing a reset. Treats an unreadable hash as needing a rehash.
    """
    try:
        return (hasher or _DEFAULT_HASHER).check_needs_rehash(password_hash)
    except InvalidHashError:
        return True
