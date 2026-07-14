"""SimulationSdk — the SINGLE Orchestrator entry point (arch rule 3 / Table-5 gate).

Every way to play a game flows through :func:`run_peer`: config load +
``validate_agreement`` fail-fast BEFORE any socket, transport/server construction
from config only (PRD-5: no addressing via flags), the rule-7 watchdog, then the
role-alternating series (:mod:`pursuit.sdk.series`). ``fake_opponent=True`` wires a
fully in-process demo — FakeTransport pair + greedy reference-baseline opponent in a
daemon thread — with zero sockets/processes/LLMs (CI-safe). Injection seams
(transport/inboxes/keypair/rng/sysinfo/github_commit/logs_dir) exist for tests and
the fake mode; production callers pass none of them.
"""

from __future__ import annotations

import logging
import random
import threading
from pathlib import Path
from typing import Any

from pursuit.constants import Role
from pursuit.domain.crypto import generate_keypair
from pursuit.exceptions import ConfigError
from pursuit.peer.inboxes import PeerInboxes
from pursuit.peer.watchdog import Watchdog
from pursuit.sdk.series import run_series
from pursuit.shared.config import ConfigManager
from pursuit.shared.sysinfo import collect, get_git_commit
from pursuit.strategy.greedy import GreedyPoliceBrain, GreedyThiefBrain
from pursuit.strategy.resolve import resolve_brain
from pursuit.strategy.talk import TemplateTalk

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
#: INTEROP §1 pins the control-channel deadline; private config may override it.
_CONTROL_TIMEOUT_FALLBACK = 2.0


def _optional(reader: Any, path: str, default: Any = None) -> Any:
    try:
        return reader(path)
    except ConfigError:
        return default


def _timeouts(config: ConfigManager) -> dict[str, float]:
    """OpponentTransport timeout block, straight from the private network config."""
    private = config.private
    return {"retry_interval": float(private("network.retry_interval_seconds")),
            "connect_timeout": float(private("network.connect_timeout_seconds")),
            "audit_timeout": float(private("network.audit_send_timeout_seconds")),
            "control_timeout": float(_optional(private, "network.control_timeout_seconds",
                                               _CONTROL_TIMEOUT_FALLBACK))}


def _real_transport(config: ConfigManager, role: Role, inboxes: PeerInboxes) -> Any:
    """League/localhost wiring: own FastMCP server up, retrying client toward theirs."""
    from pursuit.infra.mcp_server import PeerMcpServer  # sockets — imported only here
    from pursuit.infra.transport import OpponentTransport

    host = str(_optional(config.private, "network.host", "127.0.0.1"))
    PeerMcpServer(role.value, host, int(config.private("network.my_port")), inboxes).start()
    return OpponentTransport(str(config.private("network.opponent_url")), _timeouts(config))


class _FakeIdentity:
    """Config view giving the in-process opponent its own group identity.

    Terms stay byte-identical (the handshake demands it); only the PRIVATE group
    id/name differ, so score rows and role maps never collapse onto one key.
    """

    def __init__(self, config: ConfigManager) -> None:
        self._config = config
        self.game, self.config_sha256 = config.game, config.config_sha256

    def private(self, path: str) -> Any:
        value = self._config.private(path)
        if path in ("game.group_id", "game.group_name"):
            return f"{value}-fake"
        return value


def _fake_opponent(config: ConfigManager, my_role: Role, my_inboxes: PeerInboxes,
                   games: int, sysinfo: dict, commit: str) -> tuple[Any, threading.Thread]:
    """In-process greedy opponent over a FakeTransport pair (the ``--fake-opponent`` demo)."""
    from pursuit.infra.transport import FakeTransport

    opp_inboxes = PeerInboxes()
    mine, theirs = FakeTransport(opp_inboxes), FakeTransport(my_inboxes)
    rng = random.Random(f"{config.private('play.seed')}:fake-opponent")
    talk = TemplateTalk(rng, str(config.game("world.map_area")),
                        int(config.game("world.hint_max_words")))

    def brain_factory(role: Role) -> Any:
        cls = GreedyPoliceBrain if role is Role.POLICE else GreedyThiefBrain
        return cls(talk, rng)

    def play() -> None:
        run_series(_FakeIdentity(config), my_role.opponent, games, theirs, opp_inboxes,
                   keypair=generate_keypair(), brain_factory=brain_factory,
                   sysinfo=sysinfo, github_commit=commit, logs_dir=None)

    return mine, threading.Thread(target=play, name="fake-opponent", daemon=True)


def run_peer(config_dir: str | Path, role: Role | str, num_games: int | None = None, *,
             fake_opponent: bool = False, transport: Any = None, inboxes: Any = None,
             keypair: tuple[bytes, bytes] | None = None, rng: random.Random | None = None,
             logs_dir: str | Path | None = None, sysinfo: dict[str, Any] | None = None,
             github_commit: str | None = None, observer: Any = None) -> dict[str, Any]:
    """Load + validate config, build the stack ONCE, run the series, return its summary."""
    config = ConfigManager.load(config_dir)
    config.validate_agreement()  # fail-fast on any missing agreed term (brief §10)
    my_role = Role(role)
    games = int(num_games if num_games is not None
                else config.game("network_and_league.num_games"))
    rng = rng if rng is not None else random.Random(int(config.private("play.seed")))
    keypair = keypair if keypair is not None else generate_keypair()
    inboxes = inboxes if inboxes is not None else PeerInboxes()
    sysinfo = sysinfo if sysinfo is not None else collect()
    commit = github_commit if github_commit is not None else get_git_commit(_REPO_ROOT)
    opponent_thread = None
    if fake_opponent:
        transport, opponent_thread = _fake_opponent(config, my_role, inboxes, games,
                                                    sysinfo, commit)
        opponent_thread.start()
    elif transport is None:
        transport = _real_transport(config, my_role, inboxes)
    watchdog = Watchdog(float(config.game("network_and_league.watchdog_timeout_sec")),
                        lambda name: logger.warning("watchdog: '%s' heartbeat frozen", name))
    watchdog.start()
    try:
        summary = run_series(
            config, my_role, games, transport, inboxes, keypair=keypair,
            brain_factory=lambda r: resolve_brain(config, r, rng), sysinfo=sysinfo,
            github_commit=commit, watchdog=watchdog, observer=observer,
            logs_dir=logs_dir if logs_dir is not None
            else _optional(config.private, "paths.logs_dir", "logs"))
    finally:
        watchdog.stop()
    if opponent_thread is not None:
        opponent_thread.join(timeout=float(config.private("network.turn_timeout_seconds")))
    return summary
