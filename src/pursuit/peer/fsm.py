"""Guarded turn state machine for one peer sub-game (book rules 4-5).

The reference simulator broadcasts 7 status labels with NO transition table —
nothing is ever rejected (reference_map gap #16). Here every legal edge is an
explicit entry in ``ALLOWED`` (architecture.md §4); anything absent raises
:class:`IllegalTransitionError` (rule 5: illegal transitions are rejected and
surfaced, never silently absorbed — the runtime decides drop-vs-abort).

States: ``BOOT → NEGOTIATING → OPP_TURN ⇄ MY_TURN → SENDING → … → GAME_OVER →
AUDITING → DONE``, plus the ``PAUSED`` overlay (resume returns to the EXACT
prior state) and terminal ``ABORTED`` (watchdog controlled extraction, rule 7).
``GAME_OVER → AUDITING`` is unconditional: the audit runs on EVERY ending,
timeout/stopped included (decision D4; fixes reference gap #5).

``wire_status()`` projects internal states onto the reference's 7 broadcast
labels so partner GUIs read us natively over the control channel.
"""

from __future__ import annotations

from enum import StrEnum

from pursuit.exceptions import IllegalTransitionError


class State(StrEnum):
    """Internal FSM states (architecture.md §4)."""

    BOOT = "BOOT"
    NEGOTIATING = "NEGOTIATING"
    OPP_TURN = "OPP_TURN"
    MY_TURN = "MY_TURN"
    SENDING = "SENDING"
    PAUSED = "PAUSED"
    GAME_OVER = "GAME_OVER"
    AUDITING = "AUDITING"
    DONE = "DONE"
    ABORTED = "ABORTED"


TERMINAL_STATES: frozenset[State] = frozenset({State.DONE, State.ABORTED})

# Explicit transition table — any (state, to_state) pair absent here is illegal.
# GAME_OVER is reachable from every non-terminal state (control(stop) / outcome /
# deadline); ABORTED from every non-terminal state (watchdog_fire / fatal).
ALLOWED: dict[State, frozenset[State]] = {
    State.BOOT: frozenset({State.NEGOTIATING, State.GAME_OVER, State.ABORTED}),
    State.NEGOTIATING: frozenset(
        {State.OPP_TURN, State.MY_TURN, State.GAME_OVER, State.ABORTED}
    ),
    State.OPP_TURN: frozenset({State.MY_TURN, State.PAUSED, State.GAME_OVER, State.ABORTED}),
    State.MY_TURN: frozenset({State.SENDING, State.PAUSED, State.GAME_OVER, State.ABORTED}),
    State.SENDING: frozenset({State.OPP_TURN, State.GAME_OVER, State.ABORTED}),
    State.PAUSED: frozenset({State.OPP_TURN, State.MY_TURN, State.GAME_OVER, State.ABORTED}),
    State.GAME_OVER: frozenset({State.AUDITING, State.ABORTED}),
    State.AUDITING: frozenset({State.DONE, State.ABORTED}),
    State.DONE: frozenset(),
    State.ABORTED: frozenset(),
}

# The reference's 7 broadcast labels (its whole "state machine") — wire contract.
WIRE_LABELS: frozenset[str] = frozenset(
    {"WAITING", "THINKING", "PLAYING", "PAUSED", "STOPPED", "GAME_OVER", "QUIT"}
)

# Projection of our guarded states onto those labels (architecture.md §4).
WIRE_PROJECTION: dict[State, str] = {
    State.BOOT: "WAITING",  # not yet negotiated — waiting for the opponent
    State.NEGOTIATING: "WAITING",
    State.OPP_TURN: "WAITING",  # turn token is with the opponent
    State.MY_TURN: "THINKING",  # brain deciding under deadline
    State.SENDING: "PLAYING",  # actively executing our turn
    State.PAUSED: "PAUSED",
    State.GAME_OVER: "GAME_OVER",
    State.AUDITING: "GAME_OVER",  # audit is part of the ending on the wire
    State.DONE: "STOPPED",  # sub-game fully closed out
    State.ABORTED: "QUIT",  # controlled extraction / fatal exit
}


class GameStateMachine:
    """Guarded FSM: ``advance`` is the ONLY mutator; every move is audited."""

    def __init__(self) -> None:
        self._state = State.BOOT
        self._history: list[tuple[State, State]] = []
        self._resume_state: State | None = None

    @property
    def state(self) -> State:
        return self._state

    @property
    def history(self) -> list[tuple[State, State]]:
        """Audit trail of every accepted transition (defensive copy)."""
        return list(self._history)

    @property
    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    def advance(self, to_state: State) -> State:
        """Move to ``to_state`` or raise :class:`IllegalTransitionError` (rule 5).

        A rejected transition leaves state and history untouched — the caller
        (turn loop / watchdog) owns the logging and escalation policy.
        """
        if to_state not in ALLOWED[self._state]:
            raise IllegalTransitionError(
                f"illegal transition {self._state.value} -> {to_state.value}"
            )
        if (
            self._state is State.PAUSED
            and to_state in (State.OPP_TURN, State.MY_TURN)
            and to_state is not self._resume_state
        ):
            raise IllegalTransitionError(
                f"resume must return to {self._resume_state and self._resume_state.value}, "
                f"not {to_state.value}"
            )
        if to_state is State.PAUSED:
            self._resume_state = self._state
        self._history.append((self._state, to_state))
        self._state = to_state
        return to_state

    def wire_status(self) -> str:
        """Current state projected onto the reference's 7 broadcast labels."""
        return WIRE_PROJECTION[self._state]
