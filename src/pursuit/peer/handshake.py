"""Symmetric no-initiator handshake (INTEROP §4) — the game clock starts here.

Both peers concurrently: (1) SEND their signed agreement (built by peer/agreement.py),
retrying every ``network.retry_interval_seconds`` until
``network.connect_timeout_seconds``; (2) RECEIVE the opponent's from the local
agreements inbox under the same deadline; (3) VERIFY terms exact-equality then the
agreement signature — refusal, never bargaining; (4) DERIVE ``game_id``/``game_uid``
independently, zero extra round-trips. D14/rule-37 payloads (Ed25519 pubkey,
counted-games count) ride inside the unsigned identity block and come back in the
:class:`Handshake` result.

Transport/inboxes/clock are injected — unit tests drive this with in-memory queues and
a fake clock (no sockets, no sleeps).
"""

from __future__ import annotations

import queue
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pursuit.domain.game_ids import derive_game_ids
from pursuit.domain.negotiation import verify_agreement_signature, verify_terms
from pursuit.exceptions import CryptoError, DeadlineError, TransportError
from pursuit.peer.agreement import build_agreement_message
from pursuit.shared.config import ConfigManager


class Transport(Protocol):
    """Outbound wire seam: one ``negotiate`` push (may raise TransportError)."""

    def negotiate(self, message: dict[str, Any]) -> None: ...


class Inboxes(Protocol):
    """Local inbound queues; ``agreements`` is queue-like (``get_nowait``/``Empty``)."""

    agreements: Any


@dataclass(frozen=True)
class Handshake:
    """Everything the runtime needs once both peers agreed (INTEROP §4 step 4)."""

    game_id: str
    game_uid: str
    terms: dict[str, Any]
    opponent_identity: dict[str, Any]
    opponent_pubkey: str | None  # PEM text off the wire (D14); None if peer omitted it
    opponent_counted_games: int | None  # rule-37 ledger count; None if peer omitted it


def _send_with_retry(
    transport: Transport, message: dict, deadline: float, retry: float, clock, sleep
) -> None:
    while True:
        try:
            transport.negotiate(message)
            return
        except TransportError as exc:
            if clock() >= deadline:
                raise TransportError(f"opponent MCP server unreachable: {exc}") from exc
            sleep(retry)


def _receive_agreement(inboxes: Inboxes, deadline: float, poll: float, clock, sleep) -> dict:
    while True:
        try:
            message = inboxes.agreements.get_nowait()
        except queue.Empty:
            if clock() >= deadline:
                raise DeadlineError("opponent never sent its agreement") from None
            sleep(poll)
            continue
        if not isinstance(message, dict):
            raise CryptoError(f"malformed agreement message: {type(message).__name__}")
        return message


def run_handshake(
    transport: Transport,
    inboxes: Inboxes,
    config: ConfigManager,
    keypair: tuple[bytes, bytes],
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Handshake:
    """Full symmetric handshake; returns the agreed :class:`Handshake` or refuses.

    Refusal matrix (INTEROP §4): terms mismatch -> NegotiationError (via
    ``verify_terms``, names the first diverging key); bad signature -> CryptoError;
    nothing delivered/received before ``network.connect_timeout_seconds`` ->
    Transport/Deadline error. Duplicate deliveries are tolerated (retries mean the
    queue may hold copies; the first message wins).
    """
    _private_pem, public_pem = keypair
    mine = build_agreement_message(config, public_pem)
    retry = float(config.private("network.retry_interval_seconds"))
    poll = float(config.private("network.poll_interval_seconds"))
    deadline = clock() + float(config.private("network.connect_timeout_seconds"))

    _send_with_retry(transport, mine, deadline, retry, clock, sleep)
    theirs = _receive_agreement(inboxes, deadline, poll, clock, sleep)

    their_terms, their_nonce = theirs.get("terms"), theirs.get("nonce")
    their_signature = theirs.get("signature")
    if not isinstance(their_terms, dict) or not isinstance(their_nonce, str):
        raise CryptoError("agreement message missing terms/nonce")
    verify_terms(mine["terms"], their_terms)  # step 3a — exact equality first
    if not isinstance(their_signature, str) or not verify_agreement_signature(
        their_terms, their_nonce, their_signature
    ):
        raise CryptoError("agreement signature mismatch — refusing to play (INTEROP §4.3b)")

    identity = theirs.get("identity")
    identity = identity if isinstance(identity, dict) else {}
    opponent_gid = identity.get("group_id")
    if not isinstance(opponent_gid, str) or not opponent_gid:
        raise CryptoError("opponent identity missing group_id — cannot derive game ids")
    my_gid = config.private("game.group_id")
    game_id, game_uid = derive_game_ids(their_terms, [my_gid, opponent_gid])
    counted = identity.get("counted_games_so_far")
    return Handshake(
        game_id=game_id,
        game_uid=game_uid,
        terms=their_terms,
        opponent_identity=identity,
        opponent_pubkey=identity.get("ed25519_public_key"),
        opponent_counted_games=counted if isinstance(counted, int) else None,
    )
