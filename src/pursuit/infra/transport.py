"""OpponentTransport — outbound MCP streamable-HTTP client for the 4 league tools.

INTEROP §1: fresh session per call on the opponent's ``/mcp`` URL; argument key
``message`` (``submit_audit`` alone: ``payload``). Every send retries each
``retry_interval`` seconds until its per-tool deadline: negotiate/receive_turn
fail hard (TransportError); submit_audit/receive_control suppress to ``None``.
Wire caller + ``timeouts`` dict are injected: no sockets in tests, no ConfigManager.
"""

from __future__ import annotations

import json
import os
import time
from functools import partialmethod
from typing import Any, Protocol

import httpx

from pursuit.exceptions import ConfigError, TransportError


def _tls_verify() -> bool:
    """Whether to verify the opponent's TLS cert (default True). Set ``PURSUIT_TLS_VERIFY=0``
    on a TLS-intercepting network (e.g. a corporate MITM proxy) where the peer cannot chain
    the re-signed cert — game integrity is Ed25519 + commit-reveal, never transport TLS, so
    the opt-in bypass never weakens the match, only the transport wrapper the crypto replaces.
    """
    return os.environ.get("PURSUIT_TLS_VERIFY", "1").strip().lower() not in {"0", "false", "no"}

REQUIRED_TIMEOUT_KEYS = ("retry_interval", "connect_timeout", "audit_timeout", "control_timeout")
#: tool -> (argument key, deadline key in timeouts, suppress errors on expiry?)
TOOL_SPEC: dict[str, tuple[str, str, bool]] = {
    "negotiate": ("message", "connect_timeout", False),
    "receive_turn": ("message", "connect_timeout", False),
    "submit_audit": ("payload", "audit_timeout", True),
    "receive_control": ("message", "control_timeout", True),
}
_PROTOCOL_VERSION = "2025-06-18"
_BASE_HEADERS = {"content-type": "application/json",
                 "accept": "application/json, text/event-stream"}


class TransportBase(Protocol):
    """What the peer runtime needs from any transport (real or fake)."""

    def negotiate(self, message: dict) -> dict | None: ...  # noqa: E704
    def receive_turn(self, message: dict) -> dict | None: ...  # noqa: E704
    def submit_audit(self, payload: dict) -> dict | None: ...  # noqa: E704
    def receive_control(self, message: dict) -> dict | None: ...  # noqa: E704


def rpc_result(response: Any, rpc_id: int) -> dict:
    """The JSON-RPC result for ``rpc_id`` out of a JSON or SSE response body."""
    if getattr(response, "status_code", 200) >= 400:
        raise TransportError(f"HTTP {response.status_code} from MCP endpoint")
    if "text/event-stream" in response.headers.get("content-type", ""):
        messages = [json.loads(line[5:].strip())
                    for line in response.text.splitlines() if line.startswith("data:")]
    else:
        messages = [json.loads(response.text)]
    for msg in messages:
        if msg.get("id") == rpc_id and "error" in msg:
            raise TransportError(f"MCP error reply: {msg['error']}")
        if msg.get("id") == rpc_id and "result" in msg:
            return msg["result"]
    raise TransportError("no JSON-RPC result in streamable-HTTP response")


def tool_ack(result: dict) -> dict:
    """The ack dict (INTEROP: ``{"ok": true}``) out of a tools/call result."""
    if result.get("isError"):
        raise TransportError(f"tool call failed remotely: {result}")
    if isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]
    for block in result.get("content", []):
        if block.get("type") == "text":
            return json.loads(block["text"])
    return {}


def http_call_tool(url: str, tool: str, arguments: dict, timeout: float) -> dict:
    """One full MCP session over httpx: initialize → initialized → tools/call."""
    headers = dict(_BASE_HEADERS)
    with httpx.Client(timeout=timeout, verify=_tls_verify()) as client:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": _PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "pursuit", "version": "0.1.0"}}}
        response = client.post(url, json=init, headers=headers)
        rpc_result(response, 1)  # raises TransportError on a bad handshake
        if response.headers.get("mcp-session-id"):
            headers["mcp-session-id"] = response.headers["mcp-session-id"]
        client.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                    headers=headers)
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool, "arguments": arguments}}
        return tool_ack(rpc_result(client.post(url, json=call, headers=headers), 2))


class OpponentTransport:
    """Retrying MCP client toward the opponent's server (implements TransportBase)."""

    def __init__(self, opponent_url: str, timeouts: dict[str, Any], *,
                 caller: Any = None, sleep: Any = time.sleep, clock: Any = time.monotonic):
        missing = [key for key in REQUIRED_TIMEOUT_KEYS if key not in timeouts]
        if missing:
            raise ConfigError(f"transport timeouts missing keys: {missing}")
        self._url = opponent_url
        self._t = {key: float(timeouts[key]) for key in REQUIRED_TIMEOUT_KEYS}
        self._caller = caller if caller is not None else http_call_tool
        self._sleep, self._clock = sleep, clock

    def _send(self, tool: str, body: dict) -> dict | None:
        arg_key, deadline_key, suppress = TOOL_SPEC[tool]
        budget, interval = self._t[deadline_key], self._t["retry_interval"]
        deadline = self._clock() + budget
        while True:
            remaining = deadline - self._clock()
            try:
                return self._caller(self._url, tool, {arg_key: body}, max(remaining, interval))
            except (httpx.HTTPError, TransportError, OSError) as exc:
                if self._clock() + interval >= deadline:
                    if suppress:
                        return None
                    raise TransportError(
                        f"Opponent MCP server unreachable: {tool} kept failing "
                        f"within its {budget:g}s deadline ({exc})"
                    ) from exc
                self._sleep(interval)

    negotiate = partialmethod(_send, "negotiate")
    receive_turn = partialmethod(_send, "receive_turn")
    submit_audit = partialmethod(_send, "submit_audit")
    receive_control = partialmethod(_send, "receive_control")


class FakeTransport:
    """In-memory TransportBase — delivers straight into the OPPONENT's inboxes."""

    _CHANNEL = {"negotiate": "negotiation", "receive_turn": "turns",
                "submit_audit": "audits", "receive_control": "controls"}

    def __init__(self, opponent_inboxes: Any) -> None:
        self.opponent_inboxes = opponent_inboxes
        self.sent: list[tuple[str, dict]] = []

    @classmethod
    def pair(cls, inboxes_a: Any, inboxes_b: Any) -> tuple[FakeTransport, FakeTransport]:
        """Two transports wired crosswise: A sends into B's inboxes, B into A's."""
        return cls(inboxes_b), cls(inboxes_a)

    def _deliver(self, tool: str, body: dict) -> dict:
        self.sent.append((tool, body))
        self.opponent_inboxes.channel(self._CHANNEL[tool]).put(body)
        return {"ok": True}

    negotiate = partialmethod(_deliver, "negotiate")
    receive_turn = partialmethod(_deliver, "receive_turn")
    submit_audit = partialmethod(_deliver, "submit_audit")
    receive_control = partialmethod(_deliver, "receive_control")
