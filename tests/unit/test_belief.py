"""Unit tests for pursuit.domain.belief — BeliefV2 filter, kernels, reliability.

Pure in-process math: no sockets, no processes, no LLMs. Opponent scent is
emitted by the real ScentModel dialects so the emission inversion is tested
against the byte-faithful locked law it will meet on the wire.
"""

import math

import pytest

from pursuit.constants import Role
from pursuit.domain.belief import BeliefV2, ReliabilityLedger
from pursuit.domain.belief.kernel import apply_kernel, mobility, transition_row, utility
from pursuit.domain.belief.likelihood import (
    absolute_log_likelihood,
    forward_snapshot,
    residual_log_likelihood,
)
from pursuit.domain.belief.reliability import hint_footprint, trail_centroid
from pursuit.domain.board import Board
from pursuit.domain.scent import make_scent_model
from pursuit.exceptions import ConfigError

PHEROMONES = {
    "board_size": 7,
    "smell_grid_size": 5,
    "emit_intensity": 0.9,
    "decay_per_step": 0.10,
    "min_center_intensity": 0.5,
}
MOVES = ["N", "S", "E", "W", "STAY"]
CFG = {
    "move_set": MOVES,
    "sigma_obs": 0.02,
    "zero_scent_weight": 2.0,
    "resync_floor": 1e-9,
    "motion_eta_thief": 2.0,
    "motion_eta_police": 2.0,
    "kernel_mobility_mu": 0.3,
    "kernel_mobility_k": 3,
    "lie_inversion": False,
    "lie_inversion_below": 0.25,
    "hint_alpha0": 1.0,
    "hint_beta0": 1.0,
    "reliability_forget": 0.95,
    "injection_penalty": 5.0,
    "zones": {
        "park": [[0, 0], [0, 1], [1, 0], [1, 1]],
        "docks": [[0, 5], [0, 6], [1, 5], [1, 6]],
    },
}
DIALECTS = ["reference", "book"]


def pheromones(dialect: str = "reference") -> dict:
    return {**PHEROMONES, "dialect": dialect}


def engine(dialect: str = "reference", **overrides) -> BeliefV2:
    return BeliefV2(7, {**CFG, **overrides}, pheromones(dialect))


def observe_walk(belief: BeliefV2, opponent, cells, role=Role.THIEF) -> None:
    """Drive the canonical TurnHandler order: predict (diffuse) -> update (observe)."""
    for cell in cells:
        opponent.deposit(cell)
        opponent.decay()
        belief.diffuse(role)
        belief.observe_smell(opponent.snapshot())


def matrix_total(belief: BeliefV2) -> float:
    return sum(sum(row) for row in belief.as_matrix())


def all_finite(belief: BeliefV2) -> bool:
    return all(math.isfinite(v) for row in belief.as_matrix() for v in row)


def expected_distance(belief: BeliefV2, ref) -> float:
    m = belief.as_matrix()
    return sum(
        m[r][c] * (abs(r - ref[0]) + abs(c - ref[1])) for r in range(7) for c in range(7)
    )


class TestSurface:
    def test_uniform_start_row_major_argmax(self) -> None:
        b = engine()
        assert b.most_likely() == (0, 0)  # tie-break matches ScentModel.strongest
        assert b.most_likely_p() == pytest.approx(1 / 49)

    def test_as_matrix_shape_and_normalization(self) -> None:
        b = engine()
        m = b.as_matrix()
        assert len(m) == 7 and all(len(row) == 7 for row in m)
        assert matrix_total(b) == pytest.approx(1.0)

    def test_as_matrix_is_a_copy(self) -> None:
        b = engine()
        b.as_matrix()[0][0] = 99.0
        assert b.as_matrix()[0][0] == pytest.approx(1 / 49)

    def test_uniform_entropy_is_log2_of_cells(self) -> None:
        assert engine().entropy() == pytest.approx(math.log2(49))

    def test_accepts_prebuilt_scent_model(self) -> None:
        b = BeliefV2(7, dict(CFG), make_scent_model(pheromones()))
        assert b.most_likely_p() == pytest.approx(1 / 49)


