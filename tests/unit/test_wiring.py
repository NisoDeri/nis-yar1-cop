"""Integration-seam tests for the wiring the INTEGRATOR added.

Covers the four seams that are otherwise only reachable from a live game/CLI:
the live-view ``board_snapshot`` builder, Ollama talk selection in ``resolve``, the
opt-in end-of-series email gate in ``series``, and the ``replay`` / agent-vs-agent CLI
dispatch. All in-process; no sockets, no LLMs, no real email.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pursuit.infra.email as email_mod
import pursuit.interface.cli as cli
import pursuit.strategy.ollama_talk as ollama_talk_mod
from pursuit.constants import Role
from pursuit.interface.cli_replay import replay_command
from pursuit.interface.live_view import board_snapshot
from pursuit.peer.sealing import SealedLog
from pursuit.sdk.series import _maybe_email
from pursuit.shared.config import ConfigManager
from pursuit.strategy.ollama_talk import OllamaTalk
from pursuit.strategy.resolve import resolve_brain
from pursuit.strategy.talk import TemplateTalk


# --- live_view.board_snapshot ----------------------------------------------------------------
class _Board:
    size = 3


class _State:
    board = _Board()
    position = (1, 1)
    barriers = {(0, 0)}
    visited = {(1, 1)}
    step_number = 4


class _MatrixBelief:
    def as_matrix(self):
        return [[0.1, 0.2, 0.3] for _ in range(3)]


class _Runtime:
    state = _State()
    role = Role.POLICE
    belief = _MatrixBelief()


def test_board_snapshot_uses_real_belief_matrix():
    view = board_snapshot(_Runtime(), "my_turn", "hi", "ho")
    assert view["step"] == 4
    assert view["role"] == "police"
    assert view["my_pos"] == (1, 1)
    assert view["barriers"] == [(0, 0)]
    assert view["belief_matrix"] == [[0.1, 0.2, 0.3]] * 3
    assert (view["hint_in"], view["hint_out"], view["status"]) == ("hi", "ho", "my_turn")


def test_board_snapshot_falls_back_to_uniform_without_as_matrix():
    class _Plain:
        state = _State()
        role = Role.THIEF
        belief = object()  # no as_matrix

    view = board_snapshot(_Plain(), "opp_turn")
    assert len(view["belief_matrix"]) == 3
    assert abs(view["belief_matrix"][0][0] - 1 / 9) < 1e-9


# --- resolve: Ollama talk selection ----------------------------------------------------------
def test_resolve_builds_ollama_talk_when_provider_is_ollama():
    cfg = ConfigManager(
        game_terms={"world": {"hint_max_words": 12}},
        private_terms={"trash_talk": {"provider": "ollama", "model": "m",
                                      "ollama_url": "http://x", "deadline_seconds": 3}},
        rate_limits={})
    brain = resolve_brain(cfg, Role.THIEF, random.Random(0))
    assert isinstance(brain.talk, OllamaTalk)
    assert brain.talk.hint_max_words == 12


def test_resolve_falls_back_to_template_when_ollama_construction_fails(monkeypatch):
    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("ollama unavailable")

    monkeypatch.setattr(ollama_talk_mod, "OllamaTalk", _Boom)
    cfg = ConfigManager({}, {"trash_talk": {"provider": "ollama"}}, {})
    brain = resolve_brain(cfg, Role.POLICE, random.Random(0))
    assert isinstance(brain.talk, TemplateTalk)  # never raises into the game


def test_resolve_keeps_template_for_default_provider():
    cfg = ConfigManager({}, {"trash_talk": {"provider": "template"}}, {})
    brain = resolve_brain(cfg, Role.POLICE, random.Random(0))
    assert isinstance(brain.talk, TemplateTalk)


# --- series: opt-in end-of-series email gate -------------------------------------------------
_SUMMARY = {"group_id": "nis-yar1", "game_id": "nis-yar1-vs-opp",
            "totals": {"nis-yar1": 20, "opp": 5}, "sub_games": []}


def test_maybe_email_is_a_noop_when_disabled(monkeypatch):
    def _forbidden(*a, **k):
        raise AssertionError("email must not be constructed when disabled")

    monkeypatch.setattr(email_mod, "GmailSender", _forbidden)
    _maybe_email(ConfigManager({}, {"email": {"enabled": False}}, {}), _SUMMARY)


def test_maybe_email_sends_through_gatekeeper_when_enabled(monkeypatch):
    calls = {}

    class _FakeSender:
        def send_result(self, subject, body_dict, to=None):
            calls["subject"], calls["body"] = subject, body_dict
            return {"sent": True, "reason": "fake"}

    monkeypatch.setattr(email_mod, "GmailSender", _FakeSender)
    cfg = ConfigManager({"rate_limiter_gatekeeper": {}}, {"email": {"enabled": True}}, {})
    _maybe_email(cfg, _SUMMARY)
    assert calls["subject"] == "pursuit result nis-yar1-vs-opp"
    assert calls["body"]["_schema"]  # a real result artifact was built and passed


# --- CLI: replay + agent-vs-agent dispatch ---------------------------------------------------
def test_replay_command_prints_verdict_and_returns_zero(tmp_path, capsys):
    log = SealedLog({"dialect": "reference"})
    log.seal_step({"step": 0, "type": "system_spec", "spec": {}})
    log.seal_step({"step": 1, "state": "grid=4x4;self=[0, 0];barriers=[]",
                   "position": [0, 0], "move": "MOVE:S"})
    doc = {"summary": {"game_id": "g", "result": "capture"}, "records": log.audit_reveal()}
    path = tmp_path / "log.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    rc = replay_command(str(path), no_gui=True)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["passed"] is True
    assert out["n_records"] == 2


def test_cli_lab_routes_to_versus_when_both_b_brains_given(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "run_lab_versus",
                        lambda *a: seen.setdefault("args", a) or {"games": len(a)})
    rc = cli.main(["lab", "--games", "2", "--seed", "1", "--police", "m:P", "--thief", "m:T",
                   "--police-b", "m:PB", "--thief-b", "m:TB"])
    assert rc == 0
    assert seen["args"][2:6] == ("m:P", "m:T", "m:PB", "m:TB")
    assert seen["args"][6] == Path("config") / "police"
