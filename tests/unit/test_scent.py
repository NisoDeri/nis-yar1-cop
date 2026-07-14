"""Unit tests for pursuit.domain.scent — both dialects, factory, wire round-trip."""

import pytest

from pursuit.domain.scent import (
    BookScent,
    ReferenceScent,
    ScentModel,
    ScentParams,
    make_scent_model,
)
from pursuit.exceptions import ConfigError

CFG = {
    "board_size": 7,
    "smell_grid_size": 5,
    "emit_intensity": 0.9,
    "decay_per_step": 0.10,
    "min_center_intensity": 0.5,
}
DIALECTS = [BookScent, ReferenceScent]


def make(dialect_cls: type[ScentModel], **overrides) -> ScentModel:
    return dialect_cls(ScentParams(**{**CFG, **overrides}))


class TestFactory:
    def test_default_dialect_is_book(self) -> None:
        assert isinstance(make_scent_model(dict(CFG)), BookScent)

    def test_explicit_book(self) -> None:
        assert isinstance(make_scent_model({**CFG, "dialect": "book"}), BookScent)

    def test_explicit_reference(self) -> None:
        assert isinstance(make_scent_model({**CFG, "dialect": "reference"}), ReferenceScent)

    def test_unknown_dialect_raises(self) -> None:
        with pytest.raises(ConfigError, match="dialect"):
            make_scent_model({**CFG, "dialect": "quantum"})

    @pytest.mark.parametrize("missing", sorted(CFG))
    def test_missing_term_raises(self, missing: str) -> None:
        cfg = {k: v for k, v in CFG.items() if k != missing}
        with pytest.raises(ConfigError, match=missing):
            make_scent_model(cfg)


class TestParamsValidation:
    @pytest.mark.parametrize("board_size", [0, -1, 6.5])
    def test_bad_board_size(self, board_size) -> None:
        with pytest.raises(ConfigError, match="board_size"):
            ScentParams(**{**CFG, "board_size": board_size})

    @pytest.mark.parametrize("grid", [0, -5, 4])  # even sizes have no center cell
    def test_bad_grid_size(self, grid: int) -> None:
        with pytest.raises(ConfigError, match="smell_grid_size"):
            ScentParams(**{**CFG, "smell_grid_size": grid})

    @pytest.mark.parametrize("rho", [-0.1, 1.5])
    def test_decay_out_of_range(self, rho: float) -> None:
        with pytest.raises(ConfigError, match="decay_per_step"):
            ScentParams(**{**CFG, "decay_per_step": rho})

    def test_non_numeric_term(self) -> None:
        with pytest.raises(ConfigError, match="number"):
            ScentParams(**{**CFG, "decay_per_step": "0.1"})

    def test_non_positive_emit(self) -> None:
        with pytest.raises(ConfigError, match="emit_intensity"):
            ScentParams(**{**CFG, "emit_intensity": 0})

    def test_emit_below_anti_decoy_floor(self) -> None:
        with pytest.raises(ConfigError, match="anti-decoy"):
            ScentParams(**{**CFG, "emit_intensity": 0.4})


@pytest.mark.parametrize("dialect_cls", DIALECTS)
class TestDepositProfile:
    """The shared stamp law: 0.9 / 0.6 / 0.3 Chebyshev rings, 3-dp rounding."""

    def test_center_deposit_rings(self, dialect_cls) -> None:
        model = make(dialect_cls)
        model.deposit((3, 3))
        snap = model.snapshot()
        assert snap["3,3"] == 0.9  # ring 0 (center)
        assert snap["3,4"] == 0.6 and snap["2,2"] == 0.6  # ring 1
        assert snap["3,5"] == 0.3 and snap["1,1"] == 0.3  # ring 2
        assert len(snap) == 25  # full 5x5 window in bounds

    def test_corner_deposit_clipped_to_board(self, dialect_cls) -> None:
        model = make(dialect_cls)
        model.deposit((0, 0))
        snap = model.snapshot()
        assert len(snap) == 9  # 3x3 quadrant survives
        assert snap["0,0"] == 0.9 and snap["2,2"] == 0.3

    def test_deposit_off_board_raises(self, dialect_cls) -> None:
        with pytest.raises(ValueError, match="outside"):
            make(dialect_cls).deposit((7, 0))

    def test_strongest_is_deposit_center(self, dialect_cls) -> None:
        model = make(dialect_cls)
        model.deposit((3, 3))
        assert model.strongest() == (3, 3)