@pytest.mark.parametrize("dialect", DIALECTS)
class TestScentInversion:
    """STRATEGY §2.3-2.4: the emission inversion collapses onto the true cell."""

    def test_concentrates_on_true_cell_within_two_observations(self, dialect) -> None:
        b, opp = engine(dialect), make_scent_model(pheromones(dialect))
        observe_walk(b, opp, [(2, 3), (2, 4)])
        assert b.most_likely() == (2, 4)
        assert b.most_likely_p() > 0.9

    def test_single_observation_already_locates_the_center(self, dialect) -> None:
        b, opp = engine(dialect), make_scent_model(pheromones(dialect))
        observe_walk(b, opp, [(4, 2)])
        assert b.most_likely() == (4, 2)
        assert b.most_likely_p() > 0.99

    def test_far_cells_annihilated_by_zero_scent(self, dialect) -> None:
        b, opp = engine(dialect), make_scent_model(pheromones(dialect))
        observe_walk(b, opp, [(1, 1)])
        m = b.as_matrix()
        assert m[5][5] < 1e-9 and m[6][6] < 1e-9  # their stamp would hit 0.000 cells

    def test_resync_after_lost_history(self, dialect) -> None:
        b, opp = engine(dialect), make_scent_model(pheromones(dialect))
        observe_walk(b, opp, [(1, 1)])  # filter pinned at (1, 1)
        fresh = make_scent_model(pheromones(dialect))  # unrelated trail = lost messages
        fresh.deposit((5, 5))
        fresh.decay()
        b.observe_smell(fresh.snapshot())  # inconsistent with EVERY candidate
        assert b.most_likely() == (5, 5)  # absolute refit found the new center
        assert matrix_total(b) == pytest.approx(1.0) and all_finite(b)

    def test_duplicate_delivery_is_harmless(self, dialect) -> None:
        b, opp = engine(dialect), make_scent_model(pheromones(dialect))
        observe_walk(b, opp, [(2, 2), (2, 3), (2, 4)])
        b.observe_smell(opp.snapshot())  # legal duplicate (reference_map §3)
        # The true cell must sit on the argmax plateau. Under the book dialect
        # stacked stale cells clamp at E0 and may TIE with the fresh center —
        # the cap-plateau ambiguity of STRATEGY §1.2; reference stays unique.
        assert b.as_matrix()[2][4] == pytest.approx(b.most_likely_p())
        if dialect == "reference":
            assert b.most_likely() == (2, 4)
        assert matrix_total(b) == pytest.approx(1.0) and all_finite(b)

    def test_observe_rejects_dishonest_wire_data(self, dialect) -> None:
        b = engine(dialect)
        with pytest.raises(ValueError, match="malformed"):
            b.observe_smell({"2;3": 0.5})
        with pytest.raises(ValueError, match="outside"):
            b.observe_smell({"9,9": 0.5})


class TestZeroScentEvidence:
    """The lambda_zero branch: zero cells inside a would-be stamp are evidence."""

    def test_zero_observed_cells_carry_the_configured_weight(self) -> None:
        predicted = {"3,3": 0.8, "3,4": 0.5}
        weak = residual_log_likelihood({}, predicted, 0.02, 1.0)
        strong = residual_log_likelihood({}, predicted, 0.02, 2.0)
        assert strong == pytest.approx(2.0 * weak)  # every term hit the zero branch
        assert strong < weak < 0.0

    def test_nonzero_observed_cells_use_unit_weight(self) -> None:
        observed, predicted = {"3,3": 0.7}, {"3,3": 0.8}
        assert residual_log_likelihood(observed, predicted, 0.02, 5.0) == pytest.approx(
            residual_log_likelihood(observed, predicted, 0.02, 1.0)
        )

    def test_exact_match_scores_zero(self) -> None:
        snap = {"3,3": 0.8, "3,4": 0.5}
        assert residual_log_likelihood(snap, snap, 0.02, 2.0) == 0.0

    def test_absolute_fit_ignores_stale_surplus_penalizes_deficit(self) -> None:
        fresh = {"3,3": 0.8, "3,4": 0.5}
        surplus = {"3,3": 0.8, "3,4": 0.9, "0,0": 0.4}  # stale trail on top is lawful
        assert absolute_log_likelihood(surplus, fresh, 0.02, 2.0) == 0.0
        deficit = {"3,3": 0.8}  # ring cell missing -> impossible at the true cell
        assert absolute_log_likelihood(deficit, fresh, 0.02, 2.0) < -100.0

    def test_forward_snapshot_replays_the_sender_order(self) -> None:
        model = make_scent_model(pheromones())
        opp = make_scent_model(pheromones())
        opp.deposit((3, 3))
        opp.decay()
        assert forward_snapshot(model, {}, (3, 3)) == opp.snapshot()


