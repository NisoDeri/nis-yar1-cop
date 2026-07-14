"""Stateless board geometry for the NxN pursuit grid.

The negotiated ``move_set`` (Appendix F: ``["N","S","E","W","STAY"]``) is validated
STRICTLY against :class:`~pursuit.constants.Direction` — an unknown entry raises
:class:`~pursuit.exceptions.ConfigError` instead of silently falling back to king
moves (the reference simulator's fallback is a known technical-loss trap, D4).

Geometry only: a cell with zero legal moves is *jailed*, but jail **detection**
(rule 47 capture) lives in ``rules.py``. Barrier-aware BFS distance and k-step
reachability (the mobility metric ``mob_k``, STRATEGY.md §4.2) are the primitives
the strategy layer builds on.
"""

from collections import deque
from collections.abc import Set as AbstractSet

from pursuit.constants import DIRECTION_DELTAS, Cell, Direction
from pursuit.exceptions import ConfigError


class Board:
    """Immutable NxN grid geometry under a negotiated move set (no game state)."""

    def __init__(self, size: int, move_set: list[str]) -> None:
        if not isinstance(size, int) or size < 1:
            raise ConfigError(f"board size must be a positive int, got {size!r}")
        if not move_set:
            raise ConfigError("move_set must not be empty")
        directions: list[Direction] = []
        for entry in move_set:
            try:
                direction = Direction(entry)
            except ValueError:
                raise ConfigError(
                    f"unknown move {entry!r} in move_set {move_set!r} — "
                    "no king-move fallback (allowed: N/S/E/W/STAY)"
                ) from None
            if direction not in directions:
                directions.append(direction)
        self.size = size
        self.move_set: tuple[Direction, ...] = tuple(directions)
        # STAY is a legal *move* but never a step delta for geometry walks.
        self.step_directions: tuple[Direction, ...] = tuple(
            d for d in directions if d is not Direction.STAY
        )
        self.allows_stay: bool = Direction.STAY in directions

    def in_bounds(self, cell: Cell) -> bool:
        """True iff ``cell`` lies on the grid (0-indexed, origin top-left)."""
        row, col = cell
        return 0 <= row < self.size and 0 <= col < self.size

    @staticmethod
    def _shift(pos: Cell, direction: Direction) -> Cell:
        """Raw delta application — internal helper, no legality checks."""
        d_row, d_col = DIRECTION_DELTAS[direction]
        return (pos[0] + d_row, pos[1] + d_col)

    def step(
        self, origin: Cell, direction: Direction, barriers: AbstractSet[Cell]
    ) -> Cell | None:
        """SINGLE physics primitive (reference_map §domain/board.py, todo T1.10).

        Destination cell, or ``None`` when the step is illegal: direction outside
        the negotiated move set, destination off-board, or destination barriered.
        Movement legality and barrier-placement legality both route through here.
        """
        if direction not in self.move_set:
            return None
        dest = self._shift(origin, direction)
        if not self.in_bounds(dest) or dest in barriers:
            return None
        return dest

    def neighbors(self, cell: Cell) -> list[Cell]:
        """In-bounds orthogonal neighbors per the negotiated step directions."""
        candidates = (self._shift(cell, d) for d in self.step_directions)
        return [c for c in candidates if self.in_bounds(c)]

    def legal_moves(self, pos: Cell, barriers: set[Cell]) -> list[tuple[Direction, Cell]]:
        """All (direction, destination) pairs legal from ``pos`` given barriers.

        Includes ``(STAY, pos)`` when STAY is in the move set; excludes off-board
        and barrier destinations. An empty result means the agent is jailed —
        the capture consequence of that is judged in ``rules.py`` (rule 47).
        """
        moves: list[tuple[Direction, Cell]] = []
        for direction in self.move_set:
            dest = self.step(pos, direction, barriers)
            if dest is not None:
                moves.append((direction, dest))
        return moves

    @staticmethod
    def manhattan(a: Cell, b: Cell) -> int:
        """L1 distance — exact only on an empty orthogonal board (see bfs_distance)."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def bfs_distance(self, a: Cell, b: Cell, barriers: set[Cell]) -> int | None:
        """Barrier-aware true step distance from ``a`` to ``b``; None if unreachable.

        The strategy layer's interception math depends on this being the *true*
        distance around walls, not the Manhattan lower bound.
        """
        if not (self.in_bounds(a) and self.in_bounds(b)):
            return None
        if a == b:
            return 0
        if b in barriers:
            return None
        frontier: deque[tuple[Cell, int]] = deque([(a, 0)])
        seen = {a}
        while frontier:
            cell, dist = frontier.popleft()
            for nxt in self.neighbors(cell):
                if nxt in seen or nxt in barriers:
                    continue
                if nxt == b:
                    return dist + 1
                seen.add(nxt)
                frontier.append((nxt, dist + 1))
        return None

    def reachable_cells(self, pos: Cell, barriers: set[Cell], k: int) -> set[Cell]:
        """Cells BFS-reachable from ``pos`` within ``k`` steps (mobility ``mob_k``).

        Includes ``pos`` itself; barrier-aware; empty set if ``pos`` is off-board.
        """
        if k < 0:
            raise ConfigError(f"reachability horizon k must be >= 0, got {k}")
        if not self.in_bounds(pos):
            return set()
        reached = {pos}
        frontier: deque[tuple[Cell, int]] = deque([(pos, 0)])
        while frontier:
            cell, dist = frontier.popleft()
            if dist == k:
                continue
            for nxt in self.neighbors(cell):
                if nxt in reached or nxt in barriers:
                    continue
                reached.add(nxt)
                frontier.append((nxt, dist + 1))
        return reached
