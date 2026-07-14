"""Series driver — N sub-games, role alternation, fresh PeerRuntime each (arch §sdk).

Odd sub-games are played in my CONFIG role, even ones in the opposite role (the
reference's alternation), and every sub-game re-runs the handshake inside its fresh
:class:`PeerRuntime` (INTEROP §4.6). Emission here is the MINIMAL writer: the raw
sealed per-sub-game log (nonces revealed post-audit, replayable) plus one series
summary JSON under ``logs/<group_id>/`` — the full 4-artifact schema-1.1 builders
land in the report stage. ``ScentBelief`` is the stage-2 stand-in belief exposing
exactly the BeliefV2 surface the turn handler and the v1 brains consume.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pursuit.constants import Cell, Role
from pursuit.domain.scoring import ScoreTable
from pursuit.exceptions import ConfigError
from pursuit.peer.runtime import PeerRuntime
from pursuit.sdk.series_log import LieProfiler, log_document, sub_row, write_json


def _cell_of(key: str) -> Cell:
    row_text, _, col_text = key.partition(",")
    return (int(row_text), int(col_text))


class ScentBelief:
    """Wire-driven stand-in belief: the mode is the opponent's strongest scent cell.

    Duck-types the surface both seams need — ``diffuse``/``observe_smell`` (turn
    handler + lab arena) and ``most_likely``/``most_likely_p`` (v1 brains). BeliefV2
    plugs into the exact same calls when the strategy stage wires it.
    """

    def __init__(self, start: Cell) -> None:
        self._mode: Cell = (int(start[0]), int(start[1]))  # opponent's signed start cell
        self._p = 1.0

    def diffuse(self, opponent_role: Any = None, reference: Any = None) -> None:
        """PREDICT is a no-op here: the scent mode is already the freshest evidence."""

    def observe_smell(self, cells: dict[str, float]) -> None:
        """UPDATE: adopt the strongest cell (ties row-major, like ScentModel.strongest)."""
        if cells:
            key = min(cells, key=lambda k: (-float(cells[k]), _cell_of(k)))
            self._mode, self._p = _cell_of(key), min(1.0, float(cells[key]))

    def most_likely(self) -> Cell:
        return self._mode

    def most_likely_p(self) -> float:
        return self._p


def belief_for(config: Any, role: Role, trust_prior: float | None = None) -> Any:
    """BeliefV2 when private belief config is present; else the ScentBelief stand-in.

    ``trust_prior`` (E2 profiler output, default ``None``) seeds the next reliability prior.
    """
    key = "thief_start" if role is Role.POLICE else "cop_start"
    start: Cell = tuple(config.game(f"board_and_agents.{key}"))  # type: ignore[assignment]
    try:
        cfg = config.private("belief")
    except Exception:  # noqa: BLE001
        return ScentBelief(start)
    if not isinstance(cfg, dict) or "sigma_obs" not in cfg:
        return ScentBelief(start)
    from pursuit.domain.belief.engine import BeliefV2  # import here — keeps lab import-free

    board_size = int(config.game("board_and_agents.grid_size"))
    belief_cfg = LieProfiler.belief_cfg(config, cfg, trust_prior)
    scent_cfg = {
        "dialect": config.game("pheromones.dialect"),
        "board_size": board_size,
        "smell_grid_size": int(config.game("pheromones.pheromone_grid_size")),
        "emit_intensity": float(config.game("pheromones.pheromone_center_intensity")),
        "decay_per_step": float(config.game("pheromones.pheromone_decay")),
        "min_center_intensity": float(config.game("pheromones.pheromone_min_center_intensity")),
    }
    return BeliefV2(board_size, belief_cfg, scent_cfg)


def counted_games(config: Any) -> int:
    """The rule-37 ledger count; a fresh ledger (absent key) is 0 (ruling A9b)."""
    try:
        return int(config.private("game.counted_games_so_far"))
    except ConfigError:
        return 0


def _maybe_email(config: Any, summary: dict[str, Any]) -> None:
    """Opt-in (private ``email.enabled``): send the result artifact via the email Gatekeeper."""
    try:
        if not bool(config.private("email.enabled")):
            return
    except ConfigError:
        return
    try:  # a send failure must NEVER crash the series (§email, D8)
        from pursuit.infra.email import GmailSender
        from pursuit.infra.gatekeeper import Gatekeeper
        from pursuit.report.artifacts import build_result_artifact

        my_gid = str(summary.get("group_id", ""))
        opp = next((g for g in summary.get("totals", {}) if g != my_gid), "opponent")
        artifact = build_result_artifact(summary, my_gid, opp)
        Gatekeeper.from_config(config, "email").execute(
            GmailSender().send_result, f"pursuit result {summary.get('game_id', '')}", artifact)
    except Exception:  # noqa: BLE001
        pass


def run_series(config: Any, role: Role, num_games: int, transport: Any, inboxes: Any, *,
               keypair: tuple[bytes, bytes], brain_factory: Any, sysinfo: dict[str, Any],
               github_commit: str, watchdog: Any = None, observer: Any = None,
               logs_dir: str | Path | None = None) -> dict[str, Any]:
    """Play ``num_games`` sub-games; aggregate scores + the tie rule; emit logs + email."""
    my_gid = str(config.private("game.group_id"))
    table = ScoreTable(config.game("scoring"))
    rows: list[dict[str, int]] = []
    subs: list[dict[str, Any]] = []
    game_id = ""
    profiler = LieProfiler(config)  # E2 cross-sub-game lie-profiler (default off, non-fatal)
    for number in range(1, num_games + 1):
        inboxes.turns.drain()  # stale-turn hygiene between sub-games (INTEROP §2.4);
        inboxes.audits.drain()  # safe: fresh turns only follow the new handshake
        role_now = role if number % 2 == 1 else role.opponent  # odd = my config role
        runtime = PeerRuntime(role_now, config, transport, inboxes,
                              brain_factory(role_now), belief_for(config, role_now, profiler.prior),
                              keypair, sysinfo=sysinfo, github_commit=github_commit,
                              counted_games=counted_games(config), watchdog=watchdog,
                              observer=observer)
        outcome = runtime.run()
        game_id = outcome.game_id
        opp_gid = outcome.opponent_group or "opponent"
        rows.append({my_gid: outcome.scores[role_now],
                     opp_gid: outcome.scores[role_now.opponent]})
        subs.append(sub_row(number, role_now, my_gid, opp_gid, outcome))
        profiler.observe(outcome, role_now.opponent)  # seed the next sub-game's r_0 (E2)
        if logs_dir is not None:
            write_json(Path(logs_dir) / my_gid / f"log_{game_id}_g{number:02d}.json",
                       log_document(number, role_now, my_gid, outcome))
    summary = {"game_id": game_id, "group_id": my_gid, "num_sub_games": num_games,
               "sub_games": subs, **table.series_totals(rows)}
    if logs_dir is not None:
        write_json(Path(logs_dir) / my_gid / f"series_{game_id}.json", summary)
    _maybe_email(config, summary)
    return summary
