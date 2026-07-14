"""pursuit CLI — a thin argparse shell over the SDK (Table-5 gate: rule 3).

Config-only addressing (PRD-5): there are NO port/URL flags — peers are wired
entirely from ``config/<role>/game.toml`` + the signed ``game.json``. The ONLY
top-level game-logic import is :mod:`pursuit.sdk`; a unit test enforces it (GUI and
replay helpers are imported lazily inside the branches that use them).

Subcommands::

    peer  --role {police,thief} [--config-dir P] [--fake-opponent] [--gui]
    lab   --games N --seed S --police M:C --thief M:C
          [--police-b M:C --thief-b M:C]      # both -> agent-vs-agent series
    replay <logfile> [--no-gui]               # headless verify (+ optional viewer)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pursuit.exceptions import PursuitError
from pursuit.sdk import run_lab, run_lab_versus, run_peer

ROLES = ("police", "thief")


def build_parser() -> argparse.ArgumentParser:
    """The full argument grammar; anything outside it is refused by argparse."""
    parser = argparse.ArgumentParser(
        prog="pursuit", description="P2P Cops & Robbers peer — group nis-yar1")
    commands = parser.add_subparsers(dest="command", required=True)
    peer = commands.add_parser("peer", help="run one peer for a full series")
    peer.add_argument("--role", required=True, choices=ROLES,
                      help="which side this OS process plays")
    peer.add_argument("--config-dir", default=None,
                      help="config directory (default: config/<role>)")
    peer.add_argument("--fake-opponent", action="store_true",
                      help="self-contained demo: in-process greedy opponent, no network")
    peer.add_argument("--gui", action="store_true",
                      help="live window with the belief heatmap (self-contained demo)")
    lab = commands.add_parser("lab", help="paired-seed self-play / agent-vs-agent lab (D7)")
    lab.add_argument("--games", type=int, required=True, help="number of paired seeds")
    lab.add_argument("--seed", type=int, required=True, help="base seed")
    lab.add_argument("--police", required=True, help="police brain 'module:Class'")
    lab.add_argument("--thief", required=True, help="thief brain 'module:Class'")
    lab.add_argument("--police-b", default=None, help="agent-B police brain 'module:Class'")
    lab.add_argument("--thief-b", default=None, help="agent-B thief brain 'module:Class'")
    lab.add_argument("--config-dir", default=None,
                     help="signed-terms source (default: config/police)")
    replay = commands.add_parser("replay", help="headless verify a sealed series log")
    replay.add_argument("logfile", help="path to a {summary, records} series log")
    replay.add_argument("--no-gui", action="store_true", help="verdict only, never open Tk")
    return parser


def _config_dir(explicit: str | None, fallback_role: str) -> Path:
    """Config-only addressing: an explicit dir wins, else the repo-layout default."""
    return Path(explicit) if explicit else Path("config") / fallback_role


def _run_peer(args: argparse.Namespace) -> dict:
    """Dispatch ``peer``: a live GUI demo when ``--gui``, else the series (real/fake)."""
    config_dir = _config_dir(args.config_dir, args.role)
    if args.gui:
        from pursuit.interface.live_view import run_live  # lazy: Tk, GUI-only

        return run_live(config_dir, args.role)
    return run_peer(config_dir, args.role, fake_opponent=args.fake_opponent)


def _run_lab(args: argparse.Namespace) -> dict:
    """Dispatch ``lab``: agent-vs-agent when BOTH -b brains are given, else self-play."""
    config_dir = _config_dir(args.config_dir, "police")
    if args.police_b and args.thief_b:
        return run_lab_versus(args.games, args.seed, args.police, args.thief,
                              args.police_b, args.thief_b, config_dir)
    return run_lab(args.games, args.seed, args.police, args.thief, config_dir)


def main(argv: list[str] | None = None) -> int:
    """Parse, dispatch through the SDK, print the JSON summary; 0 on success."""
    args = build_parser().parse_args(argv)
    if args.command == "replay":
        from pursuit.interface.cli_replay import replay_command  # lazy: interface, not SDK

        return replay_command(args.logfile, args.no_gui)
    try:
        summary = _run_peer(args) if args.command == "peer" else _run_lab(args)
    except PursuitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0
