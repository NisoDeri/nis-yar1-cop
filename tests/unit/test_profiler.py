"""E2 opponent lie-profiler — pure, deterministic, zero-token (CREATIVITY-DESIGN E2)."""

from __future__ import annotations

import random

import pytest

from pursuit.exceptions import ConfigError
from pursuit.strategy.profiler import OpponentProfiler

# Symmetric Beta prior => an unseen opponent seeds exactly r_0 = 0.5 (config's hint_trust_prior).
CFG = {"hint_alpha0": 1.0, "hint_beta0": 1.0, "move_set": ["N", "S", "E", "W", "STAY"]}


def _rec(hint: str, intent: str, position=(3, 3), state: str = "grid=7x7;self=[3, 3];barriers=[]"):
    """Wrap a single revealed step record the way the sealed logs do."""
    payload = {"hint": hint, "intent": intent, "position": list(position), "state": state}
    return {"payload": payload, "nonce": "x", "commit": "y"}


def _north_liar_records(rng: random.Random):
    """Opponent lies about north ~80% of the time, truthful about other directions."""
    records = []
    for i in range(20):  # north-heavy transcript
        intent = "lie" if i % 5 != 0 else "truth"  # 16 lies / 4 truths => 0.8 lie-rate on N
        records.append(_rec("head north to the bridge", intent))
    for direction in ("south", "east", "west", "east", "south"):  # truthful elsewhere
        records.append(_rec(f"I am really going {direction}", "truth"))
    return records


def test_north_liar_is_flagged_and_distrusted():
    profiler = OpponentProfiler(CFG, rng=random.Random(0))
    profiler.ingest_subgame(_north_liar_records(random.Random(0)), opponent_role="thief")

    summary = profiler.profile()
    assert "N" in summary["flagged_directions"]
    assert profiler.per_direction_bias()["N"] == pytest.approx(0.8)
    assert 0.5 < summary["lie_rate"] < 0.9
    assert profiler.trust_prior() < 0.5


def test_all_truthful_opponent_earns_trust():
    profiler = OpponentProfiler(CFG)
    records = [_rec(f"honestly heading {w}", "truth") for w in ("north", "south", "east", "west")]
    profiler.ingest_subgame(records * 3, opponent_role="police")

    assert profiler.trust_prior() >= 0.5
    assert profiler.flagged_directions() == []
    assert profiler.lie_rate() == 0.0


def test_unseen_opponent_seeds_neutral_prior():
    profiler = OpponentProfiler(CFG)
    assert profiler.trust_prior() == pytest.approx(0.5)
    assert profiler.profile()["samples"] == 0


def test_system_rows_without_intent_are_ignored():
    profiler = OpponentProfiler(CFG)
    profiler.ingest_subgame([{"payload": {"type": "system_spec", "step": 0}}], "thief")
    assert profiler.profile()["samples"] == 0
    assert profiler.trust_prior() == pytest.approx(0.5)


def test_truthfulness_near_barriers_is_measured():
    profiler = OpponentProfiler(CFG)
    near = "grid=7x7;self=[3, 3];barriers=[[3, 4], [2, 3]]"
    far = "grid=7x7;self=[0, 0];barriers=[[6, 6]]"
    records = [
        _rec("truthful when boxed in", "truth", position=(3, 3), state=near),
        _rec("bluff in the open", "lie", position=(0, 0), state=far),
    ]
    profiler.ingest_subgame(records, "police")
    summary = profiler.profile()
    assert summary["near_barrier_truth_rate"] == pytest.approx(1.0)
    assert summary["far_barrier_truth_rate"] == pytest.approx(0.0)


def test_phrasing_repetition_and_top_phrase():
    profiler = OpponentProfiler(CFG)
    records = [_rec("same tired line", "lie") for _ in range(3)] + [_rec("fresh", "truth")]
    profiler.ingest_subgame(records, "thief")
    summary = profiler.profile()
    assert summary["top_phrase"] == "same tired line"
    assert summary["phrasing_repetition_rate"] == pytest.approx(2 / 4)


def test_raw_payload_records_are_accepted():
    profiler = OpponentProfiler(CFG)
    profiler.ingest_subgame([{"hint": "going north", "intent": "lie", "position": [3, 3]}], "thief")
    assert profiler.lie_rate() == 1.0


@pytest.mark.parametrize("missing", ["hint_alpha0", "hint_beta0", "move_set"])
def test_missing_config_term_is_rejected(missing):
    cfg = {k: v for k, v in CFG.items() if k != missing}
    with pytest.raises(ConfigError):
        OpponentProfiler(cfg)


def test_nonpositive_prior_is_rejected():
    with pytest.raises(ConfigError):
        OpponentProfiler({**CFG, "hint_alpha0": 0.0})
