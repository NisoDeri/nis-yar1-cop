"""Vocabulary guards: wire literals and StrEnum semantics of pursuit.constants."""

from pursuit.constants import DIRECTION_DELTAS, Direction, GameResult, MoveType, Role


def test_role_opponent_is_an_involution() -> None:
    assert Role.POLICE.opponent is Role.THIEF
    assert Role.THIEF.opponent is Role.POLICE
    assert Role.POLICE.opponent.opponent is Role.POLICE


def test_enums_serialize_to_bare_wire_values() -> None:
    # StrEnum: str()/f-string yields the pinned wire literal, not "Role.POLICE".
    assert str(Role.POLICE) == "police"
    assert f"MOVE:{Direction.N}" == "MOVE:N"
    assert str(MoveType.BARRIER) == "BARRIER"
    assert str(GameResult.TECHNICAL_LOSS) == "technical_loss"


def test_direction_deltas_cover_every_direction() -> None:
    assert set(DIRECTION_DELTAS) == set(Direction)
    assert DIRECTION_DELTAS[Direction.STAY] == (0, 0)
    # Origin top-left, row grows downward (book Table 13).
    assert DIRECTION_DELTAS[Direction.N] == (-1, 0)
    assert DIRECTION_DELTAS[Direction.S] == (1, 0)
    assert DIRECTION_DELTAS[Direction.E] == (0, 1)
    assert DIRECTION_DELTAS[Direction.W] == (0, -1)