class TestDecayCurves:
    """Numeric divergence of the two decay laws over 5 turns (rule-23 material)."""

    def test_book_multiplicative_curve(self) -> None:
        model = make(BookScent)
        model.deposit((3, 3))
        centers, ring1 = [], []
        for _ in range(5):
            model.decay()
            snap = model.snapshot()
            centers.append(snap["3,3"])
            ring1.append(snap["3,4"])
        assert centers == [0.81, 0.729, 0.656, 0.59, 0.531]  # 0.9 * 0.9^k
        assert ring1 == [0.54, 0.486, 0.437, 0.394, 0.354]  # 0.6 * 0.9^k

    def test_reference_subtractive_curve(self) -> None:
        model = make(ReferenceScent)
        model.deposit((3, 3))
        centers = []
        for _ in range(5):
            model.decay()
            centers.append(model.snapshot()["3,3"])
        assert centers == [0.8, 0.7, 0.6, 0.5, 0.4]  # 0.9 - k * 0.1

    def test_reference_prunes_exhausted_ring(self) -> None:
        model = make(ReferenceScent)
        model.deposit((3, 3))
        for _ in range(3):
            model.decay()
        snap = model.snapshot()  # ring 2 (0.3) hits zero on the 3rd decay
        assert "1,1" not in snap and len(snap) == 9

    def test_book_never_reaches_zero_at_default_rho(self) -> None:
        model = make(BookScent)
        model.deposit((3, 3))
        for _ in range(5):
            model.decay()
        assert len(model.snapshot()) == 25

    def test_book_prunes_sub_wire_residue(self) -> None:
        model = make(BookScent, decay_per_step=0.9995, min_center_intensity=0.0)
        model.deposit((3, 3))
        model.decay()  # 0.9 * 0.0005 = 0.00045 -> rounds to 0.000 -> pruned
        assert model.snapshot() == {} and model.strongest() is None

    def test_reference_full_decay_empties_grid(self) -> None:
        model = make(ReferenceScent, decay_per_step=1.0, min_center_intensity=0.0)
        model.deposit((3, 3))
        model.decay()
        assert model.snapshot() == {} and model.strongest() is None


class TestMergeLaw:
    """Additive-with-cap vs max-merge — the observable dialect split."""

    def test_overlap_adds_in_book_but_maxes_in_reference(self) -> None:
        values = {}
        for cls in DIALECTS:
            model = make(cls)
            model.deposit((3, 3))
            model.deposit((3, 4))
            values[cls.dialect] = model.snapshot()
        # (1,2) is ring 2 (0.3) of BOTH stamps: additive doubles, max keeps.
        assert values["book"]["1,2"] == 0.6
        assert values["reference"]["1,2"] == 0.3

    def test_book_clamp_after_add_caps_at_emit_intensity(self) -> None:
        model = make(BookScent)
        model.deposit((3, 3))
        model.deposit((3, 4))
        snap = model.snapshot()
        assert max(snap.values()) == 0.9  # 0.9 + 0.6 clamps to E0, never 1.5
        # Cap-plateau (STRATEGY §2.3): the clamp saturates MORE cells at E0
        # than the two true centers — argmax uniqueness is gone.
        assert sum(1 for v in snap.values() if v == 0.9) > 2

    def test_reference_peak_cells_are_exactly_the_centers(self) -> None:
        model = make(ReferenceScent)
        model.deposit((3, 3))
        model.deposit((3, 4))
        peaks = {k for k, v in model.snapshot().items() if v == 0.9}
        assert peaks == {"3,3", "3,4"}

    @pytest.mark.parametrize("dialect_cls", DIALECTS)
    def test_strongest_tie_breaks_row_major(self, dialect_cls) -> None:
        model = make(dialect_cls)
        model.deposit((5, 5))  # two equal 0.9 centers, greater cell deposited first:
        model.deposit((1, 1))  # deposit order must not matter, row-major must win
        assert model.strongest() == (1, 1)


