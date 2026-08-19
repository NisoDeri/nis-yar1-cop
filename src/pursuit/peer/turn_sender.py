"""TurnSender — decide, guard, apply, seal, send one of MY turns (INTEROP §2.2, rules 14/21/26-27).

Guardrail order (STRATEGY §8): the decision is validated against the SAME rules the handler
applies to the opponent — an illegal move is NEVER sent; it degrades to the first legal move
(flagged ``random_move``) or the jailed-HOLD backstop. ``barrier_placed``/``capture_claim`` come
from the APPLIED move, not brain claims (rule 14); the hint is linted BEFORE sealing (wire ==
audited bytes). Step accounting per A5: MOVE/HOLD/BARRIER each consume one MY step. A truthful
``claim_response`` caught:true is the concession (sealed HOLD + "You got me."). The brain runs
under a wall-clock bound (peer/brain_clock) so a hang degrades to a safe HOLD. Fresh per sub-game.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pursuit.constants import DIRECTION_DELTAS, Cell, Direction, MoveType, Role
from pursuit.domain import rules
from pursuit.domain.protocol import CAPTURE_CONCESSION_HINT, SILENCE_HINT, TurnMessage
from pursuit.domain.protocol_audit import INTENTS, format_move_string, sealed_payload
from pursuit.exceptions import IllegalMoveError, IllegalTransitionError
from pursuit.peer.brain_clock import decide_bounded
from pursuit.peer.fsm import State


def lint_hint(text: Any, hint_max_words: int) -> str:
    """Mechanical rules 26-27 gate: drop digit-bearing words, cap the words, never empty."""
    words = [w for w in str(text).split() if not any(ch.isdigit() for ch in w)]
    return " ".join(words[:hint_max_words]) or SILENCE_HINT


@dataclass(frozen=True)
class SentTurn:
    """What one of my turns produced — the runtime's (and the tests') one-stop summary."""

    step: int
    message: TurnMessage
    record: dict[str, Any]  # the sealed local record (nonce stays local, rule 18)
    move_type: MoveType
    direction: Direction | None
    barrier_cell: Cell | None
    random_move: bool
    terminal: bool  # I just conceded a capture or claimed survival


class TurnSender:
    """One peer's outbound turn pipeline for a single sub-game."""

    def __init__(self, role: Role | str, *, barriers_max: int, survival_threshold: int,
                 hint_max_words: int, setting: str, brain_deadline: float | None = None,
                 model: str = "stub", now: Any = None) -> None:
        self.role = Role(role)  # every game parameter arrives from the signed config
        self.barriers_max, self.survival_threshold = int(barriers_max), int(survival_threshold)
        self.hint_max_words, self.setting = int(hint_max_words), setting
        self.brain_deadline = brain_deadline  # wall-clock bound on the move (peer/brain_clock)
        self.model = str(model or "stub")
        self.step_counter = rules.StepCounter()  # MY turn clock — ruling A5 semantics
        self._now = now or (lambda: datetime.now(UTC).isoformat())

    def take_turn(self, brain: Any, own_state: Any, belief: Any, scent_mine: Any, sealer: Any,
                  transport: Any, fsm: Any, opponent_hint: str | None, *,
                  claim_response: dict[str, Any] | None = None,
                  deadline_seconds: float | None = None) -> SentTurn:
        """decide -> guard -> apply -> scent -> lint -> seal -> compose -> send -> FSM."""
        if fsm.state is not State.MY_TURN:  # fail BEFORE any mutation (rule 5)
            raise IllegalTransitionError(f"take_turn requires MY_TURN, FSM is {fsm.state.value}")
        concede = bool(claim_response and claim_response.get("caught"))
        if concede:  # rule 21 concession: no brain on this path, the fixed literal travels
            move_type, direction, random_move = MoveType.HOLD, None, False
            hint, verdict, reasoning, prompt, seconds = (
                CAPTURE_CONCESSION_HINT, "truth", "capture concession (rule 21)", "", 0.0)
        else:
            args = (own_state, belief, opponent_hint or "", self.setting, self.barriers_max)
            decision = decide_bounded(brain, (*args, deadline_seconds), self.brain_deadline)
            verdict = decision.verdict if decision.verdict in INTENTS else "truth"
            hint, reasoning, prompt = decision.hint, decision.reasoning, decision.prompt_text
            seconds = decision.response_seconds
            move_type, direction, random_move = self._guard(decision, own_state)
        barrier_cell = self._apply(move_type, direction, own_state)
        step = self.step_counter.record_valid_move()  # MOVE/HOLD/BARRIER all count (A5)
        own_state.step_number = step  # BARRIER / jailed-HOLD never route through apply_step
        hint = lint_hint(hint, self.hint_max_words)  # BEFORE sealing: wire == audited bytes
        scent_mine.full_turn(own_state.position)  # dialect-pinned cadence, then snapshot
        record = sealer.seal_step(sealed_payload(
            own_state.state_string(), format_move_string(move_type, direction), verdict, hint,
            step, self.role.value,
            extra={"prompt_discussion": {"llm_prompt": prompt, "llm_reasoning": reasoning,
                                         "bluff_classification": verdict},
                   "model": self.model,
                   "response_seconds": seconds, "random_move": random_move}))
        survived = (self.role is Role.THIEF and not concede
                    and rules.survived(self.step_counter, self.survival_threshold))
        message = TurnMessage(
            step=step, sender=self.role.value, hint=hint, smell_grid=scent_mine.snapshot(),
            commit=record["commit"], timestamp=self._now(),
            barrier_placed=None if barrier_cell is None else list(barrier_cell),
            capture_claim=(list(own_state.position)  # cop, EVERY MOVE turn (INTEROP §2.2)
                           if self.role is Role.POLICE and move_type is MoveType.MOVE else None),
            claim_response=claim_response,
            win_claim={"type": "survival"} if survived else None)
        fsm.advance(State.SENDING)
        transport.receive_turn(message.to_wire())  # the opponent's receive_turn tool
        fsm.advance(State.GAME_OVER if (terminal := concede or survived) else State.OPP_TURN)
        return SentTurn(step, message, record, move_type, direction, barrier_cell,
                        random_move, terminal)

    def _guard(self, decision: Any, state: Any) -> tuple[MoveType, Direction | None, bool]:
        """NEVER send an illegal move: validate via domain rules, degrade on any brain bug."""
        move_type, direction = decision.move_type, decision.direction
        if move_type is MoveType.MOVE and direction is Direction.STAY:
            move_type, direction = MoveType.HOLD, None  # staying travels as HOLD:- (§2.2)
        try:
            if move_type is MoveType.MOVE:
                rules.validate_step(state.board, state.position, direction, state.barriers)
            elif move_type is MoveType.BARRIER:
                if self.role is not Role.POLICE:
                    raise IllegalMoveError("only the police may place barriers")
                rules.validate_barrier(state.board, state.position,
                                       self._barrier_target(state, direction), state.barriers,
                                       state.my_barriers, self.barriers_max)
            return move_type, direction, bool(decision.random_move)
        except IllegalMoveError:
            moves = state.board.legal_moves(state.position, state.barriers)
            if not moves:  # jailed: the HOLD backstop, never the plan (STRATEGY §8.1)
                return MoveType.HOLD, None, True
            fallback = moves[0][0]  # first legal move in move_set order, flagged random_move
            return ((MoveType.HOLD, None, True) if fallback is Direction.STAY
                    else (MoveType.MOVE, fallback, True))

    @staticmethod
    def _barrier_target(state: Any, direction: Any) -> Cell:
        """The cell a BARRIER decision names: own cell (STAY) or one orthogonal neighbour."""
        try:
            delta = DIRECTION_DELTAS[Direction(direction)]
        except ValueError:
            raise IllegalMoveError(f"bad barrier direction {direction!r}") from None
        return (state.position[0] + delta[0], state.position[1] + delta[1])

    def _apply(self, move_type: MoveType, direction: Direction | None,
               own_state: Any) -> Cell | None:
        """Mutate MY state; every branch consumes exactly one of my steps (ruling A5)."""
        if move_type is MoveType.BARRIER:
            target = self._barrier_target(own_state, direction)
            own_state.apply_barrier(target)  # quota counter + shared barrier map
            return target
        if move_type is MoveType.MOVE:
            own_state.apply_step(Direction(direction))
        elif own_state.board.step(own_state.position, Direction.STAY, own_state.barriers):
            own_state.apply_step(Direction.STAY)  # HOLD with STAY legal: the documented path
        return None  # jailed HOLD: no state change; the step still counts (A5, caller bumps)
