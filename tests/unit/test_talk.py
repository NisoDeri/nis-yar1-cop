"""Unit tests for TemplateTalk — zero-token hints, mechanical caps, rule-27 lint."""

from __future__ import annotations

import random

import pytest

from pursuit.constants import Role
from pursuit.exceptions import ConfigError
from pursuit.strategy.talk import BANK_LINES, LIE, TRUTH, TemplateTalk

# Test-local wire parameters (production values come from the signed game.json terms).
HINT_MAX_WORDS = 15
SETTINGS = ("New York", "London", "Paris", "", "Atlantis")
NY_LANDMARKS = ("times square", "central park", "brooklyn bridge", "grand central",
                "the village", "wall street")


def make_talk(setting: str = "New York", cap: int = HINT_MAX_WORDS, seed: int = 0,
              **kwargs) -> TemplateTalk:
    return TemplateTalk(random.Random(seed), setting, cap, **kwargs)


def say(talk: TemplateTalk, role: Role = Role.THIEF, setting: str = ""):
    return talk.say(role, None, None, setting, "", None)


# --- the bank itself --------------------------------------------------------------------------
def test_bank_has_at_least_forty_unique_lines() -> None:
    assert len(BANK_LINES) >= 40
    assert len(set(BANK_LINES)) == len(BANK_LINES)


def test_bank_lint_every_line_is_digit_free() -> None:
    for line in BANK_LINES:  # rule 27: numeric coordinates never leave the talk layer
        assert not any(ch.isdigit() for ch in line), line


# --- word cap (STRATEGY §8.3: enforced mechanically, template AND LLM output) -----------------
@pytest.mark.parametrize("cap", [1, 3, 7])
def test_word_cap_enforced_for_both_roles(cap: int) -> None:
    talk = make_talk(cap=cap)
    for role in (Role.THIEF, Role.POLICE):
        for _ in range(60):
            hint, _verdict, _reasoning, _prompt = say(talk, role)
            assert 1 <= len(hint.split()) <= cap


def test_generous_cap_leaves_truth_lines_intact() -> None:
    talk = make_talk(cap=50, lie_rate=0.0)  # truth pool has no {landmark} placeholder
    for _ in range(30):
        assert say(talk)[0] in BANK_LINES


# --- rule 27: no digits in any emitted hint ---------------------------------------------------
def test_no_digits_ever_reach_the_wire() -> None:
    for setting in SETTINGS:
        talk = make_talk(setting=setting, seed=7)
        for role in (Role.THIEF, Role.POLICE):
            for _ in range(40):
                hint, _v, _r, _p = say(talk, role)
                assert not any(ch.isdigit() for ch in hint), hint


# --- verdict labelling (STRATEGY §8.9: one source of truth for intent) ------------------------
def test_verdict_literals_and_prompt_shape() -> None:
    talk = make_talk(seed=3, lie_rate=0.5)
    seen = set()
    for _ in range(200):
        hint, verdict, reasoning, prompt = say(talk)
        assert verdict in (TRUTH, LIE)
        assert hint and reasoning and prompt == ""  # template mode never has an LLM prompt
        seen.add(verdict)
    assert seen == {TRUTH, LIE}  # both intents occur at lie_rate=0.5


def test_zero_lie_rate_is_pure_truth_mode() -> None:
    talk = make_talk(lie_rate=0.0)
    assert all(say(talk)[1] == TRUTH for _ in range(80))


# --- landmark awareness -----------------------------------------------------------------------
def test_landmarks_follow_the_configured_setting() -> None:
    talk = make_talk(setting="New York", seed=1, lie_rate=1.0)  # lie pool is landmark-bearing
    hints = " | ".join(say(talk)[0].lower() for _ in range(60))
    assert any(mark in hints for mark in NY_LANDMARKS)
    assert "big ben" not in hints and "eiffel" not in hints


def test_say_setting_argument_overrides_constructor_setting() -> None:
    talk = make_talk(setting="Paris", seed=1, lie_rate=1.0)
    hints = " | ".join(say(talk, setting="London")[0].lower() for _ in range(60))
    assert "big ben" in hints or "camden" in hints or "tower bridge" in hints or (
        "soho" in hints or "piccadilly" in hints or "tube" in hints
    )
    assert "eiffel" not in hints and "louvre" not in hints


def test_unknown_setting_falls_back_to_generic_landmarks() -> None:
    talk = make_talk(setting="Atlantis", seed=2, lie_rate=1.0)
    hints = " | ".join(say(talk)[0].lower() for _ in range(60))
    assert any(mark in hints for mark in ("old market", "clock tower", "river bend",
                                          "north gate"))


# --- constructor validation -------------------------------------------------------------------
@pytest.mark.parametrize("bad_cap", [0, -3])
def test_rejects_nonpositive_word_cap(bad_cap: int) -> None:
    with pytest.raises(ConfigError, match="hint_max_words"):
        make_talk(cap=bad_cap)


@pytest.mark.parametrize("bad_rate", [-0.1, 1.5])
def test_rejects_out_of_range_lie_rate(bad_rate: float) -> None:
    with pytest.raises(ConfigError, match="lie_rate"):
        make_talk(lie_rate=bad_rate)
