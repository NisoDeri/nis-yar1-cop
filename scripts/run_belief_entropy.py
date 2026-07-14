"""Measure BeliefV2 entropy per turn over 5 real games, using the arena's game loop."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pursuit.constants import Role  # noqa: E402
from pursuit.domain.belief.engine import BeliefV2  # noqa: E402
from pursuit.lab.arena import play_subgame  # noqa: E402
from pursuit.sdk.lab_gate import _LabBrain  # noqa: E402
from pursuit.shared.config import ConfigManager  # noqa: E402
from pursuit.strategy.police import InterceptorPoliceBrain  # noqa: E402
from pursuit.strategy.talk import TemplateTalk  # noqa: E402
from pursuit.strategy.thief import SurvivorThiefBrain  # noqa: E402


class TrackingBeliefV2(BeliefV2):
    """BeliefV2 that records its entropy after every observe_smell call.

    The arena's Side.decide() calls diffuse() with no args (NullBelief compatible),
    so we add a default for opponent_role to stay duck-type compatible.
    """

    def __init__(self, role: Role, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._own_role = role
        self.entropy_log: list[float] = [self.entropy()]  # initial

    def diffuse(self, opponent_role=None, reference=None):
        # Infer opponent role from our own role when called without arguments
        if opponent_role is None:
            opponent_role = Role.THIEF if self._own_role is Role.POLICE else Role.POLICE
        super().diffuse(opponent_role, reference)

    def observe_smell(self, cells):
        super().observe_smell(cells)
        self.entropy_log.append(self.entropy())


def _build_belief_v2(config, role: Role) -> TrackingBeliefV2:
    """Build a real TrackingBeliefV2 from signed config."""
    board_size = int(config.game("board_and_agents.grid_size"))
    belief_raw = config.private("belief")
    belief_cfg = {
        "move_set": list(config.game("movement_and_barriers.move_set")),
        **{k: v for k, v in belief_raw.items()
           if k not in ("smell_trust_weight", "hint_trust_prior")},
    }
    scent_cfg = {
        "dialect": config.game("pheromones.dialect"),
        "board_size": board_size,
        "smell_grid_size": int(config.game("pheromones.pheromone_grid_size")),
        "emit_intensity": float(config.game("pheromones.pheromone_center_intensity")),
        "decay_per_step": float(config.game("pheromones.pheromone_decay")),
        "min_center_intensity": float(config.game("pheromones.pheromone_min_center_intensity")),
    }
    return TrackingBeliefV2(role, board_size, belief_cfg, scent_cfg)


def main():
    config_dir = ROOT / "config" / "police"
    config = ConfigManager.load(config_dir)
    config.validate_agreement()

    terms_blocks = ("board_and_agents", "movement_and_barriers", "scoring", "pheromones")
    terms = {block: config.game(block) for block in terms_blocks}
    barriers_max = int(terms["movement_and_barriers"]["max_barriers"])

    print("Simulating belief entropy traces with real BeliefV2...", flush=True)
    entropy_traces = []
    outcomes = []

    for i in range(5):
        seed = 42 + i
        rng = random.Random(seed)
        talk = TemplateTalk(rng, "city", 10)

        # Create tracking beliefs (one per role — we track police's belief about thief)
        police_belief = _build_belief_v2(config, Role.POLICE)
        thief_belief = _build_belief_v2(config, Role.THIEF)
        # Capture loop variables in default args to avoid B023 closure-over-loop-var
        def _belief_factory(
            role: Role, _terms: dict,
            pb=police_belief, tb=thief_belief,
        ):
            return pb if role is Role.POLICE else tb

        police = _LabBrain(InterceptorPoliceBrain(talk, rng), barriers_max)
        thief = _LabBrain(SurvivorThiefBrain(talk, rng), barriers_max)

        outcome = play_subgame(
            police, thief, terms, random.Random(seed), belief_factory=_belief_factory
        )

        entropy_traces.append(police_belief.entropy_log)
        result_str = (
            f"{outcome.result.value} winner={outcome.winner_role} steps={outcome.steps}"
        )
        outcomes.append(result_str)
        n_pts = len(police_belief.entropy_log)
        print(f"  Game {i + 1}: {result_str}, {n_pts} entropy points")

    result = {
        "entropy_traces": entropy_traces,
        "outcomes": outcomes,
        "n_games": len(entropy_traces),
    }
    out_path = ROOT / "artifacts" / "lab" / "entropy_traces.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved entropy traces to {out_path}")
    for i, trace in enumerate(entropy_traces):
        n_pts = len(trace)
        print(f"Game {i + 1}: initial={trace[0]:.3f} bits -> final={trace[-1]:.3f} bits"
              f" ({n_pts} pts)")


if __name__ == "__main__":
    main()
