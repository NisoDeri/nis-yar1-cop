"""In-process referee arena — the lab's game loop (STRATEGY.md §6, D7).

Both brains run in ONE process against the REAL domain rules: every legality
check routes through :mod:`pursuit.domain.rules`, scent through the negotiated
dialect models, survival through the thief's OWN StepCounter (ruling A5 — a
cop barrier turn consumes a cop move but never advances the thief's clock).
No sockets, no LLMs: CI-safe at hundreds of games a minute. The brain-facing
contract (views, decisions, the information partition) lives in
:mod:`pursuit.lab.protocol` and is re-exported here.
"""

from __future__ import annotations

import random
from typing import Any

from pursuit.constants import Direction, GameResult, MoveType, Role
from pursuit.domain import rules
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.domain.scent import make_scent_model
from pursuit.exceptions import IllegalMoveError
from pursuit.lab.protocol import (
    BrainLike,
    LabDecision,
    LabView,
    NullBelief,
    Side,
    SubgameResult,
)

__all__ = ["BrainLike", "LabDecision", "LabView", "NullBelief", "SubgameResult", "play_subgame"]


def _null_factory(role: Role, terms: dict) -> NullBelief:
    return NullBelief()


def _scent_terms(terms: dict) -> dict:
    """Adapt the signed game.json pheromones block to the ScentParams vocabulary."""
    pheromones = terms["pheromones"]
    return {
        "dialect": pheromones["dialect"],
        "board_size": terms["board_and_agents"]["grid_size"],
        "smell_grid_size": pheromones["pheromone_grid_size"],
        "emit_intensity": pheromones["pheromone_center_intensity"],
        "decay_per_step": pheromones["pheromone_decay"],
        "min_center_intensity": pheromones["pheromone_min_center_intensity"],
    }


def _apply_step(side: Side, board: Board, decision: LabDecision, trajectory: list[str]) -> None:
    if decision.move_type is MoveType.BARRIER:
        raise IllegalMoveError(f"only the cop may place barriers, not the {side.role.value}")
    if decision.move_type is MoveType.HOLD:
        direction = Direction.STAY
    elif decision.direction is None:
        raise IllegalMoveError(f"{side.role.value} MOVE decision carries no direction")
    else:
        direction = Direction(decision.direction)
    rules.validate_step(board, side.state.position, direction, side.state.barriers)
    side.state.apply_step(direction)
    trajectory.append(f"{side.role.value}:{decision.move_type.value}:{direction.value}")


def play_subgame(police_brain: BrainLike, thief_brain: BrainLike, config_terms: dict,
                 rng: random.Random, belief_factory: Any = None) -> SubgameResult:
    """Referee one sub-game under the signed terms; the thief moves first each round."""
    agents, movement = config_terms["board_and_agents"], config_terms["movement_and_barriers"]
    board = Board(agents["grid_size"], movement["move_set"])
    factory = belief_factory or _null_factory
    scent_terms = _scent_terms(config_terms)

    def build(role: Role, brain: BrainLike, start: list) -> Side:
        return Side(role, brain, OwnGameState(board, tuple(start)),
                    factory(role, config_terms), make_scent_model(scent_terms))

    cop = build(Role.POLICE, police_brain, agents["cop_start"])
    thief = build(Role.THIEF, thief_brain, agents["thief_start"])
    counter, cop_steps, trajectory = rules.StepCounter(), 0, []

    def finish(result: GameResult, winner: Role | None, kind: str | None) -> SubgameResult:
        return SubgameResult(result, winner, counter.count, cop_steps, kind, tuple(trajectory))

    for _ in range(movement["survival_threshold"]):
        decision = thief.decide(cop, movement["survival_threshold"] - counter.count, rng)
        _apply_step(thief, board, decision, trajectory)
        counter.record_valid_move()
        thief.emit(decision)
        if rules.capture_by_landing(cop.state.position, thief.state.position):
            return finish(GameResult.CAPTURE, Role.POLICE, "landing")
        if rules.survived(counter, movement["survival_threshold"]):
            return finish(GameResult.SURVIVAL, Role.THIEF, None)
        if cop_steps >= movement["max_moves"]:  # move ceiling: the cop is out of turns
            return finish(GameResult.SURVIVAL, Role.THIEF, None)
        decision = cop.decide(thief, movement["max_moves"] - cop_steps, rng)
        cop_steps += 1  # a barrier turn consumes the cop's move too (ruling A5)
        if decision.move_type is MoveType.BARRIER:
            cell = None if decision.barrier_cell is None else tuple(decision.barrier_cell)
            rules.validate_barrier(board, cop.state.position, cell, cop.state.barriers,
                                   cop.state.my_barriers, movement["max_barriers"])
            cop.state.apply_barrier(cell)
            thief.state.note_opponent_barrier(cell)  # truthful declaration (rule 14)
            counter.record_opponent_barrier_turn()  # explicit no-op on the thief clock
            trajectory.append(f"{Role.POLICE.value}:BARRIER:{cell[0]},{cell[1]}")
            cop.emit(decision)
            if rules.capture_by_barrier(cell, thief.state.position):
                return finish(GameResult.CAPTURE, Role.POLICE, "barrier")
            if rules.jailed(board, thief.state.position, thief.state.barriers):
                return finish(GameResult.CAPTURE, Role.POLICE, "jailed")
        else:
            _apply_step(cop, board, decision, trajectory)
            cop.emit(decision)
            if rules.capture_by_landing(cop.state.position, thief.state.position):
                return finish(GameResult.CAPTURE, Role.POLICE, "landing")
    return finish(GameResult.STOPPED, None, None)  # pragma: no cover — defensive loop bound