class TestKernel:
    """Role-conditioned PREDICT (§2.4): flee/chase around the reference point."""

    def board(self) -> Board:
        return Board(7, MOVES)

    def test_eta_zero_recovers_uniform_diffuse(self) -> None:
        row = transition_row(self.board(), set(), (3, 1), (3, 3), Role.THIEF, 0.0, 0.3, 3)
        assert set(row) == {(3, 1), (2, 1), (4, 1), (3, 0), (3, 2)}
        assert all(p == pytest.approx(1 / 5) for p in row.values())

    def test_police_row_prefers_the_approach_step(self) -> None:
        row = transition_row(self.board(), set(), (3, 1), (3, 3), Role.POLICE, 2.0, 0.3, 3)
        assert max(row, key=row.get) == (3, 2)

    def test_thief_row_shuns_the_approach_step(self) -> None:
        row = transition_row(self.board(), set(), (3, 1), (3, 3), Role.THIEF, 2.0, 0.0, 3)
        assert min(row, key=row.get) == (3, 2)
        assert row[(3, 0)] > row[(3, 1)] > row[(3, 2)]

    def test_rows_are_distributions_and_barrier_aware(self) -> None:
        row = transition_row(self.board(), {(3, 2)}, (3, 1), (3, 3), Role.POLICE, 2.0, 0.3, 3)
        assert (3, 2) not in row
        assert sum(row.values()) == pytest.approx(1.0)

    def test_thief_utility_includes_mobility_bonus(self) -> None:
        board = self.board()
        base = utility(board, set(), (3, 1), (3, 0), (3, 3), Role.THIEF, 0.0, 3)
        rich = utility(board, set(), (3, 1), (3, 0), (3, 3), Role.THIEF, 0.5, 3)
        assert rich == pytest.approx(base + 0.5 * mobility(board, set(), (3, 0), 3))

    def test_police_utility_is_pure_distance_closing(self) -> None:
        assert utility(self.board(), set(), (3, 1), (3, 2), (3, 3), Role.POLICE, 9.0, 3) == 1.0

    def test_apply_kernel_conserves_mass_and_is_pure(self) -> None:
        board = self.board()
        belief = {(r, c): 1 / 49 for r in range(7) for c in range(7)}
        out = apply_kernel(board, set(), belief, (3, 3), Role.THIEF, 2.0, 0.3, 3)
        assert sum(out.values()) == pytest.approx(1.0)
        assert belief[(3, 3)] == pytest.approx(1 / 49)  # input untouched

    def test_engine_diffuse_drifts_away_for_thief(self) -> None:
        b = engine()
        before = expected_distance(b, (3, 3))
        b.diffuse(Role.THIEF, reference=(3, 3))
        assert expected_distance(b, (3, 3)) > before

    def test_engine_diffuse_drifts_toward_for_police(self) -> None:
        b = engine()
        before = expected_distance(b, (3, 3))
        b.diffuse("police", reference=(3, 3))  # wire-string role also accepted
        assert expected_distance(b, (3, 3)) < before


