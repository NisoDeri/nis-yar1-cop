"""Role-conditioned motion kernels — the PREDICT step of BeliefV2 (STRATEGY.md §2.4).

The opponent moves by policy, not by diffusion: a thief flees the reference
point (plus a kept-options mobility bonus), a cop chases it::

    K(c' | c) = softmax_eta{ u_role(c -> c') }   over  {c} + legal destinations
    u_thief(c -> c')  = [d_BFS(c', ref) - d_BFS(c, ref)] + mu * mob_k(c')
    u_police(c -> c') = [d_BFS(c, ref) - d_BFS(c', ref)]

Barrier-aware and locked to the negotiated move set via ``Board.legal_moves``;
``eta = 0`` recovers the reference's uniform diffuse (the ``belief.impl``
ablation seam). Pure functions — no state, every parameter injected.
"""

import math

from pursuit.constants import Cell, Role
from pursuit.domain.board import Board


def _distance(board: Board, barriers: set[Cell], a: Cell, b: Cell) -> float:
    """BFS true distance; unreachable pairs cost a full board sweep (finite worst)."""
    dist = board.bfs_distance(a, b, barriers)
    return float(dist) if dist is not None else float(board.size * board.size)


def mobility(board: Board, barriers: set[Cell], cell: Cell, k: int) -> int:
    """mob_k(c): cells BFS-reachable within k steps — the kept-options bonus."""
    return len(board.reachable_cells(cell, barriers, k))


def utility(
    board: Board,
    barriers: set[Cell],
    origin: Cell,
    dest: Cell,
    reference: Cell,
    role: Role | str,
    mobility_mu: float,
    mobility_k: int,
) -> float:
    """u_role(c -> c'): thief gains by fleeing + mobility, police by closing in."""
    gain = _distance(board, barriers, dest, reference) - _distance(
        board, barriers, origin, reference
    )
    if Role(role) is Role.THIEF:
        return gain + mobility_mu * mobility(board, barriers, dest, mobility_k)
    return -gain


def transition_row(
    board: Board,
    barriers: set[Cell],
    origin: Cell,
    reference: Cell,
    role: Role | str,
    eta: float,
    mobility_mu: float,
    mobility_k: int,
) -> dict[Cell, float]:
    """K(. | origin): softmax_eta over stay + legal steps; eta <= 0 -> uniform."""
    dests = {origin} | {dest for _, dest in board.legal_moves(origin, barriers)}
    if eta <= 0.0:
        return dict.fromkeys(dests, 1.0 / len(dests))
    mover = Role(role)
    utils = {
        dest: utility(board, barriers, origin, dest, reference, mover, mobility_mu, mobility_k)
        for dest in dests
    }
    top = max(utils.values())
    weights = {dest: math.exp(eta * (value - top)) for dest, value in utils.items()}
    total = sum(weights.values())
    return {dest: weight / total for dest, weight in weights.items()}


def apply_kernel(
    board: Board,
    barriers: set[Cell],
    belief: dict[Cell, float],
    reference: Cell,
    role: Role | str,
    eta: float,
    mobility_mu: float,
    mobility_k: int,
) -> dict[Cell, float]:
    """One predict sweep: b_bar(c') = sum_c K(c'|c) * b(c). Input is not mutated."""
    out = dict.fromkeys(belief, 0.0)
    for origin, mass in belief.items():
        if mass <= 0.0:
            continue
        row = transition_row(
            board, barriers, origin, reference, role, eta, mobility_mu, mobility_k
        )
        for dest, prob in row.items():
            out[dest] += mass * prob
    return out
