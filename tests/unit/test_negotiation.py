"""Unit tests for pursuit.domain.negotiation — terms build/sign/verify (INTEROP §2.1/§3.3)."""

import copy
import json
from pathlib import Path

import pytest

from pursuit.domain.negotiation import (
    DIALECT_TERM_SOURCES,
    WIRE_TERM_SOURCES,
    agreement_signature,
    build_terms,
    verify_agreement_signature,
    verify_terms,
)
from pursuit.exceptions import ConfigError, NegotiationError
from pursuit.shared.config import ConfigManager

ROOT = Path(__file__).resolve().parents[2]

#: INTEROP §2.1 worked example (num_games=1, decay 0.1) — recomputed 2026-07-13.
GOLDEN_TERMS = {
    "board_size": 7, "smell_grid_size": 5, "decay_per_step": 0.1,
    "emit_intensity": 0.9, "min_center_intensity": 0.5,
    "max_steps": 35, "barriers_max": 14,
    "setting": "New York", "hint_max_words": 15,
    "axis_origin_corner": "top-left", "axis_start_index": 0,
    "thief_start": [3, 3], "cop_start": [0, 0], "num_games": 1,
}
GOLDEN_NONCE = "0f0e0d0c0b0a09080706050403020100"
GOLDEN_SIGNATURE = "167fef4e1881492a35297832f78a550e3ffd909e69a21f259cf09c58b887472d"


def make_config(mutate=None) -> ConfigManager:
    """Real shipped police game.json (optionally mutated) + minimal private tree."""
    game = json.loads((ROOT / "config" / "police" / "game.json").read_text(encoding="utf-8"))
    if mutate is not None:
        mutate(game)
    return ConfigManager(game_terms=game, private_terms={}, rate_limits={})


class TestBuildTerms:
    def test_exactly_the_14_wire_keys_by_default(self):
        terms = build_terms(make_config())
        assert set(terms) == set(WIRE_TERM_SOURCES)
        assert len(terms) == 14

    def test_values_come_from_config_not_code(self):
        cfg = make_config()
        terms = build_terms(cfg)
        for wire_key, path in WIRE_TERM_SOURCES.items():
            assert terms[wire_key] == cfg.game(path)

    def test_changed_config_value_flows_through(self):
        def bump(game):
            game["board_and_agents"]["grid_size"] = 9

        assert build_terms(make_config(bump))["board_size"] == 9

    def test_missing_source_term_fails_fast(self):
        def drop(game):
            del game["world"]["map_area"]

        with pytest.raises(ConfigError, match="world.map_area"):
            build_terms(make_config(drop))

    def test_dialect_keys_injected_only_under_flag(self):
        def enable(game):
            game["negotiation"] = {"wire_dialect_terms": True}

        terms = build_terms(make_config(enable))
        assert set(terms) == set(WIRE_TERM_SOURCES) | set(DIALECT_TERM_SOURCES)
        assert terms["crypto_dialect"] == "reference"
        assert terms["scent_dialect"] == "reference"

    def test_flag_false_keeps_stock_shape(self):
        def disable(game):
            game["negotiation"] = {"wire_dialect_terms": False}

        assert set(build_terms(make_config(disable))) == set(WIRE_TERM_SOURCES)

    def test_non_boolean_flag_rejected(self):
        def garbage(game):
            game["negotiation"] = {"wire_dialect_terms": "yes"}

        with pytest.raises(ConfigError, match="wire_dialect_terms"):
            build_terms(make_config(garbage))


class TestAgreementSignature:
    def test_interop_2_1_golden_vector(self):
        assert agreement_signature(GOLDEN_TERMS, GOLDEN_NONCE) == GOLDEN_SIGNATURE

    def test_verify_round_trip_and_tamper(self):
        assert verify_agreement_signature(GOLDEN_TERMS, GOLDEN_NONCE, GOLDEN_SIGNATURE)
        tampered = "0" + GOLDEN_SIGNATURE[1:]  # golden starts with "1" — guaranteed different
        assert not verify_agreement_signature(GOLDEN_TERMS, GOLDEN_NONCE, tampered)
        assert not verify_agreement_signature(GOLDEN_TERMS, "f" * 32, GOLDEN_SIGNATURE)

    def test_key_order_never_matters(self):
        shuffled = dict(reversed(list(GOLDEN_TERMS.items())))
        assert agreement_signature(shuffled, GOLDEN_NONCE) == GOLDEN_SIGNATURE


class TestVerifyTerms:
    def test_equal_terms_pass(self):
        verify_terms(GOLDEN_TERMS, copy.deepcopy(GOLDEN_TERMS))  # must not raise

    @pytest.mark.parametrize("key", ["board_size", "setting", "thief_start", "num_games"])
    def test_diverging_value_names_the_key(self, key):
        theirs = copy.deepcopy(GOLDEN_TERMS)
        theirs[key] = "DIFFERENT"
        with pytest.raises(NegotiationError, match=f"terms mismatch at '{key}'"):
            verify_terms(GOLDEN_TERMS, theirs)

    def test_first_diverging_key_in_sorted_order(self):
        theirs = copy.deepcopy(GOLDEN_TERMS)
        theirs["setting"] = "Paris"
        theirs["board_size"] = 9  # sorts before 'setting' -> must be the one named
        with pytest.raises(NegotiationError, match="terms mismatch at 'board_size'"):
            verify_terms(GOLDEN_TERMS, theirs)

    def test_missing_key_named(self):
        theirs = copy.deepcopy(GOLDEN_TERMS)
        del theirs["cop_start"]
        with pytest.raises(NegotiationError, match="'cop_start'.*missing"):
            verify_terms(GOLDEN_TERMS, theirs)

    def test_extra_unagreed_key_named(self):
        theirs = copy.deepcopy(GOLDEN_TERMS)
        theirs["crypto_dialect"] = "book"  # the D3 landmine: extra keys must refuse
        with pytest.raises(NegotiationError, match="'crypto_dialect'.*extra"):
            verify_terms(GOLDEN_TERMS, theirs)

    @pytest.mark.parametrize("value", ["0.1", 1, True])
    def test_wire_type_mismatch_refused(self, value):
        theirs = copy.deepcopy(GOLDEN_TERMS)
        theirs["decay_per_step"] = value  # float 0.1 vs str/int/bool — landmine 9
        with pytest.raises(NegotiationError, match="'decay_per_step'"):
            verify_terms(GOLDEN_TERMS, theirs)

    def test_non_dict_terms_refused(self):
        with pytest.raises(NegotiationError, match="not a dict"):
            verify_terms(GOLDEN_TERMS, ["not", "a", "dict"])
