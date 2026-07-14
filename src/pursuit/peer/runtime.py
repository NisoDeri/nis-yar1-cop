"""PeerRuntime — one sub-game: handshake → thief-first turn loop → audit-on-every-ending
(A6/D4); an optional ``observer`` gets a per-tick board snapshot for the live GUI."""

from __future__ import annotations

import queue
import time
from typing import Any

from pursuit.constants import GameResult, Role
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.domain.scent import make_scent_model
from pursuit.domain.scoring import ScoreTable
from pursuit.peer.audit import SubgameOutcome, exchange_audits
from pursuit.peer.deadlines import DeadlineTracker
from pursuit.peer.fsm import GameStateMachine, State
from pursuit.peer.handshake import Handshake, run_handshake
from pursuit.peer.sealing import SealedLog
from pursuit.peer.turn_handler import TURN, TurnHandler
from pursuit.peer.turn_sender import TurnSender


class AgreementsView:
    def __init__(self, inboxes: Any) -> None:  # handshake 'agreements' seam over negotiation
        self.agreements, self._inbox = self, inboxes.negotiation

    def get_nowait(self) -> Any:
        item = self._inbox.get_nowait()
        if item is None:
            raise queue.Empty
        return item


def _scent_cfg(game: Any) -> dict[str, Any]:
    """Adapt the signed pheromones block to the ScentParams vocabulary."""
    paths = {"dialect": "pheromones.dialect", "board_size": "board_and_agents.grid_size",
             "smell_grid_size": "pheromones.pheromone_grid_size",
             "emit_intensity": "pheromones.pheromone_center_intensity",
             "decay_per_step": "pheromones.pheromone_decay",
             "min_center_intensity": "pheromones.pheromone_min_center_intensity"}
    return {key: game(path) for key, path in paths.items()}


