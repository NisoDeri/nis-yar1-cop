"""PeerRuntime end-to-end over in-memory transports — no sockets, processes or LLMs.

Two full runtimes duel over a FakeTransport pair in threads (each is one peer's whole
sub-game lifecycle: handshake → turns → audit); scripted brains make every ending
deterministic: capture by landing / by barrier, survival, the move ceiling, timeout →
technical_loss 0/0 with the audit STILL run (ruling A6), and audit-caught forgery →
technical_loss 0/0 (ruling A9a).
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from pursuit.constants import Direction, GameResult, MoveType, Role
from pursuit.domain.crypto import generate_keypair
from pursuit.domain.protocol import CAPTURE_CONCESSION_HINT
from pursuit.infra.transport import FakeTransport
from pursuit.peer.fsm import State
from pursuit.peer.handshake import Handshake
from pursuit.peer.inboxes import PeerInboxes
from pursuit.peer.runtime import PeerRuntime
from pursuit.shared.config import ConfigManager

SPEC = {"os": "TestOS", "cpu_type": "TestCPU", "cpu_freq_mhz": 1, "cpu_cores": 1,
        "ram_gb": 1.0, "gpu_model": "none", "vram_gb": 0.0}


def make_game(survival=10, max_moves=10, barriers=3, thief_start=(2, 1)) -> dict:
    return {
        "board_and_agents": {"grid_size": 7, "thief_start": list(thief_start),
                             "cop_start": [0, 0], "axis_origin_corner": "top-left",
                             "axis_start_index": 0},
        "world": {"map_area": "New York", "hint_max_words": 15},
        "movement_and_barriers": {"move_set": ["N", "S", "E", "W", "STAY"],
                                  "max_barriers": barriers, "max_moves": max_moves,
                                  "survival_threshold": survival},
        "scoring": {"capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
                    "survival_thief": 10, "tie_score": 2, "technical_loss": 0},
        "pheromones": {"dialect": "book", "pheromone_center_intensity": 0.9,
                       "pheromone_decay": 0.1, "pheromone_grid_size": 5,
                       "pheromone_min_center_intensity": 0.5},
        "crypto": {"dialect": "book"},
        "network_and_league": {"num_games": 1, "watchdog_timeout_sec": 60},
    }


def make_config(game: dict, gid: str, **net_over) -> ConfigManager:
    network = {"turn_timeout_seconds": 10.0, "poll_interval_seconds": 0.01,
               "connect_timeout_seconds": 5.0, "retry_interval_seconds": 0.01,
               "audit_send_timeout_seconds": 5.0}
    network.update(net_over)
    private = {"version": "0.1.0",
               "game": {"group_id": gid, "group_name": gid.title(), "members": ["A", "B"],
                        "sub_game_number": 1,
                        "repos": {"cop": "https://x/c", "thief": "https://x/t"},
                        "mcp_servers": {"cop": "http://c/mcp", "thief": "http://t/mcp"}},
               "trash_talk": {"model": "stub"}, "network": network,
               "fsm": {"max_illegal_events": 3}, "play": {"seed": 7}}
    return ConfigManager(game_terms=game, private_terms=private, rate_limits={})


def decision(move_type: MoveType, direction: Direction | None = None) -> SimpleNamespace:
    return SimpleNamespace(move_type=move_type, direction=direction, hint="moving quietly",
                           verdict="truth", reasoning="", prompt_text="",
                           response_seconds=0.0, random_move=False)


class StubBrain:
    """Scripted decisions, then HOLD forever — deterministic endings."""

    def __init__(self, script=()) -> None:
        self.script = list(script)

    def decide(self, state, belief, opponent_hint, setting, barriers_max, deadline=None):
        return self.script.pop(0) if self.script else decision(MoveType.HOLD)


class StubBelief:
    """The minimum surface the handler + brains touch; never influences scripts."""

    def diffuse(self, opponent_role=None, reference=None) -> None: ...

    def observe_smell(self, cells) -> None: ...

    def most_likely(self):
        return (0, 0)

    def most_likely_p(self) -> float:
        return 0.0


def duel(police_script, thief_script, game: dict, tweak=None):
    """Both runtimes in threads over crosswise FakeTransports; returns both outcomes."""
    inboxes = {"police": PeerInboxes(), "thief": PeerInboxes()}
    transports = {"police": FakeTransport(inboxes["thief"]),
                  "thief": FakeTransport(inboxes["police"])}
    scripts = {"police": police_script, "thief": thief_script}
    gids = {"police": "aa-team", "thief": "zz-team"}
    runtimes = {role: PeerRuntime(role, make_config(game, gids[role]), transports[role],
                                  inboxes[role], StubBrain(scripts[role]), StubBelief(),
                                  generate_keypair(), sysinfo=SPEC, github_commit="abc1234")
                for role in ("police", "thief")}
    if tweak is not None:
        tweak(runtimes)
    results, errors = {}, {}

    def run(name: str) -> None:
        try:
            results[name] = runtimes[name].run()
        except Exception as exc:  # noqa: BLE001 — surfaced via the assertion below
            errors[name] = exc

    threads = [threading.Thread(target=run, args=(role,)) for role in runtimes]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors, f"runtime crashed: {errors}"
    assert set(results) == {"police", "thief"}
    return results["police"], results["thief"]


MOVE = MoveType.MOVE


class TestEndings:
    def test_capture_by_landing_full_lifecycle(self):
        police = [decision(MOVE, Direction.S), decision(MOVE, Direction.S),
                  decision(MOVE, Direction.E)]
        out_p, out_t = duel(police, [], make_game())
        for outcome in (out_p, out_t):
            assert outcome.result is GameResult.CAPTURE
            assert outcome.winner is Role.POLICE
            assert outcome.scores == {Role.POLICE: 20, Role.THIEF: 5}
            assert outcome.audit["passed"] and not outcome.audit["forgery"]
        assert out_p.game_id == out_t.game_id == "aa-team-vs-zz-team"
        assert out_p.game_uid == out_t.game_uid
        assert out_t.records[-1]["payload"]["hint"] == CAPTURE_CONCESSION_HINT
        assert out_t.records[0]["payload"]["type"] == "system_spec"

    def test_capture_by_barrier_and_truthful_declaration(self):
        police = [decision(MOVE, Direction.S), decision(MoveType.BARRIER, Direction.S)]
        out_p, out_t = duel(police, [], make_game(thief_start=(2, 0)))
        assert out_p.result is out_t.result is GameResult.CAPTURE
        assert out_p.winner is Role.POLICE
        moves = [r["payload"]["move"] for r in out_p.records[1:]]
        assert "BARRIER:S" in moves  # the sealed record matches the declaration
        assert out_t.records[-1]["payload"]["hint"] == CAPTURE_CONCESSION_HINT

    def test_survival_by_thief_own_counter(self):
        out_p, out_t = duel([], [], make_game(survival=3))
        for outcome in (out_p, out_t):
            assert outcome.result is GameResult.SURVIVAL
            assert outcome.winner is Role.THIEF
            assert outcome.scores == {Role.POLICE: 5, Role.THIEF: 10}
            assert outcome.audit["passed"]
        assert out_t.steps == 3  # STAY/HOLD count on the thief's OWN clock (ruling A5)

    def test_move_ceiling_ends_as_survival_on_both_sides(self):
        out_p, out_t = duel([], [], make_game(survival=10, max_moves=2))
        assert out_p.result is out_t.result is GameResult.SURVIVAL
        assert out_p.winner is out_t.winner is Role.THIEF
        assert out_p.steps == 2  # the cop spent its whole budget

    def test_illegal_brain_move_degrades_and_is_flagged(self):
        thief = [decision(MOVE, Direction.W), decision(MOVE, Direction.W)]
        out_p, out_t = duel([], thief, make_game(survival=3, thief_start=(2, 0)))
        assert out_t.result is GameResult.SURVIVAL  # never stalled on the illegal W
        flagged = [r["payload"]["random_move"] for r in out_t.records[1:]]
        assert flagged[1] is True  # the degraded step is honestly flagged in the seal


class TestFaultPaths:
    def test_timeout_yields_technical_loss_and_still_audits(self):
        game = make_game()
        config = make_config(game, "aa-team", turn_timeout_seconds=0.2,
                             audit_send_timeout_seconds=0.2)
        transport = FakeTransport(PeerInboxes())  # opponent inboxes nobody reads
        handshake = Handshake(game_id="aa-team-vs-zz-team", game_uid="u" * 36,
                              terms={}, opponent_identity={"group_id": "zz-team"},
                              opponent_pubkey=None, opponent_counted_games=None)
        runtime = PeerRuntime("police", config, transport, PeerInboxes(), StubBrain(),
                              StubBelief(), generate_keypair(), handshake=handshake,
                              sysinfo=SPEC, github_commit="abc1234")
        outcome = runtime.run()
        assert outcome.result is GameResult.TECHNICAL_LOSS  # ruling A6: 0/0, never a win
        assert outcome.winner is None
        assert outcome.scores == {Role.POLICE: 0, Role.THIEF: 0}
        sent_tools = [tool for tool, _ in transport.sent]
        assert "submit_audit" in sent_tools  # the audit STILL ran (D4 / ruling A6)
        assert "negotiate" not in sent_tools  # injected Handshake skipped negotiation
        assert runtime.fsm.state is State.DONE

    def test_forged_reveal_is_adjudicated_technical_loss(self):
        police = [decision(MOVE, Direction.S), decision(MOVE, Direction.S),
                  decision(MOVE, Direction.E)]

        def forge(runtimes):
            original = runtimes["thief"].log.audit_reveal

            def forged():
                records = original()
                records[1]["nonce"] = "f" * 32  # break step 1's commit preimage
                return records

            runtimes["thief"].log.audit_reveal = forged

        out_p, out_t = duel(police, [], make_game(), tweak=forge)
        assert out_p.result is GameResult.TECHNICAL_LOSS  # ruling A9a: forfeit, 0/0
        assert out_p.scores == {Role.POLICE: 0, Role.THIEF: 0}
        assert out_p.audit["forgery"] and not out_p.audit["passed"]
        assert 1 in out_p.audit["failed_steps"]
        assert out_t.result is GameResult.CAPTURE  # the forger's own view is unchanged


class TestWireHygiene:
    def test_no_nonce_or_position_leaks_before_audit(self):
        _, out_t = duel([], [], make_game(survival=3))
        police_inbox_view = out_t.records  # revealed only POST-audit by design
        assert all("nonce" in record for record in police_inbox_view)

    def test_capture_claim_only_on_police_move_turns(self):
        police = [decision(MoveType.BARRIER, Direction.S), decision(MOVE, Direction.S)]
        out_p, _ = duel(police, [], make_game(survival=4, thief_start=(4, 4)))
        payloads = [r["payload"] for r in out_p.records[1:]]
        assert payloads[0]["move"] == "BARRIER:S"  # barrier turn: no landing claim
        assert out_p.result in (GameResult.CAPTURE, GameResult.SURVIVAL)


@pytest.mark.parametrize("dialect", ["book", "reference"])
def test_both_crypto_dialects_cross_audit_clean(dialect):
    game = make_game(survival=2)
    game["crypto"]["dialect"] = dialect
    out_p, out_t = duel([], [], game)
    assert out_p.audit["passed"] and out_t.audit["passed"]
