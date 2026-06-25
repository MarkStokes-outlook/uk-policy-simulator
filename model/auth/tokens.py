"""Password-reset tokens: storage + hashing (EPIC-005, US-005).

A reset token is a high-entropy, single-use, time-limited secret. Following
industry practice we **never store the raw token** — only a SHA-256 hash of it,
exactly as one would never store a raw session token or API key. Because the
token itself is 256 bits of randomness (see :func:`secrets.token_urlsafe` use in
the provider), a fast cryptographic hash is the correct choice here — unlike
*passwords*, which are low-entropy and need a slow KDF (Argon2id, see
``password.py``).

Single-use is enforced by deleting a user's tokens on completion; expiry is
enforced by `expires_at`. The store mirrors the user store: a single versioned
JSON file, validate-on-read, atomic writes. It holds only hashes, but is treated
as secrets data and gitignored all the same.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

from .types import UserStoreError

# Bump when the on-disk reset-token schema changes shape.
RESET_TOKENS_SCHEMA_VERSION = 1


def hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest used to store/look up a reset token.

    The raw token is high-entropy, so SHA-256 (fast, no salt) is appropriate and
    standard; the stored hash is useless to an attacker without the raw token.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResetToken:
    """A stored password-reset token (hash only) bound to a user and a window."""

    token_hash: str
    user_id: str
    created_at: str
    expires_at: str

    def is_expired(self, now: datetime) -> bool:
        """True if ``now`` (an aware datetime) is at/after the expiry instant.

        Parsing goes through :func:`_parse_timestamp`, so a corrupt stored
        ``expires_at`` surfaces as a controlled :class:`UserStoreError` rather
        than a raw ``ValueError`` — keeping the reset flow on its uniform failure
        path even if it is handed a token built from bad data.
        """
        return now >= _parse_timestamp(self.expires_at, "expires_at")


@runtime_checkable
class ResetTokenStore(Protocol):
    """Repository for reset tokens, keyed by token hash."""

    def add(self, token: ResetToken) -> None:
        """Persist a new token."""
        ...

    def get_by_hash(self, token_hash: str) -> ResetToken | None:
        """Return the token with this hash, or ``None``."""
        ...

    def invalidate_for_user(self, user_id: str) -> None:
        """Delete **all** tokens for a user (used to enforce single-use / reissue)."""
        ...


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise UserStoreError(message)


def _parse_timestamp(value: str, field_name: str) -> datetime:
    """Parse a timezone-aware ISO-8601 timestamp, converting bad data to a
    controlled error.

    Stored reset-token timestamps must be **timezone-aware** ISO strings. Two
    classes of corrupt ``reset_tokens.json`` data are rejected here as
    :class:`UserStoreError` so callers keep their uniform-failure guarantees:

    * unparseable strings (e.g. ``"not-a-date"``), and
    * ISO-parseable but **offset-naive** timestamps (e.g.
      ``"2026-01-01T00:00:00"``). A naive datetime cannot be compared against the
      provider's aware UTC ``now`` and would otherwise escape as a raw
      ``TypeError`` from :meth:`ResetToken.is_expired`, bypassing the auth error
      path. We reject rather than normalise: the schema requires an explicit
      offset, so a missing one is corrupt stored data, not a value to guess at.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise UserStoreError(
            f"Reset token field '{field_name}' is not a valid ISO-8601 datetime "
            f"(got {value!r})."
        ) from exc
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise UserStoreError(
            f"Reset token field '{field_name}' must be a timezone-aware ISO-8601 "
            f"datetime (got offset-naive {value!r})."
        )
    return parsed


def _token_to_dict(t: ResetToken) -> dict[str, object]:
    return {
        "token_hash": t.token_hash,
        "user_id": t.user_id,
        "created_at": t.created_at,
        "expires_at": t.expires_at,
    }


def _token_from_dict(raw: object) -> ResetToken:
    _require(isinstance(raw, dict), "Each reset token must be a mapping.")
    assert isinstance(raw, dict)
    for field_name in ("token_hash", "user_id", "created_at", "expires_at"):
        value = raw.get(field_name)
        _require(
            isinstance(value, str) and value != "",
            f"Reset token is missing '{field_name}'.",
        )
    # Validate-on-read: timestamps must be *parseable*, not merely non-empty
    # strings, so corrupt data is rejected here (as UserStoreError) rather than
    # exploding later as a raw ValueError inside ResetToken.is_expired().
    _parse_timestamp(raw["created_at"], "created_at")
    _parse_timestamp(raw["expires_at"], "expires_at")
    return ResetToken(
        token_hash=raw["token_hash"],
        user_id=raw["user_id"],
        created_at=raw["created_at"],
        expires_at=raw["expires_at"],
    )


class JsonResetTokenStore:
    """File-backed :class:`ResetTokenStore`, single-process/local by design."""

    def __init__(self, path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, ResetToken]:
        if not self.path.exists():
            return {}
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UserStoreError(f"Could not parse reset-tokens file '{self.path}': {exc}") from exc
        except OSError as exc:
            raise UserStoreError(f"Could not read reset-tokens file '{self.path}': {exc}") from exc

        _require(isinstance(doc, dict), f"Reset-tokens file '{self.path}' must be a JSON object.")
        version = doc.get("schema_version")
        _require(
            version == RESET_TOKENS_SCHEMA_VERSION,
            f"Unsupported reset-tokens schema_version {version!r} in '{self.path}' "
            f"(this build supports {RESET_TOKENS_SCHEMA_VERSION}).",
        )
        raw_tokens = doc.get("tokens", [])
        _require(isinstance(raw_tokens, list), f"Reset-tokens file '{self.path}': 'tokens' must be a list.")

        tokens: dict[str, ResetToken] = {}
        for raw in raw_tokens:
            token = _token_from_dict(raw)
            tokens[token.token_hash] = token
        return tokens

    def _write(self, tokens: Mapping[str, ResetToken]) -> None:
        doc = {
            "schema_version": RESET_TOKENS_SCHEMA_VERSION,
            "tokens": [_token_to_dict(t) for t in tokens.values()],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def add(self, token: ResetToken) -> None:
        tokens = self._read()
        tokens[token.token_hash] = token
        self._write(tokens)

    def get_by_hash(self, token_hash: str) -> ResetToken | None:
        return self._read().get(token_hash)

    def invalidate_for_user(self, user_id: str) -> None:
        tokens = self._read()
        remaining = {h: t for h, t in tokens.items() if t.user_id != user_id}
        if len(remaining) != len(tokens):
            self._write(remaining)
