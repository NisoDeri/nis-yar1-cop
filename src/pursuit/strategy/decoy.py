"""Active scent-decoy routing for the thief (CREATIVITY-DESIGN.md E3, DEFAULT OFF).

Movement is fully ours to choose; the scent cloud is an uncontrollable *consequence*
of the cells we visit, never a signal we fabricate. We cannot suppress emission, so we
SHAPE it: when the flight-safety margin is high, take a short step that lays scent in a
region AWAY from the true escape corridor, dragging the cop's belief argmax onto an
empty decoy cell before we slip out the far edge next turn.

Pure geometry: no config, no I/O, no rng. The brain gates this behind ``decoy_enabled``
and a ``decoy_margin`` distance threshold, and every numeric default lives in the brain
constructor. :func:`propose_decoy` returns ``None`` whenever no *safe* decoy exists
(never a jail-risk cell, never a flee-distance below the safety floor) so the caller
falls straight back to pure flight — the disabled path is byte-for-byte unchanged.
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import Cell, Direction

#: A single step changes true distance by at most one cell, so the deepest a decoy may
#: dip below the current flee distance is one step — and only when the cop is already far.
_MAX_FLEE_SACRIFICE = 1


def _exits(board: Any, cell: Cell, barriers: set[Cell]) -> int:
    """Post-move mobility: non-STAY steps still available from ``cell`` (the jail metric)."""
    return sum(1 for d, _c in board.legal_moves(cell, barriers) if d is not Direction.STAY)


def _safe_moves(
    board: Any,
    moves: list[tuple[Direction, Cell]],
    threat: Cell,
    barriers: set[Cell],
    floor: int,
    opponent_charges: int,
    jail_min_mobility: int,
) -> list[tuple[Direction, Cell]]:
    """Real steps that keep flee-distance >= ``floor`` and never enter a jail-risk cell."""
    safe: list[tuple[Direction, Cell]] = []
    for direction, cell in moves:
        if direction is Direction.STAY:
            continue
        distance = board.bfs_distance(cell, threat, barriers)
        if distance is None or distance < floor:
            continue
        if opponent_charges > 0 and _exits(board, cell, barriers) < jail_min_mobility:
            continue
        safe.append((direction, cell))
    return safe


def propose_decoy(
    board: Any,
    position: Cell,
    threat: Cell,
    barriers: set[Cell],
    moves: list[tuple[Direction, Cell]],
    *,
    margin: int,
    opponent_charges: int,
    jail_min_mobility: int,
) -> tuple[Direction, Cell] | None:
    """A safe misdirection step, or ``None`` when the cop is close / no safe decoy exists.

    Gate: only when the true flee distance is at least ``margin`` (the cop is far enough
    that we can spend tempo). The escape corridor is the safe cell that maximises flee
    distance; the decoy is the safe step whose cell lies FARTHEST from that corridor,
    pulling the cop's future argmax away from where we actually intend to slip out.
    """
    flee = board.bfs_distance(position, threat, barriers)
    if flee is None or flee < margin:
        return None
    floor = flee - _MAX_FLEE_SACRIFICE
    safe = _safe_moves(
        board, moves, threat, barriers, floor, opponent_charges, jail_min_mobility
    )
    if not safe:
        return None
    corridor = max(safe, key=lambda m: (board.bfs_distance(m[1], threat, barriers), m[1]))[1]
    return max(safe, key=lambda m: (board.manhattan(m[1], corridor), m[1]))
