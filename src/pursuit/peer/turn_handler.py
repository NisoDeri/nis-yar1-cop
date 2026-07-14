"""TurnHandler — fold one opponent TurnMessage into MY local truth (Zero-Trust gate).

Everything is validated against MY replica of the shared physics BEFORE any mutation
(rules 4-5): envelope, sender, step sequence (retries legally duplicate — a seen step drops
idempotently, INTEROP §1), role-legal claim fields, barrier legality (A3), smell geometry.
A violation takes the breach path (counted, surfaced); ``max_breaches`` consecutive
rejects end the sub-game (``technical_loss`` 0/0, D4). Valid messages fold in seam order
(STRATEGY §2.4): truthful barrier (rule 14) -> scent ``absorb`` -> belief PREDICT
(``diffuse`` on MY cell) -> UPDATE (``observe_smell``); hint/capture-claim stashed for the
brain/sender; ``capture_claim`` answered TRUTHFULLY (rule 21); rules 46-47 self-detected.
Each valid opponent ``commit`` is retained to bind live vs revealed at the end-game audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pursuit.constants import Cell, Role
from pursuit.domain import rules
from pursuit.domain.protocol import TurnMessage
from pursuit.exceptions import TransportError
from pursuit.peer.fsm import ALLOWED, State

TURN, DUPLICATE, BREACH = "turn", "duplicate", "breach"


@dataclass(frozen=True)
class ProcessedTurn:
    """One inbound message, digested — everything the runtime and the brain need."""

    kind: str  # "turn" | "duplicate" | "breach"
    step: int
    hint: str = ""
    claim_response_due: dict[str, Any] | None = None  # attach to MY next TurnMessage
    captured: str | None = None  # I am caught: "landing" | "barrier" | "jailed"
    opponent_caught: bool = False  # their claim_response confirmed MY capture claim
    survival_claimed: bool = False  # opponent's validated survival win_claim
    barrier_cell: Cell | None = None
    breach_reason: str | None = None
    game_over: bool = False


def _cell(value: Any, board: Any, label: str) -> Cell:
    """Validated wire ``[r, c]`` -> in-bounds Cell; TransportError otherwise."""
    ok = (isinstance(value, list | tuple) and len(value) == 2
          and all(isinstance(v, int) and not isinstance(v, bool) for v in value))
    if not ok or not board.in_bounds((value[0], value[1])):
        raise TransportError(f"{label} must be an in-bounds [row, col], got {value!r}")
    return (value[0], value[1])


class TurnHandler:
    """Per-sub-game inbound gate: dedup -> validate -> fold -> FSM advance."""

    def __init__(self, role: Role | str, *, survival_threshold: int, barriers_max: int,
                 max_breaches: int) -> None:  # limits arrive from the signed shared config
        self.role, self.opponent = Role(role), Role(role).opponent
        self.survival_threshold, self.barriers_max = int(survival_threshold), int(barriers_max)
        self.max_breaches = int(max_breaches)
        self.last_step, self.last_hint = 0, ""  # dedup key + stashed brain intake (§2.5)
        self.opponent_barriers, self.breaches, self.commits = 0, 0, {}  # commits: step->wire commit

    def process(self, message: TurnMessage | dict[str, Any], own_state: Any, belief: Any,
                scent_reader: Any, fsm: Any) -> ProcessedTurn:
        """Digest one inbound turn; mutations happen only after EVERY check passed."""
        try:
            msg = message if isinstance(message, TurnMessage) else TurnMessage.from_wire(message)
        except TransportError as exc:
            return self._breach(fsm, self.last_step, f"envelope: {exc}")
        if msg.step <= self.last_step:
            return ProcessedTurn(kind=DUPLICATE, step=msg.step, hint=msg.hint)
        try:
            barrier, response = self._validate(msg, own_state, fsm)
            scent_reader.absorb(msg.smell_grid)  # validates + mirrors the authoritative trail
        except (TransportError, ValueError) as exc:
            return self._breach(fsm, msg.step, str(exc))
        self.last_step, self.last_hint, self.breaches = msg.step, msg.hint, 0
        self.commits[msg.step] = msg.commit  # bind live commit -> checked vs reveal at audit
        if barrier is not None:
            own_state.note_opponent_barrier(barrier)  # truthful by rule 14
            self.opponent_barriers += 1
            if hasattr(belief, "note_barrier"):
                belief.note_barrier(barrier)
        belief.diffuse(self.opponent, own_state.position)  # PREDICT: they react to ME
        belief.observe_smell(msg.smell_grid)  # UPDATE: emission inversion (STRATEGY §2.4)
        captured, response = self._captured(response, barrier, own_state)
        opponent_caught = bool(msg.claim_response and msg.claim_response.get("caught"))
        survival = msg.win_claim is not None
        game_over = opponent_caught or survival
        fsm.advance(State.GAME_OVER if game_over else State.MY_TURN)
        return ProcessedTurn(kind=TURN, step=msg.step, hint=msg.hint, barrier_cell=barrier,
                             claim_response_due=response, captured=captured, game_over=game_over,
                             opponent_caught=opponent_caught, survival_claimed=survival)

    def _validate(self, msg: TurnMessage, own_state: Any,
                  fsm: Any) -> tuple[Cell | None, dict[str, Any] | None]:
        """Protocol + physics checks — pure: raises TransportError, mutates nothing."""
        if msg.sender != self.opponent.value:
            raise TransportError(f"sender must be {self.opponent.value!r}, got {msg.sender!r}")
        if msg.step != self.last_step + 1:
            raise TransportError(f"step {msg.step} breaks sequence, expected {self.last_step + 1}")
        if fsm.state is not State.OPP_TURN:
            raise TransportError(f"turn message while my FSM is {fsm.state.value}")
        forbidden = ((msg.claim_response, msg.win_claim) if self.opponent is Role.POLICE
                     else (msg.barrier_placed, msg.capture_claim))
        if any(field is not None for field in forbidden):
            raise TransportError(f"{msg.sender} sent a claim field reserved for the other role")
        barrier = response = None
        if msg.barrier_placed is not None:
            if self.opponent_barriers >= self.barriers_max:
                raise TransportError(f"opponent barrier quota exhausted ({self.barriers_max})")
            barrier = _cell(msg.barrier_placed, own_state.board, "barrier_placed")
            if barrier in own_state.barriers:
                raise TransportError(f"barrier_placed {barrier} is already barriered")
        if msg.capture_claim is not None:  # rule 21: answer truthfully from MY own state
            claim = _cell(msg.capture_claim, own_state.board, "capture_claim")
            response = {"claim": list(claim),
                        "caught": rules.capture_by_landing(claim, own_state.position)}
        if msg.claim_response is not None and not (isinstance(msg.claim_response, dict)
                and isinstance(msg.claim_response.get("caught"), bool)):
            raise TransportError(f"malformed claim_response {msg.claim_response!r}")
        if msg.win_claim is not None:
            if not isinstance(msg.win_claim, dict) or msg.win_claim.get("type") != "survival":
                raise TransportError(f"unknown win_claim {msg.win_claim!r}")
            if msg.step < self.survival_threshold:  # ruling A5: their OWN counter is the clock
                raise TransportError(f"win_claim before step {self.survival_threshold}")
        return barrier, response

    def _captured(self, response: dict[str, Any] | None, barrier: Cell | None,
                  own_state: Any) -> tuple[str | None, dict[str, Any] | None]:
        """Rules 46-47 self-detection; every capture yields a truthful concession answer."""
        if self.role is not Role.THIEF:
            return None, response
        if response is not None and response["caught"]:
            return "landing", response
        if barrier is not None:
            if rules.capture_by_barrier(barrier, own_state.position):
                return "barrier", {"claim": list(barrier), "caught": True}
            if rules.jailed(own_state.board, own_state.position, own_state.barriers):
                return "jailed", {"claim": list(own_state.position), "caught": True}
        return None, response

    def _breach(self, fsm: Any, step: int, reason: str) -> ProcessedTurn:
        """Rule-5 path: reject + count; K consecutive breaches end the sub-game (D4)."""
        self.breaches += 1
        fatal = self.breaches >= self.max_breaches
        if fatal and State.GAME_OVER in ALLOWED[fsm.state]:
            fsm.advance(State.GAME_OVER)
        return ProcessedTurn(kind=BREACH, step=step, breach_reason=reason, game_over=fatal)
