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
from pursuit.sdk.series_log import (
    LieProfiler,
    emit_artifacts,
    log_document,
    sub_row,
    write_json,
)


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


def logical_subgame_numbers(config: Any, role: Role, count: int, alternate: bool) -> list[int]:
    """Return the sub-game numbers this process should declare.

    Fixed-role two-endpoint play runs only the parity assigned to this group/role:
    first sorted group is cop on odd sub-games, second sorted group is thief on odd sub-games.
    """
    if alternate:
        return list(range(1, count + 1))
    try:
        pair = sorted(str(gid) for gid in config.game("agreed_between"))
        signed_total = int(config.game("network_and_league.num_games"))
        my_gid = str(config.private("game.group_id"))
    except Exception:  # noqa: BLE001 - synthetic tests may omit pairing metadata
        return list(range(1, count + 1))
    if len(pair) != 2 or my_gid not in pair:
        return list(range(1, count + 1))
    first = pair[0] == my_gid
    # Some opponents (e.g. najamjad) use the opposite convention — first-sorted opens as
    # THIEF, not cop. game.parity_invert flips our odd/even role assignment to match theirs,
    # agreed out-of-band; it changes neither the signed terms nor the game_uid.
    try:
        if bool(config.private("game.parity_invert")):
            first = not first
    except Exception:  # noqa: BLE001 — absent flag = default convention
        pass

    def role_for(number: int) -> Role:
        odd = number % 2 == 1
        if first:
            return Role.POLICE if odd else Role.THIEF
        return Role.THIEF if odd else Role.POLICE

    return [number for number in range(1, signed_total + 1) if role_for(number) is role][:count]


def run_series(config: Any, role: Role, num_games: int, transport: Any, inboxes: Any, *,
               keypair: tuple[bytes, bytes], brain_factory: Any, sysinfo: dict[str, Any],
               github_commit: str, watchdog: Any = None, observer: Any = None,
               logs_dir: str | Path | None = None, alternate: bool = True,
               series_gate: Any = None) -> dict[str, Any]:
    """Play ``num_games`` sub-games; aggregate scores + the tie rule; emit logs + email.

    ``alternate`` (default True) is the reference role-swap: odd sub-games in my config role,
    even in the opposite. Set False for the two-endpoint league topology, where each peer
    exposes a FIXED-role MCP endpoint and plays every sub-game in that one role (my config
    role) — its opposite-role sub-games are played by my other endpoint against the peer's
    complementary endpoint. A single sub-game (``num_games == 1``) is my config role either way.
    """
    my_gid = str(config.private("game.group_id"))
    table = ScoreTable(config.game("scoring"))
    rows: list[dict[str, int]] = []
    subs: list[dict[str, Any]] = []
    game_id = ""
    profiler = LieProfiler(config)  # E2 cross-sub-game lie-profiler (default off, non-fatal)
    logs: list[dict[str, Any]] = []  # per-sub-game docs -> the 4-artifact emission
    for number in logical_subgame_numbers(config, role, num_games, alternate):
        if series_gate is not None:
            series_gate.wait(number)
        inboxes.turns.drain()  # stale-turn hygiene between sub-games (INTEROP §2.4);
        role_now = role if (not alternate or number % 2 == 1) else role.opponent  # odd = my
        # config role; a fixed-role endpoint (alternate=False) plays every sub-game in it
        runtime = PeerRuntime(role_now, config, transport, inboxes,
                              brain_factory(role_now), belief_for(config, role_now, profiler.prior),
                              keypair, sysinfo=sysinfo, github_commit=github_commit,
                              counted_games=counted_games(config), watchdog=watchdog,
                              observer=observer, sub_game_number=number)
        outcome = runtime.run()
        if series_gate is not None:
            series_gate.complete(number)
        game_id = outcome.game_id
        opp_gid = outcome.opponent_group or "opponent"
        rows.append({my_gid: outcome.scores[role_now],
                     opp_gid: outcome.scores[role_now.opponent]})
        subs.append(sub_row(number, role_now, my_gid, opp_gid, outcome))
        profiler.observe(outcome, role_now.opponent)  # seed the next sub-game's r_0 (E2)
        doc = log_document(number, role_now, my_gid, outcome)
        logs.append(doc)
        if logs_dir is not None:
            write_json(Path(logs_dir) / my_gid / f"log_{game_id}_g{number:02d}.json", doc)
    summary = {"game_id": game_id, "group_id": my_gid, "num_sub_games": num_games,
               "sub_games": subs, "config_sha256": config.config_sha256(),
               **table.series_totals(rows)}
    if logs_dir is not None:
        write_json(Path(logs_dir) / my_gid / f"series_{game_id}.json", summary)
        emit_artifacts(config, summary, logs, sysinfo, github_commit, keypair,
                       Path(logs_dir) / my_gid)
    return summary