class TestHintFusion:
    """§2.5 mixture: r=0 no-op, r=1 hard mask, bounded damage in between."""

    def test_r_zero_is_a_no_op(self) -> None:
        b, opp = engine(), make_scent_model(pheromones())
        observe_walk(b, opp, [(3, 3)])
        before = b.as_matrix()
        q = b.fuse_hint({"claimed_direction": "S"}, 0.0)
        after = b.as_matrix()
        assert q is not None
        for r in range(7):
            assert after[r] == pytest.approx(before[r])

    def test_r_one_masks_hard_to_the_half_plane(self) -> None:
        b = engine()  # uniform belief -> centroid is the exact board center (3, 3)
        q = b.fuse_hint({"claimed_direction": "S"}, 1.0)
        assert q == pytest.approx(21 / 49)  # prior mass south of the centroid
        m = b.as_matrix()
        assert all(m[r][c] == 0.0 for r in range(4) for c in range(7))
        assert all(m[r][c] == pytest.approx(1 / 21) for r in range(4, 7) for c in range(7))

    def test_zone_claim_masks_to_the_landmark_table(self) -> None:
        b = engine()
        q = b.fuse_hint({"claimed_zone": "park"}, 1.0)
        assert q == pytest.approx(4 / 49)
        m = b.as_matrix()
        assert m[0][0] == m[1][1] == pytest.approx(1 / 4)
        assert m[6][6] == 0.0

    def test_zone_and_direction_intersect(self) -> None:
        b = engine()
        assert b.fuse_hint({"claimed_zone": "docks", "claimed_direction": "E"}, 1.0) is not None
        assert b.as_matrix()[0][5] > 0.0
        b2 = engine()  # park is west, direction says east -> empty intersection -> no-op
        assert b2.fuse_hint({"claimed_zone": "park", "claimed_direction": "E"}, 1.0) is None

    def test_uninformative_claims_are_no_ops(self) -> None:
        b = engine()
        assert b.fuse_hint(None, 1.0) is None
        assert b.fuse_hint({}, 1.0) is None
        assert b.fuse_hint({"claimed_zone": "atlantis"}, 1.0) is None
        assert b.fuse_hint({"claimed_direction": "STAY"}, 1.0) is None
        assert matrix_total(b) == pytest.approx(1.0)

    def test_confidence_scales_the_mixture_weight(self) -> None:
        b = engine()
        q = b.fuse_hint({"claimed_direction": "S", "confidence": 0.0}, 1.0)
        assert q == pytest.approx(21 / 49)  # reported, but weight 0 -> no reshaping
        assert b.most_likely_p() == pytest.approx(1 / 49)

    def test_lie_inversion_turns_words_into_negative_evidence(self) -> None:
        b = engine(lie_inversion=True)
        b.fuse_hint({"claimed_direction": "S"}, 0.0)  # r below lie_inversion_below
        m = b.as_matrix()
        assert all(m[r][c] == 0.0 for r in range(4, 7) for c in range(7))
        assert matrix_total(b) == pytest.approx(1.0)

    def test_bounded_damage_a_lie_cannot_override_scent(self) -> None:
        b, opp = engine(), make_scent_model(pheromones())
        observe_walk(b, opp, [(1, 1)])
        b.fuse_hint({"claimed_direction": "S"}, 0.5)  # words point away from the mass
        assert b.most_likely() == (1, 1)  # mixture floor kept the scent verdict

    def test_footprint_respects_barriers(self) -> None:
        b = engine()
        b.note_barrier((0, 0))
        b.fuse_hint({"claimed_zone": "park"}, 1.0)
        assert b.as_matrix()[0][0] == 0.0
        assert b.as_matrix()[0][1] == pytest.approx(1 / 3)


class TestHintGeometry:
    def test_centroid_prefers_trail_over_belief(self) -> None:
        belief = {(0, 0): 1.0}
        assert trail_centroid({"4,5": 0.8}, belief) == (4.0, 5.0)
        assert trail_centroid({}, belief) == (0.0, 0.0)

    def test_half_plane_is_relative_to_the_trail_centroid(self) -> None:
        trail = {"1,1": 0.8}  # centroid (1, 1)
        cells = hint_footprint({"claimed_direction": "N"}, trail, {}, 7, {})
        assert cells == {(0, c) for c in range(7)}

    def test_empty_claim_yields_empty_footprint(self) -> None:
        assert hint_footprint(None, {}, {(0, 0): 1.0}, 7, {}) == set()


class TestReliabilityLedger:
    def test_prior_value(self) -> None:
        assert ReliabilityLedger(CFG).value() == pytest.approx(0.5)
        skewed = ReliabilityLedger({**CFG, "hint_alpha0": 3.0, "hint_beta0": 1.0})
        assert skewed.value() == pytest.approx(0.75)

    def test_rises_on_consistent_evidence(self) -> None:
        ledger = ReliabilityLedger(CFG)
        assert ledger.update(1.0) > 0.5
        assert ledger.update(1.0) > 0.6

    def test_collapses_on_contradictions(self) -> None:
        ledger = ReliabilityLedger(CFG)
        for _ in range(3):
            value = ledger.update(0.0)
        assert value < 0.2

    def test_injection_penalty_hook(self) -> None:
        ledger = ReliabilityLedger(CFG)
        assert ledger.injection_detected() < 0.2  # beta burned hard, r collapses

    def test_update_range_enforced(self) -> None:
        with pytest.raises(ValueError, match="consistency"):
            ReliabilityLedger(CFG).update(1.5)

    @pytest.mark.parametrize("missing", ["hint_alpha0", "hint_beta0", "reliability_forget"])
    def test_missing_terms_raise(self, missing: str) -> None:
        cfg = {k: v for k, v in CFG.items() if k != missing}
        with pytest.raises(ConfigError, match=missing):
            ReliabilityLedger(cfg)

    @pytest.mark.parametrize(
        ("key", "bad"),
        [("hint_alpha0", 0.0), ("reliability_forget", 0.0), ("injection_penalty", -1.0)],
    )
    def test_invalid_terms_raise(self, key: str, bad: float) -> None:
        with pytest.raises(ConfigError):
            ReliabilityLedger({**CFG, key: bad})

    def test_full_pipeline_cross_check(self) -> None:
        """Brief §5 story: scent-vs-hint contradiction collapses r within turns."""
        b, opp = engine(), make_scent_model(pheromones())
        observe_walk(b, opp, [(1, 1)])
        ledger = ReliabilityLedger(CFG)
        truth = b.fuse_hint({"claimed_direction": "N"}, ledger.value())
        r_up = ledger.update(truth)
        assert truth > 0.95 and r_up > 0.5  # words agree with unfakeable scent
        lie = b.fuse_hint({"claimed_direction": "S"}, ledger.value())
        r_down = ledger.update(lie)
        assert lie < 0.05 and r_down < r_up  # claim south, mass reads north-west


