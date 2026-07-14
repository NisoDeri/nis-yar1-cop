"""CLI shell tests — grammar, config-only addressing, and the Table-5 import gate.

The dispatch tests monkeypatch the SDK entries, so no game ever runs here; the
import-gate test parses the CLI source with ``ast`` to prove the ONLY top-level
``pursuit.*`` game-logic import is :mod:`pursuit.sdk` (rule 3 / PRD-5).
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

import pursuit.interface.cli as cli
from pursuit.exceptions import ConfigError

#: Non-game-logic helpers the shell may import besides the SDK.
ALLOWED_PURSUIT_IMPORTS = {"pursuit.sdk", "pursuit.exceptions"}


class TestGrammar:
    def test_peer_parses_role_config_dir_and_fake_opponent(self):
        args = cli.build_parser().parse_args(
            ["peer", "--role", "police", "--config-dir", "cfg", "--fake-opponent"])
        assert (args.command, args.role) == ("peer", "police")
        assert args.config_dir == "cfg"
        assert args.fake_opponent is True

    def test_peer_defaults(self):
        args = cli.build_parser().parse_args(["peer", "--role", "thief"])
        assert args.config_dir is None
        assert args.fake_opponent is False

    def test_lab_parses_all_four_required_flags(self):
        args = cli.build_parser().parse_args(
            ["lab", "--games", "3", "--seed", "7", "--police", "m:P", "--thief", "m:T"])
        assert (args.games, args.seed) == (3, 7)
        assert (args.police, args.thief) == ("m:P", "m:T")

    @pytest.mark.parametrize("argv", [
        ["peer", "--role", "police", "--port", "8080"],  # NO port flags (PRD-5)
        ["peer", "--role", "police", "--url", "http://x"],  # NO url flags (PRD-5)
        ["peer", "--role", "referee"],  # only the two league roles exist
        ["peer"],  # role is mandatory
        ["lab", "--games", "3"],  # lab needs all four flags
        [],  # a subcommand is mandatory
    ])
    def test_unknown_or_incomplete_grammar_is_refused(self, argv):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(argv)


class TestTable5Gate:
    def test_only_sdk_game_logic_at_module_top_level(self):
        tree = ast.parse(Path(inspect.getfile(cli)).read_text(encoding="utf-8"))
        pursuit_imports = set()
        for node in tree.body:  # TOP-LEVEL statements only
            if isinstance(node, ast.ImportFrom) and node.module.startswith("pursuit"):
                pursuit_imports.add(node.module)
            if isinstance(node, ast.Import):
                pursuit_imports.update(alias.name for alias in node.names
                                       if alias.name.startswith("pursuit"))
        assert pursuit_imports <= ALLOWED_PURSUIT_IMPORTS  # rule 3: everything via the SDK


class TestDispatch:
    def test_peer_routes_through_run_peer_with_default_config_dir(self, monkeypatch, capsys):
        calls = {}

        def fake_run_peer(config_dir, role, **kwargs):
            calls.update(config_dir=config_dir, role=role, **kwargs)
            return {"game_id": "a-vs-b", "totals": {"a": 5}}

        monkeypatch.setattr(cli, "run_peer", fake_run_peer)
        assert cli.main(["peer", "--role", "thief"]) == 0
        assert calls["config_dir"] == Path("config") / "thief"  # config-only addressing
        assert calls["role"] == "thief"
        assert calls["fake_opponent"] is False
        assert json.loads(capsys.readouterr().out)["game_id"] == "a-vs-b"

    def test_fake_opponent_flag_passes_through(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(cli, "run_peer",
                            lambda config_dir, role, **kw: seen.update(kw) or {})
        assert cli.main(["peer", "--role", "police", "--config-dir", "c",
                         "--fake-opponent"]) == 0
        assert seen["fake_opponent"] is True

    def test_lab_routes_through_run_lab(self, monkeypatch, capsys):
        calls = {}

        def fake_run_lab(games, seed, police, thief, config_dir):
            calls.update(games=games, seed=seed, police=police, thief=thief,
                         config_dir=config_dir)
            return {"games": 4}

        monkeypatch.setattr(cli, "run_lab", fake_run_lab)
        assert cli.main(["lab", "--games", "2", "--seed", "9",
                         "--police", "m:P", "--thief", "m:T"]) == 0
        assert calls == {"games": 2, "seed": 9, "police": "m:P", "thief": "m:T",
                         "config_dir": Path("config") / "police"}
        assert json.loads(capsys.readouterr().out) == {"games": 4}

    def test_domain_errors_exit_nonzero_with_a_message(self, monkeypatch, capsys):
        def boom(*args, **kwargs):
            raise ConfigError("missing agreed term 'x' in game.json")

        monkeypatch.setattr(cli, "run_peer", boom)
        assert cli.main(["peer", "--role", "police"]) == 1
        assert "missing agreed term" in capsys.readouterr().err


def test_python_dash_m_entry_is_importable_and_guarded():
    import pursuit.__main__ as entry  # the __main__ guard must not fire on import

    assert entry.main is cli.main
