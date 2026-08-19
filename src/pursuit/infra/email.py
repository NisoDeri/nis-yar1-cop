"""Gmail sender for match-result emails — group nis-yar1.

Priority: Gmail OAuth (google-auth) → smtplib (secrets/smtp.json) → no-op.
Rate limit: max 6 emails / hour (1 per sub-game, 6 sub-games per series).
"""

from __future__ import annotations

import base64
import json
import logging
import time
from collections import deque
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_TO = "rmisegal+uoh26finalgame@gmail.com"
_MAX_PER_HOUR = 6


def _recipient_list(to: str) -> list[str]:
    """Split a recipient string (one address, or comma-separated many) into envelope addrs.

    A league friendly reports to BOTH teams' inboxes in one send, so ``to`` may carry
    several comma-separated addresses; SMTP needs them as a real list, not one string.
    """
    return [addr.strip() for addr in str(to).split(",") if addr.strip()]

try:
    import google.auth.transport.requests  # type: ignore[import-untyped]
    import google.oauth2.credentials  # type: ignore[import-untyped]
    from googleapiclient.discovery import build as _build  # type: ignore[import-untyped]

    _GOOGLE_OK = True
except ModuleNotFoundError:
    _GOOGLE_OK = False


class _RateLimiter:
    def __init__(self, max_calls: int, window: float = 3600.0) -> None:
        self._max = max_calls
        self._window = window
        self._q: deque[float] = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self._q and now - self._q[0] > self._window:
            self._q.popleft()
        if len(self._q) >= self._max:
            return False
        self._q.append(now)
        return True


def _mime(
    subject: str,
    text: str,
    data: dict[str, Any],
    sender: str | None = None,
    filename: str = "result.json",
) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["Subject"] = subject
    if sender:
        msg["From"] = sender
    msg.attach(MIMEText(text, "plain", "utf-8"))
    # Match the league's established email shape: the body is the entire JSON
    # document and the attachment carries those same UTF-8 bytes.
    att = MIMEApplication(text.encode("utf-8"), _subtype="json")
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)
    return msg


class GmailSender:
    """Send match-result emails; degrade gracefully when credentials are absent."""

    def __init__(
        self,
        token_path: str | Path = "secrets/token.json",
        smtp_path: str | Path = "secrets/smtp.json",
        max_per_hour: int = _MAX_PER_HOUR,
    ) -> None:
        self._token = Path(token_path)
        self._smtp = Path(smtp_path)
        self._rl = _RateLimiter(max_per_hour)

    def send_result(
        self,
        subject: str,
        body_dict: dict[str, Any],
        to: str | None = None,
        sender: str | None = None,
    ) -> dict[str, Any]:
        """Send a match-result email. Returns ``{"sent": bool, "reason": str}``."""
        if not self._rl.allow():
            log.warning("email rate limit (%d/hour) — skipping", _MAX_PER_HOUR)
            return {"sent": False, "reason": "rate_limit"}

        recipient = to or _DEFAULT_TO
        game_id = str(body_dict.get("game_id", "game"))
        body = json.dumps(body_dict, indent=2, ensure_ascii=False)
        msg = _mime(subject, body, body_dict, sender, f"result_{game_id}.json")

        if _GOOGLE_OK and self._token.exists():
            return self._oauth(msg, recipient)
        if not _GOOGLE_OK and self._token.exists():
            log.warning(
                "token.json found but google-auth not installed — "
                "run: uv add google-auth google-api-python-client"
            )
        if self._smtp.exists():
            return self._smtp_send(msg, recipient)
        if not self._token.exists():
            log.warning("no token at %s — email not sent", self._token)
            return {"sent": False, "reason": "no token"}
        return {"sent": False, "reason": "no_credentials"}

    def _oauth(self, msg: MIMEMultipart, to: str) -> dict[str, Any]:
        try:
            d = json.loads(self._token.read_text(encoding="utf-8"))
            creds = google.oauth2.credentials.Credentials(
                token=d.get("token"),
                refresh_token=d.get("refresh_token"),
                token_uri=d.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=d.get("client_id"),
                client_secret=d.get("client_secret"),
                scopes=d.get("scopes"),
            )
            if creds.expired and creds.refresh_token:
                creds.refresh(google.auth.transport.requests.Request())
            msg["To"] = ", ".join(_recipient_list(to))  # Gmail API delivers per the To header
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            _build("gmail", "v1", credentials=creds).users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            log.info("email sent via OAuth to %s", to)
            return {"sent": True, "reason": "oauth"}
        except Exception as exc:  # noqa: BLE001
            log.error("OAuth send failed: %s", exc)
            return {"sent": False, "reason": str(exc)}

    def _smtp_send(self, msg: MIMEMultipart, to: str) -> dict[str, Any]:
        import smtplib

        try:
            c = json.loads(self._smtp.read_text(encoding="utf-8-sig"))
            addrs = _recipient_list(to)  # envelope recipients — a real list, not one string
            msg["To"], msg["From"] = ", ".join(addrs), msg.get("From") or c["user"]
            with smtplib.SMTP(
                c.get("host", "smtp.gmail.com"), int(c.get("port", 587)), timeout=30
            ) as s:
                s.ehlo()
                s.starttls()
                s.login(c["user"], c["password"])
                s.sendmail(c["user"], addrs, msg.as_string())
            log.info("email sent via SMTP to %s", to)
            return {"sent": True, "reason": "smtp"}
        except Exception as exc:  # noqa: BLE001
            log.error("SMTP send failed: %s", exc)
            return {"sent": False, "reason": str(exc)}