class TestMaskingAndInvariants:
    def test_note_barrier_zeroes_and_persists(self) -> None:
        b, opp = engine(), make_scent_model(pheromones())
        b.note_barrier((2, 2))
        observe_walk(b, opp, [(4, 4)])
        assert b.as_matrix()[2][2] == 0.0
        assert matrix_total(b) == pytest.approx(1.0)

    def test_exclude_zeroes_one_cell(self) -> None:
        b = engine()
        b.exclude((0, 0))
        assert b.as_matrix()[0][0] == 0.0
        assert matrix_total(b) == pytest.approx(1.0)

    def test_exclude_everything_degenerates_to_uniform(self) -> None:
        b = engine()
        for r in range(7):
            for c in range(7):
                b.exclude((r, c))
        assert all_finite(b) and matrix_total(b) == pytest.approx(1.0)

    def test_degenerate_fallback_still_respects_barriers(self) -> None:
        b, opp = engine(), make_scent_model(pheromones())
        b.note_barrier((0, 0))
        observe_walk(b, opp, [(1, 1)])
        b.fuse_hint({"claimed_direction": "S"}, 1.0)  # hard mask kills ALL current mass
        assert all_finite(b) and matrix_total(b) == pytest.approx(1.0)
        assert b.as_matrix()[0][0] == 0.0  # never resurrect a barrier cell

    def test_never_nan_across_an_adversarial_sequence(self) -> None:
        b, opp = engine(), make_scent_model(pheromones())
        observe_walk(b, opp, [(3, 3), (3, 4)])
        b.note_barrier((3, 3))
        b.observe_smell(opp.snapshot())  # duplicate after a mask
        b.fuse_hint({"claimed_direction": "W"}, 1.0)
        b.diffuse(Role.THIEF)
        assert all_finite(b) and matrix_total(b) == pytest.approx(1.0)


class TestEntropy:
    def test_observation_concentrates_entropy_down(self) -> None:
        b, opp = engine(), make_scent_model(pheromones())
        h_uniform = b.entropy()
        observe_walk(b, opp, [(3, 3)])
        h_posterior = b.entropy()
        assert h_posterior < h_uniform
        assert h_posterior < 0.1  # near-delta under the reference dialect

    def test_diffuse_raises_and_observe_re_collapses(self) -> None:
        b, opp = engine(), make_scent_model(pheromones())
        observe_walk(b, opp, [(3, 3)])
        h_sharp = b.entropy()
        opp.deposit((3, 4))
        opp.decay()
        b.diffuse(Role.THIEF)
        h_spread = b.entropy()
        b.observe_smell(opp.snapshot())
        assert h_spread > h_sharp  # predict adds uncertainty
        assert b.entropy() < h_spread  # update concentrates again


class TestEngineConfig:
    @pytest.mark.parametrize(
        "missing",
        ["move_set", "sigma_obs", "zero_scent_weight", "resync_floor", "motion_eta_thief",
         "motion_eta_police", "kernel_mobility_mu", "kernel_mobility_k", "lie_inversion",
         "lie_inversion_below"],
    )
    def test_missing_required_term_raises(self, missing: str) -> None:
        cfg = {k: v for k, v in CFG.items() if k != missing}
        with pytest.raises(ConfigError, match=missing):
            BeliefV2(7, cfg, pheromones())

    def test_non_positive_resync_floor_raises(self) -> None:
        with pytest.raises(ConfigError, match="resync_floor"):
            engine(resync_floor=0.0)

    def test_board_size_mismatch_with_scent_terms_raises(self) -> None:
        with pytest.raises(ConfigError, match="board_size"):
            BeliefV2(9, dict(CFG), pheromones())

    def test_garbage_move_set_raises_no_king_fallback(self) -> None:
        with pytest.raises(ConfigError, match="king"):
            engine(move_set=["N", "K"])
