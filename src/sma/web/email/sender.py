"""Transactional email sender — Resend by default, with a logging fallback for dev.

In production, set `RESEND_API_KEY` and `EMAIL_FROM` (e.g.
`Summit Automates <noreply@summitautomates.com>`). Without those env vars set,
the sender is a no-op that logs the email body so you can copy the magic-link
URL out of the logs during local dev.

We use HTTP directly (not the resend SDK) to avoid the dependency bloat — Resend
is two endpoints.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx
from loguru import logger


@dataclass
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None


class EmailSender(Protocol):
    def send(self, msg: EmailMessage) -> None: ...


class LoggingSender:
    """Dev/test fallback. Just logs the email instead of sending it.

    The magic-link flow inserts URLs into emails — logging them is how you'd
    test signup locally without configuring Resend.
    """

    def send(self, msg: EmailMessage) -> None:
        logger.info(
            "[email-logger] to={to!r} subject={subj!r}\n--- BODY ---\n{body}\n--- END ---",
            to=msg.to, subj=msg.subject, body=msg.text,
        )


class ResendSender:
    """Sends via Resend's HTTPS API. https://resend.com/docs/api-reference/emails/send-email"""

    _API = "https://api.resend.com/emails"

    def __init__(self, api_key: str, from_addr: str) -> None:
        if not api_key:
            raise ValueError("RESEND_API_KEY required")
        if not from_addr:
            raise ValueError("EMAIL_FROM required (e.g. 'Summit Automates <noreply@summitautomates.com>')")
        self._api_key = api_key
        self._from = from_addr

    def send(self, msg: EmailMessage) -> None:
        payload: dict = {
            "from": self._from,
            "to": [msg.to],
            "subject": msg.subject,
            "text": msg.text,
        }
        if msg.html:
            payload["html"] = msg.html
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                self._API,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if r.status_code >= 400:
            logger.error(f"Resend send failed ({r.status_code}): {r.text[:500]}")
            raise RuntimeError(f"Resend rejected the email: {r.status_code}")


_sender: EmailSender | None = None


def get_sender() -> EmailSender:
    """Lazy singleton. Picks Resend if configured; falls back to logging in dev."""
    global _sender
    if _sender is None:
        api_key = os.environ.get("RESEND_API_KEY", "").strip()
        from_addr = os.environ.get("EMAIL_FROM", "").strip()
        if api_key and from_addr:
            _sender = ResendSender(api_key=api_key, from_addr=from_addr)
        else:
            logger.warning(
                "RESEND_API_KEY / EMAIL_FROM not set — using LoggingSender. Magic-link URLs "
                "will appear in stdout instead of being emailed."
            )
            _sender = LoggingSender()
    return _sender


def set_sender(sender: EmailSender) -> None:
    """Test/override hook."""
    global _sender
    _sender = sender


def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    """Top-level convenience. Never raises — logs failure and moves on."""
    try:
        get_sender().send(EmailMessage(to=to, subject=subject, text=text, html=html))
    except Exception as e:
        logger.error(f"send_email to {to!r} failed: {e}")
