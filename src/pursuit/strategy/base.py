"""Brain contract — ``Decision`` + ``BrainBase`` (reference-compatible seam, ref-map §4.1).

The move is ALWAYS pure Python: ``decide`` runs ``_decide_move`` to completion BEFORE
the talk layer is consulted (rule 25; STRATEGY §8.2 — we decline the LLM-move
exception). Talk contributes only the hint/verdict/reasoning/prompt strings.

Belief objects are duck-typed: anything exposing ``most_likely()`` and
``most_likely_p()`` works (reference BeliefGrid, BeliefV2, test fakes) — see
:class:`BeliefLike` and :func:`mode_probability`.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

from pursuit.constants import Cell, Direction, MoveType, Role


class BeliefLike(Protocol):
    """Minimum belief surface the v1 brains consume (duck-typed, never isinstance-gated)."""

    def most_likely(self) -> Cell:
        """The posterior mode cell."""
        ...

    def most_likely_p(self) -> Any:
        """Mode probability — a float, or ``(cell, prob)`` per STRATEGY §2.6."""
        ...


class TalkLike(Protocol):
    """The hint provider seam (template or LLM-backed, D8)."""

    def say(
        self, role: Role, state: Any, belief: Any, setting: str,
        opponent_hint: str, deadline: float | None,
    ) -> tuple[str, str, str, str]:
        """Return ``(hint, verdict, reasoning, prompt_text)``."""
        ...


def mode_probability(belief: BeliefLike) -> float:
    """Posterior mass of the belief mode, tolerant of both duck-typed shapes."""
    value = belief.most_likely_p()
    if isinstance(value, tuple):  # STRATEGY §2.6 variant returns (cell, prob)
        value = value[-1]
    return float(value)


@dataclass
class Decision:
    """One turn's full output — everything the sealed step record needs (INTEROP §2.3)."""

    move_type: MoveType
    direction: Direction | None
    hint: str
    verdict: str  # "truth" | "lie" — truthful label of our OWN hint (STRATEGY §8.9)
    reasoning: str = ""
    prompt_text: str = ""
    response_seconds: float = 0.0
    random_move: bool = False


class BrainBase(ABC):
    """Move first (pure Python), talk second — the only ``decide()`` order allowed."""

    role: Role  # concrete subclasses pin their role

    def __init__(self, talk: TalkLike, rng: Any) -> None:
        self.talk = talk
        self.rng = rng  # injected (STRATEGY §8.8) — subclasses may never seed their own
        self._random_move = False  # rng-driven paths flag themselves inside _decide_move

    def decide(
        self,
        state: Any,
        belief: BeliefLike,
        opponent_hint: str,
        setting: str,
        barriers_max: int,
        deadline_seconds: float | None = None,
    ) -> Decision:
        """Full turn decision: physics move first, then the (never move-picking) hint."""
        started = time.perf_counter()
        self._random_move = False
        move_type, direction = self._decide_move(state, belief, barriers_max)
        hint, verdict, reasoning, prompt = self.talk.say(
            self.role, state, belief, setting, opponent_hint, deadline_seconds
        )
        return Decision(
            move_type=move_type,
            direction=direction,
            hint=hint,
            verdict=verdict,
            reasoning=reasoning,
            prompt_text=prompt,
            response_seconds=time.perf_counter() - started,
            random_move=self._random_move,
        )

    def _decide_move(
        self, state: Any, belief: BeliefLike, barriers_max: int
    ) -> tuple[MoveType, Direction | None]:
        """Default policy: pick from PRE-FILTERED legal moves; HOLD only when jailed."""
        moves = state.board.legal_moves(state.position, state.barriers)
        if not moves:
            return (MoveType.HOLD, None)  # runtime force-HOLD backstop, never the plan (§8.1)
        direction, _cell = self._pick_move(moves, state, belief)
        return (MoveType.MOVE, direction)

    @abstractmethod
    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        """Choose one of the given legal moves — never invent a cell (STRATEGY §8.1)."""
