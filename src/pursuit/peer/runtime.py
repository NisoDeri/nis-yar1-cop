"""PeerRuntime — one sub-game: handshake → thief-first turn loop → audit-on-every-ending
(A6/D4); an optional ``observer`` gets a per-tick board snapshot for the live GUI."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from hashlib import sha256
import json
import queue
import re
import time
from typing import Any

from pursuit.constants import Direction, GameResult, Role
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.domain.scent import make_scent_model
from pursuit.domain.scoring import ScoreTable
from pursuit.peer.audit import SubgameOutcome, exchange_audits
from pursuit.peer.deadlines import DeadlineTracker
from pursuit.peer.fsm import GameStateMachine, State
from pursuit.peer.handshake import Handshake, run_handshake
from pursuit.peer.hint_fusion import build_hint_fuser
from pursuit.peer.sealing import SealedLog
from pursuit.peer.turn_handler import TURN, TurnHandler
from pursuit.peer.turn_sender import TurnSender
from pursuit.shared.config import scent_params


class AgreementsView:
    def __init__(self, inboxes: Any) -> None:  # handshake 'agreements' seam over negotiation
        self.agreements, self._inbox = self, inboxes.negotiation

    def get_nowait(self) -> Any:
        item = self._inbox.get_nowait()
        if item is None:
            raise queue.Empty
        return item


class PeerRuntime:
    """One sub-game to a :class:`SubgameOutcome`; every wait has a named deadline."""

    def __init__(self, role: Role | str, config: Any, transport: Any, inboxes: Any,
                 brain: Any, belief: Any, keypair: tuple[bytes, bytes], *,
                 handshake: Handshake | None = None, sysinfo: dict[str, Any] | None = None,
                 github_commit: str = "unknown", counted_games: int = 0,
                 watchdog: Any = None, clock: Any = time.monotonic, observer: Any = None,
                 sub_game_number: int | None = None) -> None:
        self.role, self.opponent = Role(role), Role(role).opponent
        self.config, self.transport, self.inboxes = config, transport, inboxes
        self.brain, self.belief, self.keypair = brain, belief, keypair
        self.handshake, self.watchdog, self.observer = handshake, watchdog, observer
        self.sub_game_number = sub_game_number
        self._step0_args = (dict(sysinfo or {}), github_commit, int(counted_games))
        game, movement = config.game, "movement_and_barriers"
        board = Board(game("board_and_agents.grid_size"), game(f"{movement}.move_set"))
        start = "cop_start" if self.role is Role.POLICE else "thief_start"
        self.state = OwnGameState(board, tuple(game(f"board_and_agents.{start}")))
        self.scent_mine = make_scent_model(scent_params(game))
        self.scent_reader = make_scent_model(scent_params(game))  # mirror of THEIR trail
        self.fuser = build_hint_fuser(config)  # live hint→belief fusion, gated + non-fatal
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
            hint_max_words=game("world.hint_max_words"), setting=game("world.map_area"),
            brain_deadline=float(config.private("network.brain_deadline_seconds")),
            model=str(config.private("trash_talk.model")))
        self.turn_timeout = float(config.private("network.turn_timeout_seconds"))
        self.audit_timeout = float(config.private("network.audit_send_timeout_seconds"))

    def _progress(self, event: str, **details: Any) -> None:
        """Print non-secret live progress without ever affecting game execution."""
        try:
            stamp = datetime.now(UTC).strftime("%H:%M:%S")
            game = self.sub_game_number if self.sub_game_number is not None else "?"
            fields = " ".join(
                f"{key}={value}" for key, value in details.items() if value is not None
            )
            suffix = f" {fields}" if fields else ""
            print(
                f"[{stamp}] LIVE role={self.role.value} game={game} event={event}{suffix}",
                flush=True,
            )
        except Exception:  # noqa: BLE001 - visibility must never alter the game
            pass

    def _notify(self, status: str, hint_in: str = "", hint_out: str = "") -> None:
        """Push a board snapshot to the optional live observer; a viewer never breaks the game."""
        if self.observer is not None:
            try:  # lazy import keeps Tk out of the headless game path
                from pursuit.interface.live_view import board_snapshot
                self.observer(board_snapshot(self, status, hint_in, hint_out))
            except Exception:  # noqa: BLE001 — a viewer must never break the game
                pass

    def run(self) -> SubgameOutcome:
        """Handshake → step-0 seal → thief-first turn loop → mutual audit → outcome."""
        started_at = datetime.now(UTC).isoformat()
        self._progress("starting")
        self.fsm.advance(State.NEGOTIATING)
        if self.handshake is None:  # the series may inject the pre-agreed handshake
            self.handshake = run_handshake(self.transport, AgreementsView(self.inboxes),
                                           self.config, self.keypair,
                                           sub_game_number=self.sub_game_number,
                                           role=self.role.value)
        self._progress(
            "handshake_locked",
            opponent=self.handshake.opponent_identity.get("group_id", "unknown"),
            game_id=self.handshake.game_id,
        )
        self.log.step0_record(self.config, *self._step0_args, self.keypair,
                              sub_game_number=self.sub_game_number)
        self.fsm.advance(State.MY_TURN if self.role is Role.THIEF else State.OPP_TURN)
        try:
            result, winner = self._turn_loop()
        except Exception as exc:  # noqa: BLE001 — ANY mid-game crash (timeout/transport/brain/
            result, winner = GameResult.TECHNICAL_LOSS, None  # belief) is a 0/0 loss; the
            # mandatory audit below STILL runs (A6) — a raise must never skip settlement.
            self._progress("technical_loss", error=f"{type(exc).__name__}: {exc}")
        if self.fsm.state is not State.GAME_OVER:
            self.fsm.advance(State.GAME_OVER)
        self.fsm.advance(State.AUDITING)  # the audit runs on EVERY ending (D4/A6)
        self._progress("audit_started")
        audit = exchange_audits(self.role, result, self.log, self.transport, self.inboxes.audits,
                                self.deadlines, self.audit_timeout, self.handshake.opponent_pubkey,
                                self.handler.commits, self.state.board)
        self._progress(
            "audit_finished",
            outbound_accepted=audit.get("outbound_accepted"),
            opponent_received=audit.get("opponent_received"),
            passed=audit.get("passed"),
            ignored_payloads=audit.get("ignored_payloads"),
        )
        if audit["forgery"]:
            result, winner = GameResult.TECHNICAL_LOSS, None  # provable forgery (A9a)
        self.fsm.advance(State.DONE)
        records = self.log.audit_reveal()
        digest_preimage = _end_state_digest_preimage(
            self.role, result, winner, records, audit.get("their_records"),
            self.state.barriers, self.state.step_number, self.handler.last_step,
            self.state.board, tuple(self.config.game("board_and_agents.cop_start")),
            tuple(self.config.game("board_and_agents.thief_start")))
        ended_at = datetime.now(UTC).isoformat()
        self._progress(
            "complete",
            result=result.value,
            winner=None if winner is None else winner.value,
            audit_passed=audit.get("passed"),
            own_steps=self.state.step_number,
            opponent_steps=self.handler.last_step,
        )
        return SubgameOutcome(
            result=result, winner=winner, scores=self.table.score_subgame(result, winner),
            audit=audit, records=records, steps=self.state.step_number,
            end_state_digest=_comparable_end_state_digest(result, digest_preimage),
            end_state_digest_preimage=digest_preimage,
            game_id=self.handshake.game_id, game_uid=self.handshake.game_uid,
            opponent_group=str(self.handshake.opponent_identity.get("group_id", "")),
            opponent_identity=dict(self.handshake.opponent_identity),
            started_at=started_at, ended_at=ended_at)

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
                self._progress(
                    "sent_turn",
                    step=sent.step,
                    action=sent.move_type.value,
                    direction=None if sent.direction is None else sent.direction.value,
                    position=list(self.state.position),
                    barrier=None if sent.barrier_cell is None else list(sent.barrier_cell),
                    terminal=sent.terminal,
                )
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
            self._progress(
                "received_turn",
                step=processed.step,
                status=processed.kind,
                barrier=None if processed.barrier_cell is None else list(processed.barrier_cell),
                captured=processed.captured,
                terminal=processed.game_over,
            )
            self._notify("opp_turn", processed.hint)
            if processed.kind != TURN:  # duplicate or rule-5 breach: reject-and-drop
                if processed.game_over:  # max_breaches consecutive rejects (D4)
                    return (GameResult.TECHNICAL_LOSS, None)
                continue
            if self.fuser is not None:  # E1 live hint fusion (gated); belief already smelled
                self.fuser.fuse(self.belief, processed.hint)
            response = processed.claim_response_due
            if processed.game_over:  # their concession answer or validated win_claim
                return ((GameResult.CAPTURE, Role.POLICE) if processed.opponent_caught
                        else (GameResult.SURVIVAL, Role.THIEF))
            if (processed.captured is None and self.opponent is Role.POLICE
                    and processed.step >= self.max_moves):
                return (GameResult.SURVIVAL, Role.THIEF)  # THEIR move ceiling is spent


def _end_state_digest(role: Role, result: GameResult, winner: Role | None,
                      records: list[dict[str, Any]], their_records: Any,
                      barriers: set[tuple[int, int]], own_steps: int,
                      their_steps: int, board: Board | None = None,
                      cop_start: tuple[int, int] | None = None,
                      thief_start: tuple[int, int] | None = None) -> str:
    """Symmetric compact end-state hash agreed for counted-game digest comparison."""
    preimage = _end_state_digest_preimage(
        role, result, winner, records, their_records, barriers, own_steps, their_steps,
        board, cop_start, thief_start)
    return sha256(preimage.encode("utf-8")).hexdigest()


def _end_state_digest_preimage(role: Role, result: GameResult, winner: Role | None,
                               records: list[dict[str, Any]], their_records: Any,
                               barriers: set[tuple[int, int]], own_steps: int,
                               their_steps: int, board: Board | None = None,
                               cop_start: tuple[int, int] | None = None,
                               thief_start: tuple[int, int] | None = None) -> str:
    """Compact JSON line hashed for ``end_state_digest``.

    Prefer revealed positions; when an opponent reveals only audited actions, replay those
    actions from the signed start cell so both sides can still reach the same final state.
    """
    positions = {
        role.value: _last_position(records, board, _start_for(role, cop_start, thief_start)),
        role.opponent.value: _last_position(
            their_records, board, _start_for(role.opponent, cop_start, thief_start)),
    }
    all_barriers = set(barriers) | _record_barriers(records) | _record_barriers(their_records)
    state = {
        "positions": {
            "police": positions.get(Role.POLICE.value),
            "thief": positions.get(Role.THIEF.value),
        },
        "barriers": [list(cell) for cell in sorted(all_barriers)],
        "turns_completed": _digest_turns_completed(role, winner, own_steps, their_steps),
        "outcome": result.value,
    }
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def _comparable_end_state_digest(result: GameResult, preimage: str) -> str | None:
    """Hash only complete capture/survival states; incomplete audits remain N/A."""
    if result not in (GameResult.CAPTURE, GameResult.SURVIVAL):
        return None
    try:
        state = json.loads(preimage)
    except json.JSONDecodeError:
        return None
    positions = state.get("positions") if isinstance(state, dict) else None
    if not isinstance(positions, dict):
        return None
    for role in ("police", "thief"):
        cell = positions.get(role)
        if not (isinstance(cell, list) and len(cell) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) for v in cell)):
            return None
    return sha256(preimage.encode("utf-8")).hexdigest()


def _start_for(role: Role, cop_start: tuple[int, int] | None,
               thief_start: tuple[int, int] | None) -> tuple[int, int] | None:
    return cop_start if role is Role.POLICE else thief_start


def _last_position(records: Any, board: Board | None = None,
                   start: tuple[int, int] | None = None) -> list[int] | None:
    latest_step = -1
    latest_position: list[int] | None = None
    replay_position = start
    replay_barriers: set[tuple[int, int]] = set()
    for record in records or []:
        payload = record.get("payload", {}) if isinstance(record, dict) else {}
        state_position, state_barriers = _parse_state(payload.get("state"))
        if state_position is not None:
            latest_position = list(state_position)
            latest_step = int(payload.get("step", latest_step) or latest_step)
        if state_barriers:
            replay_barriers = set(state_barriers)
        position = payload.get("position")
        if not (isinstance(position, list) and len(position) == 2):
            position = None
        if position and all(isinstance(value, int) and not isinstance(value, bool)
                            for value in position):
            step = _step(payload)
            if step >= latest_step:
                latest_step, latest_position = step, list(position)
        if board is not None and replay_position is not None and isinstance(
                payload.get("action"), dict):
            replay_position = _advance_from_action(board, replay_position, replay_barriers, payload)
            if replay_position is not None and _step(payload) >= latest_step:
                latest_step, latest_position = _step(payload), list(replay_position)
    return latest_position


def _advance_from_action(board: Board, position: tuple[int, int],
                         barriers: set[tuple[int, int]], payload: dict[str, Any]
                         ) -> tuple[int, int] | None:
    action = payload.get("action")
    if not isinstance(action, dict):
        return position
    if action.get("type") == "barrier":
        cell = _cell(action.get("cell"))
        if cell is not None:
            barriers.add(cell)
        return position
    if action.get("type") != "move":
        return position
    try:
        direction = Direction(str(action.get("move")))
    except Exception:  # noqa: BLE001
        return position
    return board.step(position, direction, barriers) or position


def _record_barriers(records: Any) -> set[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    for record in records or []:
        payload = record.get("payload", {}) if isinstance(record, dict) else {}
        _pos, state_barriers = _parse_state(payload.get("state"))
        seen.update(state_barriers)
        barrier = _cell(payload.get("barrier_placed"))
        if barrier is not None:
            seen.add(barrier)
        action = payload.get("action")
        if isinstance(action, dict) and action.get("type") == "barrier":
            barrier = _cell(action.get("cell"))
            if barrier is not None:
                seen.add(barrier)
    return seen


_SELF_RE = re.compile(r"self=(\[-?\d+,\s*-?\d+\])")
_BARRIERS_RE = re.compile(r"barriers=(\[.*\])")


def _parse_state(state: Any) -> tuple[tuple[int, int] | None, list[tuple[int, int]]]:
    if not isinstance(state, str):
        return None, []
    self_match = _SELF_RE.search(state)
    position = _cell(_literal(self_match.group(1))) if self_match else None
    barrier_match = _BARRIERS_RE.search(state)
    raw = _literal(barrier_match.group(1)) if barrier_match else []
    barriers = [_cell(item) for item in raw] if isinstance(raw, list) else []
    return position, [cell for cell in barriers if cell is not None]


def _literal(text: str) -> Any:
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def _cell(value: Any) -> tuple[int, int] | None:
    if (isinstance(value, list | tuple) and len(value) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
        return (value[0], value[1])
    return None


def _step(payload: dict[str, Any]) -> int:
    try:
        return int(payload.get("step", 0) or 0)
    except Exception:  # noqa: BLE001
        return 0


def _digest_turns_completed(role: Role, winner: Role | None,
                            own_steps: int, their_steps: int) -> int:
    if winner is role:
        return int(own_steps)
    if winner is role.opponent:
        return int(their_steps) or max(0, int(own_steps) - (1 if role is Role.THIEF else 0))
    return max(int(own_steps), int(their_steps))
