"""FastMCP HTTP server — one per peer, exposing the 4 frozen league tools.

INTEROP §2: tool names, argument keys and ack shapes are FROZEN (D1).
The tools carry ZERO game logic: each validates only the argument's shape,
pushes it onto the matching :class:`PeerInboxes` channel and returns
``{"ok": true}`` unconditionally — ALL enforcement (physics, crypto, schema)
happens in the consuming runtime (INTEROP §1). ``submit_audit`` takes
``payload``; the other three take ``message`` (the one asymmetry, §2.3).
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from pursuit.exceptions import TransportError
from pursuit.peer.inboxes import PeerInboxes

#: The unconditional ack every tool returns (INTEROP §1 call convention).
ACK: dict[str, bool] = {"ok": True}

TOOL_NAMES: tuple[str, ...] = ("negotiate", "receive_turn", "submit_audit", "receive_control")


def _require_object(tool: str, key: str, value: Any) -> None:
    """Shape gate — the argument must be a JSON object (dict); nothing deeper."""
    if not isinstance(value, dict):
        raise TypeError(f"{tool}: '{key}' must be a JSON object, got {type(value).__name__}")


def make_handlers(inboxes: PeerInboxes) -> dict[str, Callable[..., dict[str, bool]]]:
    """The four tool handlers as PLAIN functions — unit-testable before .run()."""

    def negotiate(message: dict) -> dict:
        """Receive the opponent's signed agreement (INTEROP §2.1)."""
        _require_object("negotiate", "message", message)
        inboxes.negotiation.put(message)
        return dict(ACK)

    def receive_turn(message: dict) -> dict:
        """Receive a TurnMessage — the implicit turn token (INTEROP §2.2)."""
        _require_object("receive_turn", "message", message)
        inboxes.turns.put(message)
        return dict(ACK)

    def submit_audit(payload: dict) -> dict:
        """Receive the end-of-sub-game AuditPayload (INTEROP §2.3, key=payload)."""
        _require_object("submit_audit", "payload", payload)
        inboxes.audits.put(payload)
        return dict(ACK)

    def receive_control(message: dict) -> dict:
        """Advisory control channel (INTEROP §2.4) — never part of the record."""
        _require_object("receive_control", "message", message)
        inboxes.controls.put(message)
        return dict(ACK)

    return {
        "negotiate": negotiate,
        "receive_turn": receive_turn,
        "submit_audit": submit_audit,
        "receive_control": receive_control,
    }


def ensure_port_free(
    host: str, port: int, probe_factory: Callable[[], Any] = socket.socket
) -> None:
    """Preflight: refuse to start where a stale peer is still bound (INTEROP §1)."""
    probe = probe_factory()
    try:
        probe.bind((host, port))
    except OSError as exc:
        raise TransportError(
            f"port already in use: {host}:{port} — is a stale peer still bound?"
        ) from exc
    finally:
        probe.close()


class PeerMcpServer:
    """Own-side FastMCP streamable-HTTP server (`police-thief-<role>`, path /mcp)."""

    def __init__(self, role: str, host: str, port: int, inboxes: PeerInboxes,
                 stateless: bool = False) -> None:
        self.role = role
        self.host = host
        self.port = port
        # stateless_http (opt-in per opponent): don't require an mcp-session-id header on
        # follow-up calls — some peers (e.g. najamjad) initialize but don't echo the session
        # id, which our stateful default rejects with 400 "Missing session ID". Our game state
        # lives in the runtime, not the MCP session, so stateless is safe. DEFAULT is stateful:
        # reference-kit peers (e.g. vm__fabi) require a bare GET to answer 406 (their T-protocol
        # kills the game otherwise); stateful FastMCP returns 406, stateless returns 405.
        self.stateless = bool(stateless)
        self.handlers = make_handlers(inboxes)
        self.mcp = FastMCP(f"police-thief-{role}")
        for name, handler in self.handlers.items():
            self.mcp.tool(handler, name=name)

    def start(self) -> threading.Thread:
        """Probe the port, then serve streamable-HTTP on a daemon thread."""
        ensure_port_free(self.host, self.port)
        thread = threading.Thread(
            target=self.mcp.run,
            kwargs={"transport": "http", "host": self.host, "port": self.port,
                    "show_banner": False, "stateless_http": self.stateless},
            name=f"mcp-server-{self.role}",
            daemon=True,
        )
        thread.start()
        return thread
