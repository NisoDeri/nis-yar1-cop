# Reference Architecture Map — Game-P2P-Cop-Chase (Prof. Segal's reference simulator, code/book v3.0.0)

**Purpose.** This is the single document a coding agent reads before touching the codebase.
It maps the professor's reference repo (`reference/Game-P2P-Cop-Chase/`, config schema 1.10 / shared schema 1.3 / artifact schema 1.1), records the EXACT wire protocol other groups will speak, the extension-point contracts, the four JSON artifact schemas, the private-vs-shared config split, every known gap vs the rule-book (160-page PDF, `final_project/police_thief_p2p.pdf`), per-subsystem reuse verdicts, and the PDF verification outcome.

**Precedence.** Book + Appendix F (parameters) + Appendix E (55 rules) OVERRIDE the reference repo whenever they disagree (`FINAL_PROJECT_BRIEF.md` §5). Gaps flagged below are where the repo loses.

**License.** The repo carries a restrictive GTAI educational EULA (enrolled students only, no redistribution). The professor permits building on it; the brief says "study, don't copy." Treat it as a blueprint + selectively re-implemented utilities, keep attribution, and make our graded repos our own work.

---

## 1. Layer diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ INTERFACE                                                                    │
│  cli.py (argparse: peer --role {thief,police} [--stub-llm] [--no-gui];       │
│          replay --log PATH)                                                  │
│  gui/  LivePeerApp (player.py) ── PeerWindow (window.py) ── BoardView        │
│        LiveControls / live_apply (event dispatch)                            │
│        ReplayApp (replay.py) ── replay_data (verify/normalize/sibling-log)   │
│        game_mode.py (Table-22 provider→display mapping)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ SDK FACADE                                                                   │
│  sdk/sdk.py  SimulationSdk — builds LLM (StubLlm | GatedLlm(ClaudeCli)+      │
│              ApiGatekeeper) + transport ONCE; validate_agreement fail-fast;  │
│              runs series; emits 4 JSON artifacts + Hebrew report + email     │
│  sdk/series.py run_series — N sub-games, role alternation (odd=natural),     │
│              fresh PeerRuntime per sub-game, RestartSeries loop (MAX 10)     │
├─────────────────────────────────────────────────────────────────────────────┤
│ PEER RUNTIME (one independent peer's lifecycle per sub-game)                 │
│  peer/runtime.py     PeerRuntime: negotiate → turn loop → audit              │
│  peer/handshake.py   negotiate(rt): signed-terms exchange, derive game ids   │
│  peer/turn_handler.py TurnHandler.process(): fold opponent msg → belief/     │
│                       smell/barriers; raise capture/win outcome flags        │
│  peer/turn_sender.py  brain.decide → apply_move (fallback HOLD) → seal →     │
│                       deposit+decay own scent → build_turn_message → send    │
│  peer/sealing.py      sealed_step_record / sealed_spec_record (step-0) /     │
│                       terms_from_config / REQUIRED_TERMS / build_turn_message│
│  peer/summary.py      finish(): audit exchange, tamper_forfeit, summary dict │
│  peer/controls.py + control_link.py + runtime_control.py                     │
│                       GameControls (thread-safe pause/stop/restart/speed) +  │
│                       opt-in bidirectional control channel (7 statuses)      │
├─────────────────────────────────────────────────────────────────────────────┤
│ DOMAIN (pure, zero I/O)                                                      │
│  board.py OwnGameState(own_state.py) rules.py scoring.py game_ids.py         │
│  smell.py (SmellField) belief.py (BeliefGrid) brains.py (BrainBase/          │
│  ThiefBrain/PoliceBrain/Decision) crypto.py (CommitReveal)                   │
│  negotiation.py protocol.py (TurnMessage/ControlMessage/AuditPayload)        │
│  constants.py exceptions.py                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ STRATEGY SEAM (the graded core plugs in here)                                │
│  strategy/__init__.py  load_brain_cls / resolve_brain ([strategy] config)    │
│  strategy/trash_talk.py TrashTalk (template, 0 tokens) / LlmTrashTalk        │
│  strategy/talk_providers.py resolve_trash_talk ([trash_talk] 4 modes)        │
├─────────────────────────────────────────────────────────────────────────────┤
│ INFRA + SHARED                                                               │
│  infra/mcp_server.py  FastMCP HTTP server per peer, 4 tools → PeerInboxes    │
│  infra/mcp_client.py  McpTransport (outbound calls + inbox polling)          │
│  infra/llm_provider.py ClaudeCliProvider (`claude -p`, API keys STRIPPED)    │
│  infra/email_sender.py EmailSender (external gg:email skill, DRAFT only)     │
│  shared/config.py     ConfigManager (game.toml + game.json overlay)          │
│  shared/gatekeeper.py ApiGatekeeper  shared/rate_limiter.py (sliding window) │
│  shared/sysinfo.py    collect_spec() (step-0 hardware)  shared/version.py    │
├─────────────────────────────────────────────────────────────────────────────┤
│ REPORT                                                                       │
│  report/artifacts.py + artifact_helpers.py + artifact_schemas.py + emit.py   │
│      (the 4 standardized JSON artifacts)  report/report_writer.py (Hebrew)   │
└─────────────────────────────────────────────────────────────────────────────┘

Two fully symmetric peers. Each = FastMCP HTTP server (own port; thief 8801,
police 8802 by default) + fastmcp.Client to the opponent's URL. No referee.
Only runtime dependency: fastmcp>=3.4.3, python>=3.13, uv-managed.
```

---

## 2. Per-subsystem summaries

### 2.1 Domain core (board / rules / scoring / state / ids / constants / exceptions)

All files ≤83 lines, pure, unit-tested.

| File | Key API |
|---|---|
| `domain/board.py` | `Board(size, moves)` — stateless grid. `step(origin, dir, barriers) -> Cell|None` is the SINGLE physics primitive (used for both movement and barrier legality). `legal_moves(pos, barriers) -> [(Direction, Cell)]`, `neighbors()`, `distance(a,b)` — Manhattan iff move set has no diagonal, else Chebyshev. |
| `domain/own_state.py` | `OwnGameState` — the peer's authoritative PRIVATE state: position, visited set, merged barrier set (own + opponent-declared via `note_barrier(cell)`), `my_barriers` quota counter, `step_number`, per-step JSON log. `apply_move(move_type, direction, barriers_max) -> bool` is the single legality gate; False leaves state untouched. ALL action types (MOVE/BARRIER/HOLD) increment `step_number`. |
| `domain/rules.py` | `GameRules(max_steps)`: `thief_result(state)` → `"survival"` iff `step_number >= max_steps` (judged on thief's OWN counter, HOLDs count). Static `is_captured(state, claim)` → truthful land-on answer on the thief side. |
| `domain/scoring.py` | `score_subgame(result, roles, scoring_cfg)` — keys `capture_cop/capture_thief/survival_cop/survival_thief`; any unknown result string ⇒ 0/0 technical loss. `aggregate(scores, tie_score)` — additive tie (+2 each, 2-group series only). |
| `domain/game_ids.py` | `derive_game_ids(terms, gidA, gidB)`: `game_id = "<a>-vs-<b>"` (sorted); `game_uid = UUID(sha256(canonical_json(terms) + "|" + "|".join(sorted_gids))[:16])` — deterministic, NOT RFC-4122-valid, zero extra round-trips. Both peers must construct byte-identically. |
| `constants.py` | `Role`, `MoveType` (MOVE/BARRIER/HOLD), 8 `Direction` enums + `DELTAS` (row grows south: N=(-1,0)), `directions_from_move_set()` (drops STAY/HOLD, silently ignores unknowns, falls back to FULL KING SET if nothing parses — danger), `NONCE_BYTES=16`, `VERDICT_TRUTH="truth"`/`VERDICT_LIE="lie"`, fixed strings `FALLBACK_HINT`, `FINAL_CAUGHT_HINT="You got me."`, `NO_HINT_PLACEHOLDER="(silence)"`. |
| `exceptions.py` | `SimulationError` root; Config/Provider(Auth/Timeout/Cli/Parse)/Move/Crypto/RateLimit errors; `RestartSeries` — an exception used as a control-flow signal to restart the whole series. |

Critical semantics:
- Coordinates are `(row, col)`, 0-indexed, origin top-left, row grows DOWN.
- Orthogonal-only physics exists ONLY if config supplies `move_set = ["N","S","E","W","STAY"]`; default is legacy 8-direction king movement (book violation if unset).
- Capture is entirely claim-driven: the cop attaches `capture_claim = its landing cell` to EVERY MOVE message (turn_sender), the thief answers truthfully via `is_captured`; the audit proves lies.
- Barrier placement: cop-only, via a Direction from its CURRENT cell (adjacent, in-bounds, not already barriered); quota `barriers_max` from config; irreversible; `direction=None` rejected ⇒ **placing on own cell is impossible in this impl (book gives 5 options)**.
- Illegal brain decisions are force-degraded to HOLD by the runtime ("never stall the loop").

### 2.2 Scent / belief / brains / trash-talk (the strategy layer)

| File | Key API |
|---|---|
| `domain/smell.py` | `SmellField`: `deposit(cell, intensity)` — 5×5 radial emission, falloff `intensity/(half+1)` per **Chebyshev** ring ⇒ 0.9/0.6/0.3, rounded 3dp, **max-merged** (not additive); raises ValueError below `min_center_intensity` (0.5, anti-decoy). `decay_all()` — **subtractive** `max(0, v − 0.10)` (NOT the book's multiplicative `(1−ρ)τ`). `snapshot()/absorb()` — `{"r,c": float}` string-keyed dict, the wire format. `strongest_cell()`. |
| `domain/belief.py` | `BeliefGrid(board_size, smell_trust=4.0, orthogonal=False)`: uniform prior; `observe_smell(cells)` — `P *= (1 + trust·intensity)` then normalize (scent is the ONLY evidence source — hints are never fused); `diffuse()` — motion model (von Neumann+stay iff orthogonal=True, else 3×3 king); `exclude(cell)`, `most_likely()`, `as_matrix()`. |
| `domain/brains.py` | `BrainBase` / `ThiefBrain` / `PoliceBrain` + `Decision` dataclass. `decide(state, belief, opponent_hint, setting, barriers_max, deadline_seconds, short_threshold) -> Decision`; move is ALWAYS pure Python via `_decide_move` → `_pick_move`. ThiefBrain: maximize distance from `belief.most_likely()`, tiebreak unvisited. PoliceBrain: minimize distance; 15% random chance to BARRIER the cell it would have stepped onto. |
| `strategy/trash_talk.py` | `TrashTalk` (template, 0 tokens, landmark lines for New York/London/Paris, thief lies ~40%) and `LlmTrashTalk` (every_n_steps, deadline via throwaway ThreadPoolExecutor, JSON contract `{"message","verdict","reasoning"}`, ANY failure → template fallback; full prompt sealed for audit). 15-word cap. |
| `strategy/talk_providers.py` | `resolve_trash_talk`: provider = `template|claude_cli|ollama|claude_api`; ollama = stdlib POST to `localhost:11434/api/generate` with `format:"json"`, default model `llama3.2`; claude_api default `claude-haiku-4-5`. Unknown provider silently → template. |
| `strategy/__init__.py` | `load_brain_cls("package.module:Class")` importlib loader with `issubclass(cls, BrainBase)` check; `resolve_brain(config, role, llm, rng)` honors `strategy.thief_class`/`strategy.police_class`. |

Per-opponent-turn update order (turn_handler): `belief.diffuse()` → `belief.observe_smell(msg.smell_grid)` → `smell_field.absorb(msg.smell_grid)` → `smell_field.decay_all()`. Own turn (turn_sender): `my_scent.deposit(position, emit_intensity)` → `my_scent.decay_all()`. Decay is message-driven, not clock-driven; each peer decays its own outgoing trail too.

`belief.smell_trust_weight` (private game.toml, default 4.0) is an explicitly sanctioned unsigned per-team tuning knob.

### 2.3 Crypto / commit-reveal / negotiation / sealing

| File | Key API |
|---|---|
| `domain/crypto.py` | `CommitReveal`: `commit_of(payload, nonce) = sha256(canonical_json(payload) + "|" + nonce).hexdigest()` where `canonical_json = json.dumps(sort_keys=True, ensure_ascii=False, separators=(",",":"))`. **Nonce is pipe-appended AFTER the JSON, NOT a key inside it** (the brief's §7 snippet puts nonce inside — the two are INCOMPATIBLE; a literal-book peer will fail our audit unless negotiated). `seal(payload) -> {nonce, commit}`; `verify()` uses plain `!=` (not `compare_digest`); `audit_records(records) -> {passed, verified_steps, failed_steps}`. |
| `domain/negotiation.py` | `Negotiation(terms, identity).signed() -> {terms, nonce, signature=commit_of(terms,nonce), identity}`; `verify_peer()` first requires **exact dict equality of terms** (both configs value-identical), then re-verifies the signature. Identity (group_id/name/members/repos/mcp_servers/llm_model/hardware spec) is deliberately UNSIGNED. |
| `peer/sealing.py` | `sealed_step_record` payload keys: `step, state ("grid=NxN;self=[r, c];barriers=[[r,c],…]" sorted), position, move, intent (=decision.verdict), verdict (DUPLICATE of intent — replicate both or hashes break), hint, prompt_discussion {llm_prompt, llm_reasoning, bluff_classification}, model, tokens_step, tokens_total, response_seconds, random_move`. `sealed_spec_record` (step-0): `{step:0, type:"system_spec", spec: collect_spec(), model, code_version, group_name, sub_game_number}` — records[0] of the SAME commit chain. `terms_from_config` / `REQUIRED_TERMS` (board_size, smell_grid_size, decay_per_step, emit_intensity, min_center_intensity, max_steps, barriers_max, thief_start, cop_start — no code defaults, fail-fast). `build_turn_message`. |
| `peer/handshake.py` | `negotiate(rt)`: exchange signed agreement → `verify_peer` → `derive_game_ids` → **game clock starts here** (negotiation latency eats the timer). |

Commit-reveal is 2-stage, not the book's 4-stage: TurnMessage carries commit only; no per-step Acknowledge, no per-step Reveal; ALL nonces revealed only in the single end-of-game AuditPayload. No asymmetric key / ed25519 anywhere — step-0 "signing" is the same nonce-commit. No `github_commit` in step-0 (book rule 24/53 requires it).

### 2.4 Peer lifecycle / turn loop / series / CLI+SDK

- **Lifecycle** (`runtime.run()`): negotiate → pump(PLAYING) → **thief unconditionally moves first** → `_turn_loop()` → pump(GAME_OVER) → `summary.finish()`.
- **Turn token is implicit**: receiving a TurnMessage IS the token ("makes this peer green"). No token field; no dedup — a replayed message could desync ownership.
- **Turn loop**: poll (`network.poll_interval_seconds` 0.5) → on timeout past deadline: `_result=('timeout', OWN role)` — **the waiting peer is recorded WINNER** (book says timeout = 0/0 technical loss — must fix). Deadline resets on every received message (a slow-but-alive opponent never times out). On message: `TurnHandler.process` → outcome flags (`i_won` / `opponent_won` / `i_am_caught` → send mandatory `FINAL_CAUGHT_HINT` final message) → else `_take_turn`.
- **Outbound turn**: brain.decide (deadline = GUI speed slider or `llm.step_deadline_seconds` 30) → `apply_move` else forced HOLD → thief self-checks survival on its own send → cop attaches `capture_claim` on every MOVE → seal → deposit+decay scent → send.
- **End of game** (`summary.finish`): audit skipped for results in `('timeout','stopped')` (the most dispute-prone endings get NO verification); otherwise exchange AuditPayloads, run `audit_records` on the opponent's records; failure ⇒ result rewritten to `tamper_forfeit`, honest peer wins.
- **Statuses**: WAITING/THINKING/PLAYING/PAUSED/STOPPED/GAME_OVER/QUIT — broadcast LABELS with overlay precedence, **no transition table, nothing rejected** (brief rule 4–5 requires a guarded FSM — must add).
- **Series** (`sdk/series.py`): `num_games` from config (default 1; book fixes 6); role alternation `role_for` (odd = natural role, even = swapped) — a full-series peer needs BOTH brain classes; fresh PeerRuntime + full re-negotiation per sub-game; `RestartSeries` loop (drain inboxes, MAX_RESTARTS=10); one shared ControlLink survives restarts.
- **SDK**: `SimulationSdk.run_peer(role, stub_llm, transport=None, listener=None, controls=None)` — transport/listener/controls injectable (integration tests run both peers in-process). `_build_llm` hard-codes StubLlm-or-ClaudeCli; the 4 trash-talk modes live in the strategy layer, not here. Emits 4 artifacts + legacy Hebrew report + unconditional result email.
- **CLI**: `peer --role {thief,police} [--config DIR] [--stub-llm] [--no-gui]`; `replay --log PATH`. No flags for ports/URLs/series length — config-file only.

### 2.5 Infra + shared

- **`infra/mcp_server.py`**: `start_peer_server(role, host, port)` → FastMCP(`police-thief-{role}`) HTTP on a daemon thread; port-free preflight probe. `PeerInboxes` = 4 `queue.Queue`s (agreements/turns/audits/controls). **Tools do ZERO validation** — enqueue and return `{"ok": true}`; all enforcement is local.
- **`infra/mcp_client.py`**: `McpTransport(opponent_url, inboxes, connect_timeout=60, retry_interval=1.0, audit_send_timeout=10, control_send_timeout=2)`. Per-call `async with Client(url)` via `asyncio.run`; retry-until-deadline; `exchange_audit` best-effort BOTH ways (opponent's server may die mid-response; `None` return is legal). `drain_inboxes()` clears turns/controls/audits but NOT agreements.
- **`infra/llm_provider.py`**: `ClaudeCliProvider` — pipes prompt file to `claude -p --output-format json`, **strips ANTHROPIC_API_KEY/CLAUDECODE/ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN/API_TIMEOUT_MS** from the env so it bills the browser-login subscription (matches our zero-API-key course rule). Token usage from wrapper `usage` (input + cache_creation + cache_read + output). Timeout/auth/CLI/parse exceptions.
- **`infra/email_sender.py`**: shells out to an external `gg:email` skill on the PROFESSOR'S machine path, creates a Gmail DRAFT only, disabled by default. **Must be rewritten** — book requires autonomous OAuth send-only Gmail with the result JSON as an ATTACHMENT to `rmisegal+uoh26finalgame@gmail.com`. (We have a working HW6 Gmail OAuth sender to port.)
- **`shared/config.py`** (164 lines — violates the ≤150 rule, split before reuse): loads private `game.toml` + `rate_limits.json` (version-gated to `1.10`), deep-merges optional shared `game.json` via `_translate_shared` (Appendix-F schema → dotted TOML keys). **Only a subset of game.json is translated**: `num_games` yes, but `rate_limiter_gatekeeper`, `response_timeout_sec` (30), `watchdog_timeout_sec` (60), token budget, diversity fields are NOT wired to runtime — the private `turn_timeout_seconds=180` silently wins over the agreed 30/60. game.json's own `schema_version` is never validated.
- **`shared/gatekeeper.py` + `rate_limiter.py`**: sliding-window RPM limiter (NOT the book's token-bucket) + retry loop; `retry_after_seconds` is loaded but never slept; `concurrent_max` never enforced; no daily Quota Manager, no DOS detector — the book's 3-gate Gatekeeper must be built.
- **`shared/sysinfo.py`**: `collect_spec()` — OS/CPU/RAM/GPU via PowerShell CIM + nvidia-smi (fixes Win32's 4GB VRAM cap); cached per process.

### 2.6 GUI + Report

- **Live GUI**: local-truth-only enforced STRUCTURALLY — live events never contain the opponent position (`render(opponent_pos=None)`), satisfying rules 8–9 architecturally. Belief heatmap white→red normalized to the current peak (`#ff{gb}{gb}`, gb = 255·(1−0.8·p/peak)); 52px cells; slider 0–60s is BOTH the enforced LLM deadline and the animation pacer (fast turns padded up with sleep). Sub-game dropdown (1–6) overrides `num_games` at Start; mismatched picks → signature check refuses to play.
- **ReplayApp** (the mandatory verifier): re-feeds a saved log through the pure domain (BeliefGrid rebuilt from RECORDED smell grids, never stored belief), re-verifies every commit via `CommitReveal.verify` → per-step label `"<hash24>... [verified OK]"` (lowercase; there is NO big banner — add one for the mandatory screenshot), auto-discovers the opponent's sibling log at `logs/<opponent_group_id>/log_<game_id>_gNN.json` to overlay the true track, frozen-track amber banner for shorter logs, accepts both legacy and standardized log dialects (`normalize_log`; note it defaults missing audit to `{'passed': True}` — do not copy that leniency).
- **Report**: pure builders in `report/artifacts.py` + `emit.py` writes all four files into `logs/<own_group_id>/` (group_id keys everything, because roles alternate). `github_commit` emitted as literal `"unknown"` and opponent tokens hard-coded 0 — both must be wired for the book. `report_writer.py` emits a separate all-Hebrew official report (סוג_דוח='משחק_ליגה_רשמי' etc.) with a self-referential consensus hash.
- **TWO different canonical hashers coexist**: `canonical_sha256` (compact separators `(",",":")`) for `config_sha256`; `consensus_signature` (DEFAULT spaced separators) for group blocks, log mutual_agreement, and the Hebrew report. Mixing them silently fails verification — replicate each exactly per field.
- The mutual result signature deliberately hashes only the SYMMETRIC outcome subset `{game_id, aggregate, sub_games:[{sub_game_number, roles, result, winner_group, score}]}` — excluding per-peer tokens/timestamps so both independently-emitted result files agree byte-identically. Essential trick to copy.

---

## 3. EXACT wire protocol (cross-group interop surface — do not deviate without negotiation)

**Transport**: FastMCP over HTTP (streamable). Each peer runs its own server, name `police-thief-{role}`, bound to `network.my_port` (reference: thief **8801**, police **8802**), URL path `/mcp` (e.g. `http://127.0.0.1:8802/mcp`; league play swaps in the ngrok public URL). Client: `fastmcp.Client(opponent_url)` → `await client.call_tool(name, {...})`.

**Exactly 4 tools**, all fire-and-forget mailbox pushes returning `{"ok": true}` with zero validation:

| # | Tool | Argument key | Body |
|---|---|---|---|
| 1 | `negotiate` | `message` | signed agreement (below) |
| 2 | `receive_turn` | `message` | TurnMessage (also passes the implicit turn token) |
| 3 | `submit_audit` | **`payload`** ← the odd one out; sending `message` here fails schema validation | AuditPayload |
| 4 | `receive_control` | `message` | ControlMessage (advisory, best-effort, 2s send timeout) |

**Retry semantics a partner must tolerate**: sender retries the same call every 1s up to 60s (negotiate/connect), 10s (audit), 2s (control) — duplicates possible; receiver queues have no dedup.

### 3.1 Signed agreement (negotiate)

```json
{
  "terms": {
    "board_size": 7, "smell_grid_size": 5, "decay_per_step": 0.10,
    "emit_intensity": 0.9, "min_center_intensity": 0.5,
    "max_steps": 35, "barriers_max": 14,
    "setting": "New York", "hint_max_words": 15,
    "axis_origin_corner": "top-left", "axis_start_index": 0,
    "thief_start": [3,3], "cop_start": [0,0], "num_games": 6
  },
  "nonce": "<32 hex>",
  "signature": "<sha256hex = commit_of(terms, nonce)>",
  "identity": { "group_id": "...", "group_name": "...", "members": [...],
                "repos": {...}, "mcp_servers": {...}, "llm_model": "...",
                "spec": { ...hardware... } }
}
```
`verify_peer` requires EXACT dict equality of `terms` (types included) then signature re-check. Identity is unsigned. Mismatch = hard `CryptoError`, no in-protocol bargaining — terms are agreed out-of-band and typed identically into both configs.

### 3.2 TurnMessage (receive_turn)

```json
{
  "step": 4, "sender": "thief" | "police",
  "hint": "<free NL, ≤15 words, may lie>",
  "smell_grid": {"2,3": 0.9, "2,4": 0.6},          // "r,c" string keys, cells > 0 only
  "commit": "<sha256hex of sealed step payload>",    // nonce withheld until audit
  "timestamp": "<ISO-8601 UTC>",
  "barrier_placed": [r,c] | null,                    // cop's mandatory truthful declaration
  "capture_claim": [r,c] | null,                     // cop only; its own landing cell, EVERY move
  "claim_response": {"claim":[r,c],"caught":true} | null,  // thief's crypto-obligated honest answer
  "win_claim": {"type":"survival"} | null            // thief
}
```
`from_dict` hard-fails (TypeError) listing missing required fields (step/sender/hint/smell_grid/commit/timestamp). Fixed literals a partner will see: final message hint `"You got me."`, empty-hint placeholder `"(silence)"`, fallback hint `"I keep moving through the streets."`.

### 3.3 AuditPayload (submit_audit)

```json
{ "sender": "thief", "result_claim": "capture" | "survival" | "timeout",
  "records": [ { "payload": { ...sealed step payload, records[0] is the step-0
                              system_spec... }, "nonce": "<32 hex>", "commit": "<sha256hex>" } ] }
```

### 3.4 ControlMessage (receive_control)

```json
{ "kind": "enable" | "status" | "restart" | "quit", "sender": "thief"|"police",
  "sub_game_number": 1, "status": "WAITING|THINKING|PLAYING|PAUSED|STOPPED|GAME_OVER|QUIT",
  "step_budget": 30.0, "payload": {} | null }
```
`from_dict` silently drops unknown keys (forward-compatible). Channel active only when BOTH peers sent `enable`; restart is then auto-approved and raises `RestartSeries` on both sides.

### 3.5 Hash/canonicalization contracts (byte-exact or interop dies)

1. **Commit**: `sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",",":")) + "|" + nonce)` — nonce OUTSIDE the JSON; `ensure_ascii=False` (Hebrew hints hash as raw UTF-8).
2. **game_uid**: `UUID(bytes=sha256(canonical_json(terms) + "|" + gid1 + "|" + gid2)[:16])`, gids sorted — not RFC-4122-valid; copy byte-for-byte.
3. **config_sha256**: compact-separator canonical sha256 of the shared terms.
4. **consensus_signature**: sha256 of `json.dumps(sort_keys=True, ensure_ascii=False)` with DEFAULT (spaced) separators — different from (3)!

---

## 4. Extension-point contracts

### 4.1 `[strategy]` — the graded core

Private `game.toml`:
```toml
[strategy]
thief_class  = "my_team.strategy:MyThiefBrain"
police_class = "my_team.strategy:MyPoliceBrain"
```
- Loader: `strategy.load_brain_cls` — importlib on `module:Class`, MUST subclass `BrainBase` (TypeError otherwise); unset ⇒ shipped heuristic brain. Roles alternate per sub-game ⇒ supply BOTH classes.
- Instantiated as `cls(llm, rng=rng, trash=resolve_trash_talk(...))` — **keep the `__init__(self, llm=None, rng=None, trash=None)` signature**.
- Override points:
  - `_pick_move(self, moves, state, belief) -> (Direction, (row,col))` — moves pre-filtered legal; movement policy, both roles.
  - `_decide_move(self, state, belief, barriers_max) -> (MoveType, Direction|None)` — the ONLY place to choose BARRIER placement (cop).
  - Do NOT override `decide()` unless re-wiring trash-talk; the LLM never picks the move (book allows an LLM-move exception ONLY by explicit mutual documented agreement, and legality must still be locally enforced).
- Inputs available: `state.board.legal_moves/distance`, `state.position/visited/barriers/my_barriers`, `belief.most_likely()/as_matrix()/diffuse()/observe_smell()/exclude()`.
- Output `Decision(move_type, direction, hint, verdict "truth"|"lie", fallback, random_move, response_seconds, prompt_text, reasoning)` — `verdict/prompt/reasoning` are SEALED into the audited record.

### 4.2 `[trash_talk]` — verbal/deception layer (private, not negotiated)

```toml
[trash_talk]
provider = "template"   # template | ollama | claude_api | claude_cli
model = "qwen2.5:7b"    # for ollama/claude_api
every_n_steps = 3       # LLM only every Nth turn; template between
ollama_url = "http://localhost:11434/api/generate"
```
Custom provider: subclass `TrashTalk`, contract `say(role, state, belief, setting, opponent_hint, deadline=None) -> (hint, verdict, reasoning, prompt)`; hint capped at `hint_max_words`. Any error/deadline miss → template fallback (loop never stalls). Unknown provider silently → template.

### 4.3 Other seams

- **Transport injection**: any object with `exchange_agreement/send_turn/poll_turn/exchange_audit` (+ optional `send_control/poll_control/drain_inboxes`) replaces McpTransport (`SimulationSdk.run_peer(transport=...)`) — how integration tests run both peers in-process.
- **LLM provider**: any object with `.send(prompt)->str`, `.tokens_consumed:int`, `.last_usage:dict`.
- **Listener**: event callback (`negotiated/incoming/moved/game_over/control_*/series_restart`) for GUI or headless drivers; **GameControls** = pause/play/stop/restart/quit/enable/set_speed.
- **Private belief tuning**: `[belief] smell_trust_weight` (default 4.0) — sanctioned unsigned knob.
- **rate_limits.json** `services` map — add any service name for `ApiGatekeeper(config, service=...)`.

---

## 5. The four JSON artifacts (schema_version "1.1", timezone "Asia/Jerusalem")

Filenames (from `game_id` + `<NN:02d>`): `declaration_<game_id>.json`, `config_<game_id>_g<NN>.json`, `log_<game_id>_g<NN>.json`, `result_<game_id>.json`. All embed `_schema` (verbatim self-documenting prose the grader expects), `schema_version`, `game_id`, `game_uid`, and a `links` block with literal `g<NN>` placeholders. Each peer writes ALL FOUR into `logs/<own_group_id>/`.

1. **Declaration** (pre-game): `declaration_type "pre_game_declaration"`, timezone, `game_started_at/ended_at`, `num_sub_games`, `max_tokens_per_game` (default 200000), `groups.group_1/group_2` each `{group_id, group_name, members[], repos{cop,thief}, mcp_servers{cop,thief}, llm_model, hardware_spec{cpu_type,cpu_freq_mhz,cpu_cores,ram_gb,gpu_model,vram_gb}, signature = consensus_signature(block-sans-signature)}`.
2. **Config**: shared terms spread at top level (board_and_agents / world / movement_and_barriers / scoring / pheromones / network_and_league / rate_limiter_gatekeeper) + `config_name` + `config_sha256 = canonical_sha256(shared_terms)`.
3. **Log**: `summary {sub_game_number, group_id, role, opponent_group_id, result, winner_role, steps, timezone, started_at, ended_at, duration_seconds, tokens_total, audit}` + `records` (sealed commit-reveal records incl. step-0 system_spec, WITH nonces — post-reveal on disk) + `mutual_agreement {opponent_group_id, sha256 = consensus_signature(records), confirmed}`.
4. **Result** (THE mandatory email attachment): `sub_games[] {sub_game_number, roles {gid:role}, started_at, ended_at, result, winner_group, tie, github_commit {gid: hash}  ← repo emits "unknown", MUST wire real hash, tokens {own, opp} ← opp hard-coded 0, MUST fix, score, log_files, audit {log_verified, tampered}}` + `final_result {total_score, sub_games_won, ties, winner_group, series_tie, tokens_total_series}` + `mutual_agreement {sha256 = consensus_signature(SYMMETRIC-only subset), confirmed}`. Book also requires all 4 repo links in the result (currently declaration-only).

Plus a fifth, non-standard artifact: the official Hebrew report (`report_writer.py`, book §8) with Hebrew field names and a self-referential consensus hash.

---

## 6. Config: private vs shared split

| File | Nature | Contents |
|---|---|---|
| `config/<role>/game.json` | **SHARED — byte-identical both peers, hashed + signed in the handshake; mismatch = refuse to play** | board_and_agents (grid 7×7, starts (3,3)/(0,0), axis origin/index), world (map_area "New York", hint_max_words 15), movement_and_barriers (move_set `["N","S","E","W","STAY"]`, max_barriers 14, max_moves/survival 35), scoring (20/5, 5/10, tie 2, tech 0), pheromones (0.9 / 0.10 / 5×5 / min_center 0.5 — the 0.5 floor is a repo invention, negotiate it), network_and_league (num_games — ship 1, book fixes 6; token_budget 200000; response_timeout 30; watchdog 60), rate_limiter_gatekeeper |
| `config/<role>/game.toml` | **PRIVATE per peer (version "1.10")** | group identity (group_id/name/members/repos/mcp_servers), `[network]` my_port / opponent_url / turn_timeout_seconds=180 / poll 0.5 / connect 60, `[belief]` smell_trust_weight, `[gui]`, `[paths]`, `[play]` seed + step_speed, `[llm]` provider=claude / model / step_deadline_seconds=30 / short_prompt_threshold=10, `[strategy]` (commented), `[trash_talk]` (commented), `[email]` |
| `config/<role>/rate_limits.json` | private | claude 30 rpm / 2 conc / 5s retry / 3 retries; email 5/1/10/2; queue depth 100, timeout 300s |

Traps: `_translate_shared` wires only a SUBSET of game.json into runtime (num_games yes; gatekeeper/timeouts NO — private 180s turn timeout silently beats the agreed 30/60); game.json's schema_version is never validated; per-game filenames `config_<game_id>_g<NN>.json` (book) are not implemented — one static game.json per role dir.

---

## 7. Gaps vs the book (consolidated — each is work WE must do)

### Game-rule correctness (technical-loss risk)
1. **Capture rule 2 (barrier-on-thief = capture, rule 46) — ABSENT.** capture_claim rides only MOVE turns; nothing checks barrier == thief cell.
2. **Capture rule 3 (jailed thief = capture, rule 47) — ABSENT.** A fully-walled thief HOLDs to a survival win — the OPPOSITE of the book.
3. **Barrier on the cop's OWN cell impossible** (direction=None rejected) — book gives 5 placement options, impl gives 4.
4. **Default physics is 8-dir king movement** when `move_set` unset/unparseable (silent fallback, no ConfigError) — book fixes 4-orthogonal+stay; correctness is pure config discipline. `BeliefGrid` likewise defaults to king diffusion.
5. **Timeout awards the waiting peer the win** — book: technical loss 0/0 to both; audit is also SKIPPED on timeout/stopped endings.
6. **Survival counting ambiguity**: judged on the thief's OWN `step_number >= max_steps`, HOLDs and barriers count as steps — book says "35 valid moves"; semantics must be negotiated/locked.
7. **num_games defaults 1** — book fixes 6; nothing enforces it.
8. Scoring values are config-supplied, never asserted against Appendix F — a bad config silently mis-scores.

### Scent model (RULE 23 — must lock ONE formula pre-series)
9. **Decay is subtractive** `max(0, τ−0.10)` vs book's multiplicative `max(0,(1−ρ)τ+Δτ)`; **deposit max-merges** vs book's additive Δτ. Book wins — implement the book's law (or config-selectable) and be ready to negotiate; the formula TEXT + numeric example is never hashed (only the parameters are in the signed terms).
10. Falloff detail (linear Chebyshev rings 0.9/0.6/0.3, 3-dp rounding) is a repo-specific choice — exactly what rule 23 says to exchange and hash; never assume the partner runs the same code.

### Crypto / protocol
11. Commit-reveal is 2-stage (commit + end-game reveal), not the book's 4-stage (Commit→Acknowledge→Reveal→Final Audit) — no per-step Ack lock, no per-step Reveal.
12. **Hash construction differs from the book's reference snippet** (nonce pipe-appended vs nonce-inside-JSON; `ensure_ascii=False` vs default) — a literal-book partner WILL fail cross-audit; the hash construction is itself a must-negotiate term.
13. No asymmetric signing anywhere; step-0 "signature" = self-hash. If the lecturer's "pre-supplied key" means a real keypair, add it.
14. **No `github_commit` in step-0 or result** (emitted as `"unknown"`) — rules 24/53 require it; wire `git rev-parse HEAD`.
15. Opponent tokens hard-coded 0 in result rows; 4 repo links missing from result JSON.

### Architecture / rules 1–10
16. **No guarded state machine** — statuses are labels; no transition table, no illegal-transition rejection (rules 4–5).
17. **No watchdog** (60s freeze / crash monitoring / controlled data extraction — rule 7); only the per-turn deadline exists and it resets on any message.
18. **No tunneling integration** (rule 10) — localhost config only.
19. Gatekeeper is one sliding-window RPM limiter — book requires 3 cumulative gates (daily Quota Manager, token-bucket, DOS detector/circuit-breaker); `retry_after_seconds` never slept; `concurrent_max` never enforced; no 429 backoff.
20. **Gmail: draft-only via an external skill on the professor's machine, disabled** — book requires autonomous OAuth send-only Gmail, JSON as ATTACHMENT.

### Hygiene
21. `shared/config.py` = 164 lines (>150 rule); `gui/player.py` 154 / `gui/replay.py` 167 raw lines borderline.
22. Belief never fuses the verbal hint — **the book's flagship lie-detection (hint-vs-scent, named reliability coefficient) does not exist anywhere and is ours to build.** Barrier policy is a 15% random stub; both brains are baseline heuristics. This is where the grade is.

---

## 8. Per-subsystem reuse verdicts

| Subsystem | Verdict | Notes |
|---|---|---|
| Domain core (board/scoring/game_ids/constants/exceptions) | **Reuse as-is** | Keep canonical-JSON contract byte-identical. Pin `move_set` in config; make `directions_from_move_set` raise on garbage. |
| rules.py / own_state.py | **Extend** | Add barrier-on-thief + jailed-thief capture; add own-cell barrier (5th option). |
| Scent/belief/brains/trash-talk | **Extend (graded core)** | Wire format + Brain/Decision contracts as-is. Re-implement decay/deposit per the book (config-selectable). Build: real cop trapping policy, real thief evasion, hint-vs-scent Bayesian lie detection. |
| Crypto/negotiation/protocol/sealing | **Reuse as-is** (interop surface) | Do NOT rename tools or change the hash formula unilaterally. Extend sealing (github_commit, scent-formula lock) in a NEW module (sealing.py is at 138 lines). |
| Peer runtime / series / SDK / CLI | **Reuse, extend at seams** | Add guarded FSM, book timeout semantics (0/0), watchdog, per-game config filenames. Never fork runtime for strategy. |
| infra mcp_server/mcp_client | **Reuse as-is** | Interop-critical; tool names + `message`/`payload` param keys frozen. |
| Gatekeeper/rate_limiter | **Extend** | Add quota manager + DOS gate + retry_after sleep + token-bucket. |
| email_sender | **Rewrite** | Port our HW6 Gmail OAuth send-only sender; JSON attachment. |
| shared/config.py | **Reuse after splitting** (150-line fix) | Also translate the untranslated game.json fields; validate schema_version. |
| GUI live + replay | **Reuse as-is, extend** | Add a prominent "Verified OK" banner for the mandatory screenshot; brand labels. Our HW6 web replay UI is an optional creativity bonus on top. |
| Report/artifacts/emit | **Reuse, extend emit** | Wire real github_commit + opponent tokens + 4 repo links; keep both hashers and the symmetric-subset mutual-signature trick exactly. |

---

## 9. PDF verification outcome (160-page rulebook read against the brief)

**Verified clean**: every number in brief §10 matches Appendix F exactly; all 55 rules match Appendix E in number, action-type, and sanction; filenames/emails (Table 20), LLM modes (Table 21), `[strategy]` (Table 22), Moodle mechanics, submission checklist, physics, scent formula+lock, 4-stage commit-reveal, and step-0 fields all match.

**Discrepancies (brief is wrong/incomplete)**:
1. **Move-policy tracks** (PDF Ch6 pp.59–61): three coequal ALGORITHMIC tracks — (1) pure heuristics Manhattan+Bayes, (2) *your own heuristic algorithm* (belief+scent+barriers+lookahead, e.g. minimax/expectimax), (3) optional Q-Learning. An LLM-mapped move policy is NOT a standard track.
2. **LLM deciding the move** (PDF p.66): allowed as an explicit, mutual, documented pre-game exception (a real negotiation lever); local legality enforcement still mandatory. The brief presents the prohibition as absolute.
3. **Rule 24 sanction** (PDF p.145): skipping the signed step-0 hardware declaration forfeits the *computational-fairness BONUS* — not disqualification.

**Additions (in the PDF, absent from the brief)**:
- **Fifth grading criterion** (p.110/114): the whole submission is graded per the course-intro file "המלצות לכתיבה והגשה של תוכנה בעזרת סוכני AI" — Dr. Segal's Professional Software Excellence baseline applies in full.
- **Feature-branch workflow required** (Appendix C p.133): every substantive capability developed on a dedicated branch, merged to main only when stable.
- **Contract is a floor, not a ceiling** (p.34): may never weaken the book, MAY upgrade rules, and exploiting undefined loopholes is "permitted and even desirable" when legal and mutually agreed.
- **Reliability coefficient** (p.63): each incoming hint must be Bayes-combined with an explicit named מקדם מהימנות.
- Arena examples include London/Paris, not only New York.

**Deadline**: NOT in the PDF; the league runs "with no pre-dictated schedule" (Ch9). Deadline + any 75→100 league mapping come from Moodle/lecture only.

**League scoring (what the book actually says)**: one counted game per opponent (warm-ups free); diversity reward 10 fixed for a win vs a NEW opponent; ≥2 counted games vs different groups to pass; ≤10 counted; 6 sub-games per series fixed; series tie = 2 each; lecturer applies an unspecified normalization bonusing algorithmic efficiency on modest hardware.

**Emails**: general/repo sharing `rmisegal@gmail.com`; agent JSON reports (the single mandatory target) `rmisegal+uoh26finalgame@gmail.com`.

**Read confidence**: pp. 34–67, 85–98, 110–120, 133–160 read in full; pp. 1–33, 68–84, 99–109, 121–132 (Appendix A Gmail setup, Appendix B config schema) keyword-scanned only — line-verify before relying on exact Gmail/config-schema claims from the brief.

---

## 10. Interop landmine checklist (pin these with the partner group BEFORE the series)

1. Hash construction: nonce pipe-appended after compact canonical JSON with `ensure_ascii=False` — vs the book snippet's nonce-inside-JSON. Agree on ONE.
2. `submit_audit` uses param key `payload`; the other three tools use `message`.
3. game_uid = non-RFC UUID from sha256[:16] of `canonical(terms)|gid1|gid2` (sorted gids).
4. Scent law: repo subtractive+max-merge vs book multiplicative+additive — rule 23 forces one hashed formula + numeric example; also 3-dp rounding, Chebyshev rings, min_center 0.5.
5. Survival counting: whose counter, do HOLD/BARRIER count as "valid moves".
6. Timeout semantics: repo waiting-peer-wins vs book 0/0 — and audit currently skipped on timeout.
7. Two canonical hashers (compact vs spaced separators) used for different fields.
8. Fixed literals: "You got me." / "(silence)" / fallback hint; thief moves first; turn token = message possession.
9. Terms dict must be exactly equal, types included; identity unsigned; negotiation is out-of-band.
10. Barrier semantics: repo 4 adjacent cells only vs book 5 (own cell included); barrier-on-thief and jailed-thief captures must both be agreed as implemented.

---

## 11. Team assets to leverage (build-recommendation context)

- **HW6**: refereed 5×5 cops-and-robbers — FastMCP experience, BFS pursuit/evasion tactics (seed for real brains), **working Gmail OAuth send** (fixes gap #20), web replay UI (creativity extension over the Tk replay).
- **Stable-hostname tunneling know-how** — rule 10 solved with stable public URLs for the declaration's `mcp_servers` block; provider decided at Stage 5 (the old paid ngrok account was deleted: fresh ngrok reserved domains or a free named Cloudflare tunnel, D5 / LEAGUE-OPS §2).
- **Local Ollama** (qwen2.5:7b/14b/0.5b, aya-expanse:8b, RTX 3500 Ada 12GB) — `[trash_talk] provider="ollama"` at zero API tokens; strong computational-fairness story on a laptop.
- **Zero-API-key constraint** — matches the reference's `claude_cli` design (env-stripped subscription billing) and the template/ollama zero-token modes.