class PeerRuntime:
    """One sub-game to a :class:`SubgameOutcome`; every wait has a named deadline."""

    def __init__(self, role: Role | str, config: Any, transport: Any, inboxes: Any,
                 brain: Any, belief: Any, keypair: tuple[bytes, bytes], *,
                 handshake: Handshake | None = None, sysinfo: dict[str, Any] | None = None,
                 github_commit: str = "unknown", counted_games: int = 0,
                 watchdog: Any = None, clock: Any = time.monotonic, observer: Any = None) -> None:
        self.role, self.opponent = Role(role), Role(role).opponent
        self.config, self.transport, self.inboxes = config, transport, inboxes
        self.brain, self.belief, self.keypair = brain, belief, keypair
        self.handshake, self.watchdog, self.observer = handshake, watchdog, observer
        self._step0_args = (dict(sysinfo or {}), github_commit, int(counted_games))
        game, movement = config.game, "movement_and_barriers"
        board = Board(game("board_and_agents.grid_size"), game(f"{movement}.move_set"))
        start = "cop_start" if self.role is Role.POLICE else "thief_start"
        self.state = OwnGameState(board, tuple(game(f"board_and_agents.{start}")))
        self.scent_mine = make_scent_model(_scent_cfg(game))
        self.scent_reader = make_scent_model(_scent_cfg(game))  # mirror of THEIR trail
        self.log, self.table = SealedLog(game("crypto")), ScoreTable(game("scoring"))
        self.fsm, self.deadlines = GameStateMachine(), DeadlineTracker(clock)
        self.max_moves = int(game(f"{movement}.max_moves"))
        self.handler = TurnHandler(
            self.role, survival_threshold=game(f"{movement}.survival_threshold"),
            barriers_max=game(f"{movement}.max_barriers"),
            max_breaches=config.private("fsm.max_illegal_events"))
        self.sender = TurnSender(
            self.role, barriers_max=game(f"{movement}.max_barriers"),
            survival_threshold=game(f"{movement}.survival_threshold"),
            hint_max_words=game("world.hint_max_words"), setting=game("world.map_area"))
        self.turn_timeout = float(config.private("network.turn_timeout_seconds"))
        self.audit_timeout = float(config.private("network.audit_send_timeout_seconds"))

    def _notify(self, status: str, hint_in: str = "", hint_out: str = "") -> None:
        """Push a board snapshot to the optional live observer; a viewer never breaks the game."""
        if self.observer is None:
            return
        try:
            from pursuit.interface.live_view import board_snapshot  # lazy: GUI-only, no Tk
            self.observer(board_snapshot(self, status, hint_in, hint_out))
        except Exception:  # noqa: BLE001 — a viewer must never break the game
            pass

    def run(self) -> SubgameOutcome:
        """Handshake → step-0 seal → thief-first turn loop → mutual audit → outcome."""
        self.fsm.advance(State.NEGOTIATING)
        if self.handshake is None:  # the series may inject the pre-agreed handshake
            self.handshake = run_handshake(self.transport, AgreementsView(self.inboxes),
                                           self.config, self.keypair)
        self.log.step0_record(self.config, *self._step0_args, self.keypair)
        self.fsm.advance(State.MY_TURN if self.role is Role.THIEF else State.OPP_TURN)
        try:
            result, winner = self._turn_loop()
        except Exception:  # noqa: BLE001 — ANY mid-game crash (timeout/transport/brain/
            result, winner = GameResult.TECHNICAL_LOSS, None  # belief) is a 0/0 loss; the
            # mandatory audit below STILL runs (A6) — a raise must never skip settlement.
        if self.fsm.state is not State.GAME_OVER:
            self.fsm.advance(State.GAME_OVER)
        self.fsm.advance(State.AUDITING)  # the audit runs on EVERY ending (D4/A6)
        audit = exchange_audits(self.role, result, self.log, self.transport,
                                self.inboxes.audits, self.deadlines, self.audit_timeout,
                                self.handshake.opponent_pubkey, self.handler.commits)
        if audit["forgery"]:
            result, winner = GameResult.TECHNICAL_LOSS, None  # provable forgery (A9a)
        self.fsm.advance(State.DONE)
        return SubgameOutcome(
            result=result, winner=winner, scores=self.table.score_subgame(result, winner),
            audit=audit, records=self.log.audit_reveal(), steps=self.state.step_number,
            game_id=self.handshake.game_id, game_uid=self.handshake.game_uid,
            opponent_group=str(self.handshake.opponent_identity.get("group_id", "")))

    def _turn_loop(self) -> tuple[GameResult, Role | None]:
        response: dict[str, Any] | None = None  # claim_response due on MY next message
        while True:
            if self.watchdog is not None:
                self.watchdog.kick("turn-loop")  # rule-7 heartbeat
            if self.fsm.state is State.MY_TURN:
                sent = self.sender.take_turn(
                    self.brain, self.state, self.belief, self.scent_mine, self.log,
                    self.transport, self.fsm, self.handler.last_hint, claim_response=response)
                response = None
                self._notify("my_turn", self.handler.last_hint, sent.message.hint)
                if sent.terminal:  # my concession (rule 21) or my survival claim (A5)
                    cr = sent.message.claim_response
                    return ((GameResult.CAPTURE, Role.POLICE) if cr and cr.get("caught")
                            else (GameResult.SURVIVAL, Role.THIEF))
                if self.role is Role.POLICE and sent.step >= self.max_moves:
                    return (GameResult.SURVIVAL, Role.THIEF)  # MY move ceiling is spent
                continue
            self.deadlines.arm("opponent-turn", self.turn_timeout)
            raw = self.inboxes.turns.get(timeout=self.deadlines.check("opponent-turn"))
            self.deadlines.disarm("opponent-turn")
            processed = self.handler.process(raw, self.state, self.belief,
                                             self.scent_reader, self.fsm)
            self._notify("opp_turn", processed.hint)
            if processed.kind != TURN:  # duplicate or rule-5 breach: reject-and-drop
                if processed.game_over:  # max_breaches consecutive rejects (D4)
                    return (GameResult.TECHNICAL_LOSS, None)
                continue
            response = processed.claim_response_due
            if processed.game_over:  # their concession answer or validated win_claim
                return ((GameResult.CAPTURE, Role.POLICE) if processed.opponent_caught
                        else (GameResult.SURVIVAL, Role.THIEF))
            if (processed.captured is None and self.opponent is Role.POLICE
                    and processed.step >= self.max_moves):
                return (GameResult.SURVIVAL, Role.THIEF)  # THEIR move ceiling is spent
