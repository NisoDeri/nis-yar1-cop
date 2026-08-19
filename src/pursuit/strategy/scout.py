"""Scouting: learn a greedy opponent from a FRIENDLY game, exploit it in the COUNTED one.

The commit-reveal audit discloses the opponent's FULL trajectory, so a friendly hands us
their move history. Most pure-Python agents move greedily — a thief to the neighbour that
MAXIMISES board distance from the cop, a cop to the one that MINIMISES it. If a game shows
the opponent is greedy, we can PREDICT their next cell and best-respond one step ahead
(lead the cut / flee the predicted square) instead of reacting to where they are now.

Pure functions over the board + a tiny JSON profile. No wire/interop contact. Gated:
nothing here runs unless a profile is loaded (env ``PURSUIT_SCOUT_PROFILE``) or recording
is opted in — the default game is untouched.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pursuit.constants import Cell

#: Env var naming the scout profile a scout-aware brain best-responds to (unset -> off).
PROFILE_ENV = "PURSUIT_SCOUT_PROFILE"
#: Greedy-consistency at/above which we trust the prediction (below -> fall back to belief).
GREEDY_TRUST = 0.7


def _dist(board: Any, barriers: Any, a: Cell, b: Cell) -> float:
    """BFS distance, unreachable -> a full-board sentinel (finite, sortable)."""
    d = board.bfs_distance(a, b, barriers)
    return float(d) if d is not None else float(board.size * board.size)


def _neighbours(board: Any, barriers: Any, cell: Cell) -> list[Cell]:
    """The cell itself (STAY) plus every legal orthogonal step — the greedy candidate set."""
    return [cell, *[dest for _dir, dest in board.legal_moves(cell, barriers)]]


def predict_greedy(board: Any, barriers: Any, opp_pos: Cell, my_pos: Cell,
                   opp_is_thief: bool) -> Cell:
    """The cell a GREEDY opponent moves to next: thief maximises, cop minimises distance to us.

    Ties break row-major (deterministic) — matching how a simple agent's argmax resolves.
    """
    cands = _neighbours(board, barriers, opp_pos)
    key = (lambda c: (-_dist(board, barriers, c, my_pos), c)) if opp_is_thief \
        else (lambda c: (_dist(board, barriers, c, my_pos), c))
    return min(cands, key=key)


def best_response(board: Any, barriers: Any, moves: list[tuple[Any, Cell]], my_pos: Cell,
                  target: Cell, chase: bool) -> Any:
    """Our move that leads the target: chase -> minimise, flee -> maximise distance to ``target``.

    Returns the chosen ``(Direction, Cell)`` move (or ``None`` when ``moves`` is empty). Flee
    breaks ties toward the higher-mobility square so we never corner ourselves a step early.
    """
    if not moves:
        return None
    if chase:
        return min(moves, key=lambda m: (_dist(board, barriers, m[1], target), m[1]))
    return max(moves, key=lambda m: (_dist(board, barriers, m[1], target),
                                     len(board.reachable_cells(m[1], barriers, 3)),
                                     tuple(-x for x in m[1])))


def greedy_score(my_positions: list[Cell], opp_positions: list[Cell], board: Any,
                 barriers: Any, opp_is_thief: bool) -> dict[str, Any]:
    """Fraction of the opponent's revealed moves that match the greedy prediction.

    ``*_positions`` are the two agents' post-move cells, index-aligned by turn. A move is
    'consistent' when the opponent landed on the cell greedy play would pick from the prior
    state. Returns ``{greedy_score, samples, opp_role}`` — a compact, serialisable profile.
    """
    hits = samples = 0
    for i in range(1, min(len(opp_positions), len(my_positions))):
        predicted = predict_greedy(board, barriers, opp_positions[i - 1],
                                    my_positions[i - 1], opp_is_thief)
        samples += 1
        if predicted == opp_positions[i]:
            hits += 1
    score = hits / samples if samples else 0.0
    return {"greedy_score": round(score, 3), "samples": samples,
            "opp_role": "thief" if opp_is_thief else "police"}


def merge_profiles(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Sample-weighted merge so multiple friendly sub-games accumulate into one profile."""
    for role_key in ("thief", "police"):
        cur, add = existing.get(role_key), new.get(role_key)
        if add is None:
            continue
        if cur is None:
            existing[role_key] = add
            continue
        n = cur["samples"] + add["samples"]
        blended = 0.0 if n == 0 else (cur["greedy_score"] * cur["samples"]
                                      + add["greedy_score"] * add["samples"]) / n
        existing[role_key] = {"greedy_score": round(blended, 3), "samples": n,
                              "opp_role": role_key}
    return existing


def load_profile(path: str | os.PathLike | None = None) -> dict[str, Any] | None:
    """Load the scout profile from ``path`` or ``$PURSUIT_SCOUT_PROFILE``; None if absent/bad."""
    target = path or os.environ.get(PROFILE_ENV)
    if not target:
        return None
    try:
        data = json.loads(Path(target).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save_profile(path: str | os.PathLike, profile: dict[str, Any]) -> None:
    """Write (merging into any existing profile at ``path``) — the friendly-mode recorder."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    prior = load_profile(p) or {}
    p.write_text(json.dumps(merge_profiles(prior, profile), ensure_ascii=False, indent=2),
                 encoding="utf-8")


def trusted_role(profile: dict[str, Any] | None, opp_is_thief: bool) -> bool:
    """True iff the profile shows the opponent's role plays greedily above the trust floor."""
    if not profile:
        return False
    entry = profile.get("thief" if opp_is_thief else "police")
    return bool(entry and float(entry.get("greedy_score", 0.0)) >= GREEDY_TRUST
               and int(entry.get("samples", 0)) >= 4)
