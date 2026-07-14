"""Unit tests for the opt-in E6 Step-0 rule-delta capability (CREATIVITY-DESIGN E6).

Default OFF: no ``rule_deltas`` key unless ``negotiation.propose_rule_deltas`` is set.
SAFETY INVARIANT: a delta may only RAISE a value above its book minimum, never lower a
floor. Peers bind a delta only when both signed the SAME (value-equal) block.
"""

import json
from pathlib import Path

import pytest

from pursuit.domain.negotiation import (
    RULE_DELTA_SOURCES,
    accept_rule_deltas,
    build_terms,
)
from pursuit.exceptions import ConfigError, NegotiationError
from pursuit.shared.config import ConfigManager

ROOT = Path(__file__).resolve().parents[2]


def make_config(mutate=None) -> ConfigManager:
    """Real shipped police game.json (optionally mutated) + minimal private tree."""
    game = json.loads((ROOT / "config" / "police" / "game.json").read_text(encoding="utf-8"))
    if mutate is not None:
        mutate(game)
    return ConfigManager(game_terms=game, private_terms={}, rate_limits={})


def _set_deltas(overrides):
    def mutate(game):
        game.setdefault("negotiation", {})["propose_rule_deltas"] = overrides

    return mutate


class TestBuildTermsDeltas:
    def test_flag_off_has_no_rule_deltas_key(self):
        assert "rule_deltas" not in build_terms(make_config())

    def test_empty_proposal_stays_off(self):
        assert "rule_deltas" not in build_terms(make_config(_set_deltas({})))

    def test_legal_raise_adds_block(self):
        cfg = make_config(_set_deltas({"max_moves": 45}))
        floor = cfg.game(RULE_DELTA_SOURCES["max_moves"])
        assert floor == 35  # book minimum from game.json — the delta must exceed it
        assert build_terms(cfg)["rule_deltas"] == {"max_moves": 45}

    def test_raise_flows_from_config_not_code(self):
        terms = build_terms(make_config(_set_deltas({"token_budget": 500_000})))
        assert terms["rule_deltas"] == {"token_budget": 500_000}

    def test_delta_at_floor_is_rejected(self):
        floor = make_config().game(RULE_DELTA_SOURCES["max_moves"])
        with pytest.raises(ConfigError, match="must RAISE"):
            build_terms(make_config(_set_deltas({"max_moves": floor})))

    def test_delta_lowering_a_minimum_is_rejected(self):
        with pytest.raises(ConfigError, match="max_moves.*RAISE"):
            build_terms(make_config(_set_deltas({"max_moves": 20})))

    def test_unknown_delta_key_rejected(self):
        with pytest.raises(ConfigError, match="unknown rule delta 'grid_size'"):
            build_terms(make_config(_set_deltas({"grid_size": 9})))

    @pytest.mark.parametrize("bad", ["45", True, [45]])
    def test_non_numeric_delta_rejected(self, bad):
        with pytest.raises(ConfigError, match="max_moves"):
            build_terms(make_config(_set_deltas({"max_moves": bad})))

    def test_non_dict_proposal_rejected(self):
        with pytest.raises(ConfigError, match="must be a JSON object"):
            build_terms(make_config(_set_deltas([("max_moves", 45)])))


class TestAcceptRuleDeltas:
    def test_matching_deltas_merge(self):
        block = {"max_moves": 45, "token_budget": 500_000}
        assert accept_rule_deltas(dict(block), dict(block)) == block

    def test_merge_is_a_fresh_copy(self):
        ours = {"max_moves": 45}
        merged = accept_rule_deltas({"max_moves": 45}, ours)
        merged["max_moves"] = 99
        assert ours["max_moves"] == 45  # returned block must not alias our signed one

    def test_diverging_value_refuses(self):
        with pytest.raises(NegotiationError, match="rule delta 'max_moves'"):
            accept_rule_deltas({"max_moves": 50}, {"max_moves": 45})

    def test_extra_delta_from_opponent_refuses(self):
        with pytest.raises(NegotiationError, match="'token_budget'.*extra"):
            accept_rule_deltas({"max_moves": 45, "token_budget": 500_000}, {"max_moves": 45})

    def test_delta_we_signed_but_they_did_not_refuses(self):
        with pytest.raises(NegotiationError, match="'token_budget'.*not signed"):
            accept_rule_deltas({"max_moves": 45}, {"max_moves": 45, "token_budget": 500_000})

    def test_wire_type_mismatch_refuses(self):
        with pytest.raises(NegotiationError, match="'max_moves'"):
            accept_rule_deltas({"max_moves": 45}, {"max_moves": 45.0})

    def test_non_dict_block_refused(self):
        with pytest.raises(NegotiationError, match="not a dict"):
            accept_rule_deltas(["max_moves", 45], {"max_moves": 45})
