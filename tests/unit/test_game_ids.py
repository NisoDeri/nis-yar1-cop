"""Unit tests for pursuit.domain.game_ids — INTEROP §3.2 golden vector + determinism."""

from __future__ import annotations

import json

import pytest

from pursuit.domain.game_ids import derive_game_ids
from pursuit.exceptions import ConfigError

# The INTEROP §3.2 worked example, loaded through JSON so float repr matches the wire
# (0.10 must canonicalize as 0.1).
GOLDEN_TERMS: dict = json.loads(
    '{"board_size": 7, "smell_grid_size": 5, "decay_per_step": 0.10,'
    ' "emit_intensity": 0.9, "min_center_intensity": 0.5,'
    ' "max_steps": 35, "barriers_max": 14,'
    ' "setting": "New York", "hint_max_words": 15,'
    ' "axis_origin_corner": "top-left", "axis_start_index": 0,'
    ' "thief_start": [3, 3], "cop_start": [0, 0], "num_games": 1}'
)
GOLDEN_GIDS = ["segal-police-team", "segal-thief-team"]
GOLDEN_UID = "7132f6ae-5e09-92a9-3e85-625e138e52cb"
GOLDEN_ID = "segal-police-team-vs-segal-thief-team"


def test_golden_worked_example_from_interop() -> None:
    game_id, game_uid = derive_game_ids(GOLDEN_TERMS, GOLDEN_GIDS)
    assert game_id == GOLDEN_ID
    assert game_uid == GOLDEN_UID


def test_group_order_is_normalized() -> None:
    forward = derive_game_ids(GOLDEN_TERMS, GOLDEN_GIDS)
    swapped = derive_game_ids(GOLDEN_TERMS, list(reversed(GOLDEN_GIDS)))
    assert forward == swapped == (GOLDEN_ID, GOLDEN_UID)


def test_same_inputs_same_uid_and_key_order_irrelevant() -> None:
    reordered = dict(reversed(list(GOLDEN_TERMS.items())))
    assert derive_game_ids(reordered, GOLDEN_GIDS) == (GOLDEN_ID, GOLDEN_UID)


def test_any_differing_term_changes_the_uid() -> None:
    for key, value in [("num_games", 6), ("decay_per_step", 0.2), ("setting", "Haifa")]:
        mutated = {**GOLDEN_TERMS, key: value}
        _, uid = derive_game_ids(mutated, GOLDEN_GIDS)
        assert uid != GOLDEN_UID, key


def test_different_groups_change_uid_but_not_terms_binding() -> None:
    game_id, uid = derive_game_ids(GOLDEN_TERMS, ["nis-yar1", "zzz-team"])
    assert game_id == "nis-yar1-vs-zzz-team"
    assert uid != GOLDEN_UID


def test_uid_is_not_rfc4122_normalized() -> None:
    # INTEROP §3.2: version/variant bits are whatever sha256 produced — the golden uid's
    # version nibble is 9, which a "proper" UUID library would never emit for v1-v5.
    assert GOLDEN_UID[14] == "9"
    _, uid = derive_game_ids(GOLDEN_TERMS, GOLDEN_GIDS)
    assert uid == GOLDEN_UID  # copied byte-for-byte, never re-normalized


def test_non_ascii_terms_hash_as_utf8_deterministically() -> None:
    hebrew = {**GOLDEN_TERMS, "setting": "חיפה"}
    first = derive_game_ids(hebrew, GOLDEN_GIDS)
    second = derive_game_ids(json.loads(json.dumps(hebrew, ensure_ascii=False)), GOLDEN_GIDS)
    assert first == second
    assert first[1] != GOLDEN_UID


@pytest.mark.parametrize(
    "bad_gids",
    [[], ["only-one"], ["a", "b", "c"], ["ok", ""], ["ok", 7]],
)
def test_bad_group_ids_raise_config_error(bad_gids: list) -> None:
    with pytest.raises(ConfigError):
        derive_game_ids(GOLDEN_TERMS, bad_gids)


def test_empty_terms_raise_config_error() -> None:
    with pytest.raises(ConfigError):
        derive_game_ids({}, GOLDEN_GIDS)
