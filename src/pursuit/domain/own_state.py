"""OwnGameState — one peer's private, authoritative truth (Zero-Trust, book rules 1-2, 8-9).

Each OS process holds exactly one OwnGameState and it NEVER contains the opponent's
position: the only opponent facts stored are truthfully-declared barriers (book rule 45 —
the cop must announce every barrier it builds, so both sides share the barrier map).
Everything else about the opponent lives in the belief layer, never here.

Mechanics captured:
- ``visited`` includes the start cell (survival counting, book rule 44 semantics).
- ``step_number`` is *my own* per-peer counter (ruling A5): every action I take through
  this object increments it — MOVE and STAY via :meth:`apply_step`.
- ``state_string`` is the compact sealed-state form pinned byte-exactly by INTEROP §2.2:
  ``grid=7x7;self=[4, 3];barriers=[[2, 5]]`` — Python list repr *with spaces*, barriers
  sorted — because it is hashed inside the per-step commit (rule 18); one byte of drift
  breaks every cross-audit.

Board contract (injected, stateless — see ``domain/board.py``): ``board.size -> int`` and
``board.legal_moves(pos, barriers) -> [(Direction, Cell), ...]`` — the single legality
gate. Pure domain logic: no I/O, no randomness, no hardcoded game parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from pursuit.constants import Cell, Direction
from pursuit.exceptions import IllegalMoveError


class BoardLike(Protocol):
    """The slice of the Board API this state machine relies on."""

    @property
    def size(self) -> int: ...

    def legal_moves(self, pos: Cell, barriers: set[Cell]) -> list[tuple[Direction, Cell]]:
        """All (direction, destination) pairs legal from ``pos`` given ``barriers``."""
        ...


def _cells_as_sorted_lists(cells: set[Cell]) -> list[list[int]]:
    """Barriers rendered as sorted ``[r, c]`` lists — the sealed-state ordering rule."""
    return [list(cell) for cell in sorted(cells)]


@dataclass
class OwnGameState:
    """My private truth for one sub-game. Zero-Trust: no opponent position, ever."""

    board: BoardLike
    position: Cell
    visited: set[Cell] = field(default_factory=set)
    barriers: set[Cell] = field(default_factory=set)  # ALL declared barriers, both sides
    my_barriers: int = 0  # how many of those I placed (quota counter)
    step_number: int = 0  # my own counter, per ruling A5

    def __post_init__(self) -> None:
        self.visited.add(self.position)  # the start cell always counts as visited

    def apply_step(self, direction: Direction) -> Cell:
        """Move myself one step; the board is the single legality gate.

        Raises IllegalMoveError without mutating anything (off-grid, barriered, or a
        direction outside the negotiated move set); on success updates position,
        visited, and my step counter, and returns the new cell.
        """
        legal = dict(self.board.legal_moves(self.position, self.barriers))
        destination = legal.get(direction)
        if destination is None:
            raise IllegalMoveError(f"illegal step {direction.value} from {self.position}")
        self.position = destination
        self.visited.add(destination)
        self.step_number += 1
        return destination

    def apply_barrier(self, cell: Cell) -> None:
        """Record a barrier I placed: bump my quota counter and the shared barrier map.

        Building on an already-barriered cell is provably wasted/illegal — reject it so
        the quota counter can never be inflated by no-op placements.
        """
        if cell in self.barriers:
            raise IllegalMoveError(f"barrier already present at {cell}")
        self.barriers.add(cell)
        self.my_barriers += 1

    def note_opponent_barrier(self, cell: Cell) -> None:
        """Fold the opponent's truthful barrier declaration (rule 45) into the map."""
        self.barriers.add(cell)

    def state_string(self) -> str:
        """The sealed compact state — byte-exact per INTEROP §2.2.

        Format: ``grid=NxN;self=[r, c];barriers=[[r, c], ...]`` (Python list repr with
        spaces, barriers sorted). This string is hashed inside the per-step commit, so
        its bytes are frozen by the wire contract.
        """
        size = self.board.size
        return (
            f"grid={size}x{size}"
            f";self={list(self.position)!r}"
            f";barriers={_cells_as_sorted_lists(self.barriers)!r}"
        )