@pytest.mark.parametrize("dialect_cls", DIALECTS)
class TestWireFormat:
    def test_snapshot_round_trips_via_absorb(self, dialect_cls) -> None:
        model = make(dialect_cls)
        model.deposit((3, 3))
        model.decay()
        model.deposit((5, 1))
        snap = model.snapshot()
        mirror = make(dialect_cls)
        mirror.absorb(snap)
        assert mirror.snapshot() == snap

    def test_absorb_is_idempotent_replace(self, dialect_cls) -> None:
        model = make(dialect_cls)
        model.deposit((0, 0))  # pre-existing local state is replaced, not merged
        model.absorb({"2,3": 0.9, "2,4": 0.6})
        model.absorb({"2,3": 0.9, "2,4": 0.6})  # legal wire duplicate
        assert model.snapshot() == {"2,3": 0.9, "2,4": 0.6}
        assert model.strongest() == (2, 3)

    def test_absorb_drops_non_positive_cells(self, dialect_cls) -> None:
        model = make(dialect_cls)
        model.absorb({"1,1": 0.4, "2,2": 0.0, "3,3": -0.5})
        assert model.snapshot() == {"1,1": 0.4}

    def test_absorb_malformed_key_raises(self, dialect_cls) -> None:
        model = make(dialect_cls)
        for bad in ({"2;3": 0.5}, {"2,3,4": 0.5}, {"a,b": 0.5}):
            with pytest.raises(ValueError, match="malformed"):
                model.absorb(bad)

    def test_absorb_off_board_cell_raises(self, dialect_cls) -> None:
        with pytest.raises(ValueError, match="outside"):
            make(dialect_cls).absorb({"9,9": 0.5})

    def test_snapshot_keys_row_major(self, dialect_cls) -> None:
        model = make(dialect_cls)
        model.deposit((3, 3))
        keys = [tuple(int(p) for p in key.split(",")) for key in model.snapshot()]
        assert keys == sorted(keys)

    def test_strongest_on_empty_field_is_none(self, dialect_cls) -> None:
        assert make(dialect_cls).strongest() is None


class TestWorkedExample:
    """The rule-23 lock artifact: deterministic, dialect-labeled, divergent."""

    def test_deterministic_across_calls_and_instances(self) -> None:
        for cls in DIALECTS:
            model = make(cls)
            assert model.worked_example() == model.worked_example() == make(cls).worked_example()

    def test_dialect_labels_and_formula_texts(self) -> None:
        book, ref = make(BookScent).worked_example(), make(ReferenceScent).worked_example()
        assert book["dialect"] == "book" and "clamp-after-add" in book["formula"]
        assert ref["dialect"] == "reference" and "max-merge" in ref["formula"]

    def test_same_operations_different_grids_proves_the_lock_matters(self) -> None:
        book, ref = make(BookScent).worked_example(), make(ReferenceScent).worked_example()
        assert book["operations"] == ref["operations"] == ["deposit((3, 3))", "decay()"]
        assert book["grid"] != ref["grid"]
        assert book["grid"]["3,3"] == 0.81  # 0.9 * (1 - 0.1)
        assert ref["grid"]["3,3"] == 0.8  # 0.9 - 0.1
        assert len(book["grid"]) == len(ref["grid"]) == 25

    def test_example_board_is_fixed_regardless_of_game_board(self) -> None:
        example = make(BookScent, board_size=9).worked_example()
        assert example["params"]["board_size"] == 7
        assert example["params"]["emit_intensity"] == CFG["emit_intensity"]

    def test_example_locks_the_rounding_contract(self) -> None:
        assert "round(v, 3)" in make(ReferenceScent).worked_example()["rounding"]
