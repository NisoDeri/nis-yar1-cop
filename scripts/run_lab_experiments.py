"""Lab experiments: run 4 matchups with different brain combinations and save stats."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pursuit.constants import Role  # noqa: E402
from pursuit.lab.arena import play_subgame  # noqa: E402
from pursuit.sdk.lab_gate import _belief_factory, _LabBrain  # noqa: E402
from pursuit.shared.config import ConfigManager  # noqa: E402
from pursuit.strategy.greedy import GreedyPoliceBrain, GreedyThiefBrain  # noqa: E402
from pursuit.strategy.police import InterceptorPoliceBrain  # noqa: E402
from pursuit.strategy.talk import TemplateTalk  # noqa: E402
from pursuit.strategy.thief import SurvivorThiefBrain  # noqa: E402


def run_matchup(police_cls, thief_cls, terms, n_games=100, base_seed=42):
    """Run n_games with police_cls vs thief_cls, return stats dict."""
    barriers_max = int(terms["movement_and_barriers"]["max_barriers"])

    wins_police = 0
    wins_thief = 0
    total_steps: list[int] = []

    for i in range(n_games):
        seed = base_seed + i
        rng = random.Random(seed)
        talk = TemplateTalk(rng, "city", 10)
        police = _LabBrain(police_cls(talk, rng), barriers_max)
        thief = _LabBrain(thief_cls(talk, rng), barriers_max)
        outcome = play_subgame(
            police, thief, terms, random.Random(seed), belief_factory=_belief_factory
        )
        if outcome.winner_role is Role.POLICE:
            wins_police += 1
        elif outcome.winner_role is Role.THIEF:
            wins_thief += 1
        total_steps.append(outcome.steps)

    return {
        "n_games": n_games,
        "wins_police": wins_police,
        "wins_thief": wins_thief,
        "win_rate_police": wins_police / n_games,
        "win_rate_thief": wins_thief / n_games,
        "avg_steps": sum(total_steps) / len(total_steps),
        "median_steps": sorted(total_steps)[len(total_steps) // 2],
    }


def main():
    config_dir = ROOT / "config" / "police"
    config = ConfigManager.load(config_dir)
    config.validate_agreement()

    terms_blocks = ("board_and_agents", "movement_and_barriers", "scoring", "pheromones")
    terms = {block: config.game(block) for block in terms_blocks}

    print("Running matchups...", flush=True)

    matchups = {
        "interceptor_vs_survivor": {
            "police": "InterceptorPoliceBrain",
            "thief": "SurvivorThiefBrain",
            "result": run_matchup(InterceptorPoliceBrain, SurvivorThiefBrain, terms),
        },
        "interceptor_vs_greedy": {
            "police": "InterceptorPoliceBrain",
            "thief": "GreedyThiefBrain",
            "result": run_matchup(InterceptorPoliceBrain, GreedyThiefBrain, terms),
        },
        "greedy_vs_survivor": {
            "police": "GreedyPoliceBrain",
            "thief": "SurvivorThiefBrain",
            "result": run_matchup(GreedyPoliceBrain, SurvivorThiefBrain, terms),
        },
        "greedy_vs_greedy": {
            "police": "GreedyPoliceBrain",
            "thief": "GreedyThiefBrain",
            "result": run_matchup(GreedyPoliceBrain, GreedyThiefBrain, terms),
        },
    }

    result = {
        "matchups": matchups,
        "board_size": terms["board_and_agents"]["grid_size"],
        "survival_threshold": terms["movement_and_barriers"]["survival_threshold"],
        "max_barriers": terms["movement_and_barriers"]["max_barriers"],
    }

    out_path = ROOT / "artifacts" / "lab" / "first_blood.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Saved to {out_path}", flush=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
