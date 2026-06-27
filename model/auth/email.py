"""Mailer abstraction for the identity layer (EPIC-005, US-005).

Email delivery is hidden behind the :class:`Mailer` protocol so the auth domain
never depends on a concrete transport — the same philosophy as the auth provider
abstraction. Two implementations ship here:

- :class:`ConsoleMailer` — writes the message to stdout. The safe default for
  local/dev runs where no SMTP server is configured: the reset link is printed to
  the server console so the flow is fully exercisable offline.
- :class:`SmtpMailer` — sends via SMTP (STARTTLS) using the stdlib. Wired in at
  deployment when an SMTP server is available; constructed from configuration.

Each mailer owns the email's wording **and** the reset-link base URL, so the
provider only hands over the recipient and the raw token. The provider never
learns the deployment URL.
"""

from __future__ import annotations

import smtplib
import sys
from email.message import EmailMessage
from typing import Protocol, runtime_checkable

_SUBJECT = "Reset your UK Policy Sandbox password"


def _reset_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/?reset_token={token}"


def _reset_body(link: str) -> str:
    return (
        "We received a request to reset your UK Policy Sandbox password.\n\n"
        f"Use this link to choose a new password:\n{link}\n\n"
        "This link can be used once and expires shortly. If you did not request "
        "a reset, you can safely ignore this email — your password will not change."
    )


@runtime_checkable
class Mailer(Protocol):
    """Sends transactional auth emails. Implementations own wording + link base."""

    def send_password_reset(self, to_email: str, token: str) -> None:
        """Send a password-reset message containing a link built from ``token``."""
        ...


class ConsoleMailer:
    """Dev/local mailer: prints the reset link instead of sending email.

    No external calls — safe when no SMTP server is configured. Read the server
    console to obtain the reset link.
    """

    def __init__(self, reset_url_base: str = "http://localhost:8501", *, stream=None) -> None:
        self._base = reset_url_base
        self._stream = stream if stream is not None else sys.stdout

    def send_password_reset(self, to_email: str, token: str) -> None:
        link = _reset_link(self._base, token)
        print(
            f"[password-reset] (console mailer — no SMTP configured)\n"
            f"  to:   {to_email}\n"
            f"  link: {link}",
            file=self._stream,
            flush=True,
        )


class SmtpMailer:
    """Sends password-reset email over SMTP with STARTTLS (stdlib only).

    Constructed from deployment configuration. Credentials are optional to
    support relays that authenticate by network/IP.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        reset_url_base: str,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._base = reset_url_base
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._timeout = timeout

    def send_password_reset(self, to_email: str, token: str) -> None:
        message = EmailMessage()
        message["Subject"] = _SUBJECT
        message["From"] = self._sender
        message["To"] = to_email
        message.set_content(_reset_body(_reset_link(self._base, token)))

        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username is not None:
                smtp.login(self._username, self._password or "")
            smtp.send_message(message)
