# Module Architecture — `pursuit/` (our P2P Cops & Robbers engine)

Group **nis-yar1** · Conforms to `planning/DECISIONS.md` D1–D13. Wire compatibility frozen to the
reference simulator per `planning/reference_map.md` §3 (D1). Book + Appendix F override the
reference wherever they disagree (`FINAL_PROJECT_BRIEF.md`, precedence rule).

Hard gates baked into every table below: **every `.py` ≤150 lines**, ruff clean, pytest ≥85%,
zero hardcoded parameters (config-driven everything).

---

## 1. Layer diagram

Our own implementation, mirroring the reference's proven layering (reference_map §1) so the
grader recognizes the SDK/Orchestrator/Gatekeeper patterns, but with the reference's gaps fixed
(guarded FSM, watchdog, 3-gate Gatekeeper, book physics, dual dialects).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ INTERFACE            pursuit/interface/                                       │
│   cli.py — argparse: peer --role {police,thief} [--config DIR] [--stub-llm]   │
│            [--no-gui] · replay --log PATH · configgen (per-game config)       │
│   gui/ live_app · board_view (belief heatmap; LOCAL TRUTH ONLY — render       │
│        never receives the opponent position, rules 8–9) · controls ·          │
│        replay_app · replay_data (normalize + re-verify + "Verified OK" banner)│
├──────────────────────────────────────────────────────────────────────────────┤
│ SDK / ORCHESTRATOR   pursuit/sdk/          (rule 3: SINGLE entry point)       │
│   sdk.py — builds config, dialects, LLM(+Gatekeeper), transport, watchdog     │
│            ONCE; validate-agreement fail-fast; emits artifacts + email        │
│   series.py — N sub-games, role alternation, fresh PeerRuntime per sub-game   │
├──────────────────────────────────────────────────────────────────────────────┤
│ PEER RUNTIME         pursuit/peer/   (one peer's lifecycle per sub-game)      │
│   runtime.py — negotiate → turn loop → audit                                  │
│   fsm.py (guarded state machine, rules 4–5) · handshake.py · turn_handler.py  │
│   turn_sender.py · sealing.py · step0.py (signed HW declaration + git hash)   │
│   audit.py (end-game mutual verification, ALWAYS runs — D4) ·                 │
│   watchdog.py (rule 7) · controls.py (pause/stop/restart + control channel)   │
├──────────────────────────────────────────────────────────────────────────────┤
│ DOMAIN (pure, zero I/O)   pursuit/domain/                                     │
│   board · own_state · rules (incl. barrier-on-thief + jailed-thief captures)  │
│   scoring · game_ids · constants · exceptions · negotiation · protocol        │
│   scent/    ⟨DIALECT SEAM D3⟩  reference.py | book.py behind one protocol     │
│   belief/   grid · likelihood (emission inversion) · motion (adversarial)     │
│             · hints (reliability-coefficient fusion — lie detection)          │
│   crypto/   ⟨DIALECT SEAM D3⟩  canonical (two hashers) · commit_reveal        │
├──────────────────────────────────────────────────────────────────────────────┤
│ STRATEGY SEAM (the graded core)   pursuit/strategy/                           │
│   loader (__init__) · base (BrainBase/Decision, reference-compatible) ·       │
│   thief · police · pathing (BFS true distance, mobility) · barriers (cages)   │
│   · deception · trash_talk · providers (template/ollama/claude_cli-stub) ·    │
│   hint_parser (incoming NL → structured claim, feeds reliability coeff)       │
├──────────────────────────────────────────────────────────────────────────────┤
│ INFRA                pursuit/infra/                                           │
│   mcp_server (FastMCP HTTP, 4 frozen tools → inboxes, dedup) ·                │
│   mcp_client (outbound calls + polling) · llm_providers (Ollama; ClaudeCli    │
│   stubbed off — D8) · gmail_sender (HW6 OAuth send-only port) ·               │
│   tunnel (ngrok preflight, rule 10)                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ SHARED               pursuit/shared/                                          │
│   config (private game.toml) · shared_terms (game.json — FULLY translated) ·  │
│   config_gen (config_<game_id>_g<NN>.json) ·                                  │
│   gatekeeper + gates (3-gate: quota → token-bucket → DOS, D5) · sysinfo       │
├──────────────────────────────────────────────────────────────────────────────┤
│ REPORT               pursuit/report/                                          │
│   artifacts (4 JSON builders, schema 1.1) · emit · result (+ schemas.json     │
│   data file with the verbatim _schema prose)                                  │
└──────────────────────────────────────────────────────────────────────────────┘

Two fully symmetric peers. Each = FastMCP HTTP server (thief 8801 / police 8802
locally; one reserved ngrok domain per role in league play) + fastmcp.Client to
the opponent URL. No referee (brief §0). Runtime deps: fastmcp, python≥3.13, uv.
```

---

## 2. Module list, responsibilities, line budget

Budget rule: target ≤140 lines per file (10-line headroom under the hard 150 gate); any file
trending past 140 during build is split immediately (plan.md R7). `__init__.py` re-export stubs
(≤10 lines) are excluded from the count except where listed as real modules.

### interface/ — 6 files, ~730 lines
| File | Responsibility | Budget |
|---|---|---|
| `cli.py` | argparse entry: `peer` / `replay` / `configgen` subcommands; everything else config-file driven | 90 |
| `gui/live_app.py` | Live Tk window wiring: listener events → widgets; slider = LLM deadline + pacer | 140 |
| `gui/board_view.py` | Board canvas + belief heatmap (white→red, peak-normalized); opponent position structurally absent (rules 8–9) | 140 |
| `gui/controls.py` | Start/pause/stop/restart/speed widgets → GameControls | 100 |
| `gui/replay_app.py` | Replay window: step-through of a saved log (mandatory verifier app, rule 20) | 140 |
| `gui/replay_data.py` | Log normalize + per-step commit re-verification + sibling-log overlay + prominent **"Verified OK"** banner state (never defaults audit to passed — reference_map §2.6 warning) | 120 |

### sdk/ — 2 files, ~250 lines
| File | Responsibility | Budget |
|---|---|---|
| `sdk.py` | `SimulationSdk` — the single Orchestrator entry (rule 3). Composes config, dialects, brains, LLM behind Gatekeeper, transport, watchdog, listener, controls; injectable seams for tests; emits artifacts + email at series end | 140 |
| `series.py` | `run_series`: `num_games` (book fixes 6) sub-games, role alternation (odd=natural), fresh `PeerRuntime` + re-negotiation per sub-game, bounded restart loop | 110 |

### peer/ — 10 files, ~1,270 lines
| File | Responsibility | Budget |
|---|---|---|
| `runtime.py` | Lifecycle: negotiate → turn loop → audit; owns FSM instance; force-degrade illegal brain decisions to HOLD (never stall) | 140 |
| `fsm.py` | Guarded turn state machine — §4 below (rules 4–5) | 130 |
| `handshake.py` | Signed-terms exchange, `verify_peer` exact-equality + signature, `derive_game_ids`; game clock starts here | 110 |
| `turn_handler.py` | Fold opponent TurnMessage: dedup'd, FSM-gated → belief/scent/barriers update; capture/survival/claim outcome flags incl. **barrier-on-thief** and **jailed-thief** checks (rules 46–47, D4) | 140 |
| `turn_sender.py` | brain.decide (deadline) → `apply_move` else HOLD → seal → own-scent deposit+decay → capture_claim on every cop MOVE → send | 140 |
| `sealing.py` | Sealed step records (reference-compatible payload keys incl. duplicated `intent`/`verdict`), `REQUIRED_TERMS` fail-fast, `build_turn_message` | 130 |
| `step0.py` | Step-0 signed hardware declaration: `collect_spec()` + code version + group + sub-game + **real `github_commit`** + rule-23 scent-formula lock hash; records[0] of the commit chain (rules 23–24, 53) | 100 |
| `audit.py` | End-game AuditPayload exchange + `audit_records` verification; **runs on ALL endings incl. timeout/stopped** (fixes reference gap #5); mismatch → `tamper_forfeit` | 120 |
| `watchdog.py` | Freeze/crash monitor + controlled data extraction — §5 below (rule 7) | 120 |
| `controls.py` | Thread-safe GameControls + opt-in bidirectional control channel (7 wire statuses projected from FSM) | 140 |

### domain/ core — 9 files, ~875 lines
| File | Responsibility | Budget |
|---|---|---|
| `board.py` | Stateless grid; `step()` single physics primitive; `legal_moves`; Manhattan distance (orthogonal move set) | 90 |
| `own_state.py` | Peer's authoritative PRIVATE state: position, visited, merged barriers, quota counter, step number, per-step log; `apply_move` single legality gate | 130 |
| `rules.py` | Survival (≥35 valid moves, semantics per negotiated term), `is_captured` truthful answer, **barrier-on-thief capture**, **jailed-thief capture** (rules 46–47) | 100 |
| `scoring.py` | Appendix F table 17 scoring + additive tie; unknown result ⇒ 0/0; values asserted against Appendix F at load (fixes gap #8) | 80 |
| `game_ids.py` | `game_id` + deterministic `game_uid` — byte-identical to reference derivation (reference_map §3.5.2) | 60 |
| `constants.py` | Role/MoveType/Direction enums + DELTAS (row grows south); `directions_from_move_set` **raises on garbage — no king fallback** (D4, fixes gap #4); fixed wire literals ("You got me.", "(silence)", fallback hint) | 100 |
| `exceptions.py` | `SimulationError` tree + `IllegalTransition` + `RestartSeries` control-flow signal | 60 |
| `negotiation.py` | Signed agreement build/verify (terms exact dict equality, then signature; identity unsigned — wire contract §3.1) | 110 |
| `protocol.py` | `TurnMessage` / `ControlMessage` / `AuditPayload` dataclasses, `from_dict` hard-fail on missing required fields, forward-compatible unknown-key drop on control | 145 |

### domain/scent/ — 3 files, ~260 lines ⟨dialect seam⟩
| File | Responsibility | Budget |
|---|---|---|
| `__init__.py` | `ScentModel` protocol (`deposit / decay_all / snapshot / absorb / strongest_cell`) + `make_scent(terms)` factory keyed on the signed `pheromones.dialect` term | 60 |
| `reference.py` | Reference dialect: Chebyshev-ring falloff 0.9/0.6/0.3, 3-dp rounding, **max-merge** deposit, **subtractive** decay `max(0, v−ρ)`, min-center floor | 100 |
| `book.py` | Book dialect: `τ(t+1)=max(0,(1−ρ)·τ+Δτ)` multiplicative decay, **additive** deposit (brief §5) | 100 |

### domain/belief/ — 4 files, ~480 lines (graded core, D6)
| File | Responsibility | Budget |
|---|---|---|
| `grid.py` | `BeliefGrid`: prior, normalize, `exclude`, `most_likely`, `as_matrix`; barrier masking; von Neumann-only motion (orthogonal physics) | 130 |
| `likelihood.py` | Inverts the known 5×5 emission profile (per active scent dialect) into a position likelihood; **zero-scent as evidence** | 120 |
| `motion.py` | Adversarial motion-model diffusion: thief-flees / cop-chases kernels instead of uniform | 100 |
| `hints.py` | **Reliability-coefficient hint fusion** (PDF p.63): Bayes-combine parsed hints with a trust weight learned from scent-contradiction; lie detection lowers the coefficient | 130 |

### domain/crypto/ — 2 files, ~200 lines ⟨dialect seam⟩
| File | Responsibility | Budget |
|---|---|---|
| `canonical.py` | The TWO canonical hashers, kept separate and named: `canonical_sha256` (compact separators, for commits/config) and `consensus_signature` (spaced separators, for group blocks/mutual agreement) — reference_map §3.5 | 70 |
| `commit_reveal.py` | `CommitReveal(dialect)`: seal / verify (`secrets.compare_digest`) / `audit_records`; fresh `secrets.token_hex(16)` nonce per commit, secret until final audit (rule 18) | 130 |

### strategy/ — 10 files, ~1,240 lines (the grade lives here)
| File | Responsibility | Budget |
|---|---|---|
| `__init__.py` | `load_brain_cls("module:Class")` + `resolve_brain` from `[strategy]`; `issubclass(BrainBase)` enforced | 80 |
| `base.py` | `BrainBase` + `Decision` — reference-compatible contract (`_pick_move`, `_decide_move`, `__init__(llm, rng, trash)`); move is ALWAYS pure Python (rule 25) | 130 |
| `thief.py` | Thief brain: mobility maximization (k-step reachable count — never jailed), scent-aware routing, edge discipline, deception hooks | 140 |
| `police.py` | Police brain: BFS true-distance interception, belief-mass herding, cage triggering (replaces the reference's 15% coin flip) | 140 |
| `pathing.py` | Barrier-aware BFS distances, reachable-cell counts, flight prediction — shared by both brains and the lab | 130 |
| `barriers.py` | Barrier-cage planner: funnel + quadrant sealing, quota economics, self-wall-in guard | 140 |
| `deception.py` | Planned-lie policy: lie when expected opponent-belief-error gain is highest; produces `Decision.verdict` | 110 |
| `trash_talk.py` | Template provider (0 tokens, arena landmark lines, 15-word cap) + LLM wrapper with deadline + template fallback on ANY failure; full prompt sealed for audit | 130 |
| `providers.py` | `resolve_trash_talk` (`template | ollama | claude_api | claude_cli`); unknown → template; Ollama default `qwen2.5:7b` (D8) | 120 |
| `hint_parser.py` | Incoming NL hint → structured claim (direction/landmark/class) via Ollama-or-regex; feeds `belief/hints.py`; free NL only, never numeric protocol (rules 26–27) | 120 |

### infra/ — 5 files, ~620 lines
| File | Responsibility | Budget |
|---|---|---|
| `mcp_server.py` | FastMCP HTTP server per peer; the 4 frozen tools (`negotiate`/`receive_turn`/`submit_audit`(param `payload`)/`receive_control`) → inbox queues with `(sender, step)` dedup; port preflight | 110 |
| `mcp_client.py` | `McpTransport`: per-call client, retry-until-deadline, best-effort audit both ways, `drain_inboxes` | 140 |
| `llm_providers.py` | `OllamaProvider` (stdlib POST, JSON format, token count) + `ClaudeCliProvider` stub (env-stripped, OFF by default — D8); common `.send/.tokens_consumed/.last_usage` contract | 140 |
| `gmail_sender.py` | HW6 port: OAuth 2.0 **send-only** scope, result JSON as ATTACHMENT to `rmisegal+uoh26finalgame@gmail.com`; secrets outside repo (rules 30, 32–35, 39–40) | 140 |
| `tunnel.py` | ngrok preflight: reserved domain up, URL matches declaration `mcp_servers`, fail-fast otherwise (rule 10) | 90 |

### shared/ — 6 files, ~720 lines
| File | Responsibility | Budget |
|---|---|---|
| `config.py` | Private `game.toml` + `rate_limits.json` loader, version-gated; also owns package version constant | 130 |
| `shared_terms.py` | Shared `game.json` load + validation + **FULL translation to runtime** (timeouts/gatekeeper/token budget included — fixes reference gap: shared 30/60s must beat private defaults); Appendix-F fixed-value assertions; minimums enforced upward-only | 120 |
| `config_gen.py` | Per-game `config_<game_id>_g<NN>.json` generator + `config_sha256` + rule-23 formula-lock file (formula text + numeric worked example + its SHA-256) | 110 |
| `gatekeeper.py` | `ApiGatekeeper(service)`: composes the 3 gates fail-fast; honored 429/`retry_after` backoff; fronts BOTH `gmail` and `llm` services | 110 |
| `gates.py` | The 3 gate classes — §6 below (QuotaManager, TokenBucket, DosGuard) | 140 |
| `sysinfo.py` | `collect_spec()`: OS/CPU/RAM/GPU-VRAM (nvidia-smi correction), cached per process — step-0 input | 110 |

### report/ — 3 files (+1 data file), ~370 lines
| File | Responsibility | Budget |
|---|---|---|
| `artifacts.py` | Pure builders for declaration/config/log artifacts (schema 1.1, timezone Asia/Jerusalem, `_schema` prose loaded from `schemas.json` data file) | 140 |
| `result.py` | Result artifact: real `github_commit` per sub-game, all **4** repo links, real token totals both sides, **symmetric-subset** mutual-agreement SHA (reference_map §2.6 trick, gaps #14–15 fixed) | 120 |
| `emit.py` | Writes all four files to `logs/<own_group_id>/`, per-game filenames | 110 |

**Total: 60 source files, ~7,015 budgeted lines — average 117/file, worst case 145,
all under the 150-line hard gate with headroom.** (Range fits the 45–60-file planning envelope;
tests live alongside in `tests/`, unconstrained by the source budget.)

---

## 3. Dialect seam design (D3 — strategy pattern over hash + scent)

Two known book-vs-reference splits could void league games. We ship **both sides of each**,
selected by the *signed shared config* and therefore cryptographically locked pre-series
(rule 23):

```
shared game.json (signed terms)                 factories
  crypto.dialect:  "reference" | "book"      ─▶ commit_reveal.CommitReveal(make_hash_dialect(terms))
  pheromones.dialect: "reference" | "book"    ▶ scent.make_scent(terms)
  pheromones.formula_sha256: "<64 hex>"         (rule-23 lock of formula text + worked example)
```

- **`HashDialect`** protocol — `commit(payload: dict, nonce: str) -> hex`:
  - `ReferenceHash`: `sha256(canonical_sha256_json(payload) + "|" + nonce)` — nonce pipe-appended
    OUTSIDE the JSON, `ensure_ascii=False` (reference_map §3.5.1). **Default.**
  - `BookHash`: `sha256(canonical_json({**payload, "nonce": nonce}))` — nonce inside, per the
    brief §7 snippet.
- **`ScentModel`** protocol — `deposit / decay_all / snapshot / absorb / strongest_cell`:
  - `reference.py`: max-merge deposit, Chebyshev rings 0.9/0.6/0.3 (3-dp), subtractive decay.
  - `book.py`: additive Δτ, multiplicative `max(0,(1−ρ)τ+Δτ)`.
  - The wire format (`{"r,c": float}` snapshot) is identical for both, so the dialect is pure
    local math — which is exactly why it MUST match the opponent and be locked.
- Everything downstream is dialect-agnostic: `CommitReveal`, sealing, audit, replay verification
  take the dialect instance; `belief/likelihood.py` keys its emission-inversion table on the
  active scent dialect.
- Because the dialect ids live **inside the signed terms**, a partner running the other dialect
  fails `verify_peer`'s exact-equality check at negotiation — cross-dialect games are refused
  up front, never corrupted mid-game (tested by the dialect matrix, plan.md §5.3).
- `config_gen` emits, per series, the formula text + a numeric worked example whose SHA-256 is
  the `formula_sha256` term — the artifact both groups exchange and hash under rule 23.

---

## 4. Turn state machine (rules 4–5; fixes reference gap #16)

`peer/fsm.py`. The reference broadcasts 7 status *labels* with no transition table; we implement
a real guarded FSM and **project** it onto those labels for control-channel wire compatibility.

**States**
`BOOT → NEGOTIATING → OPP_TURN ⇄ MY_TURN → SENDING → … → GAME_OVER → AUDITING → DONE`,
plus overlays `PAUSED` (from OPP_TURN/MY_TURN) and terminal `ABORTED`.

**Transition table (explicit dict `{(state, event): next_state}` — anything absent is illegal)**

| From | Event | To | Notes |
|---|---|---|---|
| BOOT | server_up ∧ config_valid | NEGOTIATING | tunnel preflight passed in league mode |
| NEGOTIATING | terms_verified | OPP_TURN / MY_TURN | thief moves first (wire contract); step-0 record sealed on exit |
| OPP_TURN | turn_received(step == expected) | MY_TURN | dedup upstream; deadline disarmed |
| OPP_TURN | deadline_expired | GAME_OVER(timeout) | **0/0 technical loss, D4 — never waiting-peer-wins** |
| MY_TURN | decision_ready | SENDING | brain deadline enforced |
| SENDING | sent_ok | OPP_TURN | scent deposited + decayed before send |
| MY_TURN / OPP_TURN | outcome(capture · survival · caught) | GAME_OVER | incl. barrier-on-thief / jailed-thief (rules 46–47) |
| OPP_TURN / MY_TURN | control(pause) | PAUSED | resume returns to the exact prior state |
| any non-terminal | control(stop) / restart_agreed | GAME_OVER(stopped) / RestartSeries | restart drains inboxes, bounded retries |
| GAME_OVER | — (unconditional) | AUDITING | **audit runs on every ending, timeout included** (fixes gap #5) |
| AUDITING | audit_done | DONE | mismatch ⇒ result rewritten `tamper_forfeit` first |
| any | watchdog_fire / fatal | ABORTED | controlled extraction (§5), exit non-zero |

**Illegal-transition handling (rule 5)**
- Lookup miss raises `IllegalTransition(state, event)`.
- **Inbound network events** (opponent messages): the message is rejected — dropped, logged with
  full payload hash, counted. Duplicates are already removed upstream by `(sender, step)` dedup
  (closes the reference's replay-desync hole, reference_map §2.4 / plan.md R9). K consecutive
  illegal inbound events (config `fsm.max_illegal_events`) ⇒ `GAME_OVER(protocol_breach)` — and
  the audit still runs, so the log proves who misbehaved.
- **Internal events** (our own bug driving an illegal edge): escalate to the watchdog's
  controlled-extraction path — never a silent pass, never an uncontrolled crash.
- Wire projection: FSM state → the reference's 7 broadcast labels
  (WAITING/THINKING/PLAYING/PAUSED/STOPPED/GAME_OVER/QUIT) so partner GUIs read us natively.

---

## 5. Watchdog design (rule 7; fixes reference gap #17)

`peer/watchdog.py` — a daemon thread with a heartbeat registry, independent of the turn loop
(the reference's only timer is the per-turn deadline, which resets on any message — a
slow-but-alive livelock never fires it).

- **Heartbeats**: turn-loop pump (each poll tick), transport (each send/recv), GUI event loop,
  MCP server thread liveness. Each source has a `last_beat` timestamp.
- **Freeze threshold**: `watchdog_timeout_sec` from the SHARED config (agreed 60s, Appendix F
  table 19) — wired to runtime via `shared_terms.py` (the reference never translates it; its
  private 180s silently wins — gap we fix).
- **On fire (freeze or unhandled exception → same path)**, *controlled data extraction*:
  1. freeze the FSM into `ABORTED`;
  2. flush the official per-step log with all sealed records so far to
     `logs/<gid>/log_<game_id>_g<NN>.json` (partial but audit-able — "loss of official log" is
     the sanction rule 7 exists to prevent);
  3. write `crash_<ts>.json` diagnostics (FSM history, last messages, heartbeat ages);
  4. best-effort control QUIT to the opponent (2s timeout) + best-effort audit exchange (10s);
  5. record result `technical` **0/0** (D4), emit whatever artifacts are derivable, exit non-zero.
- The watchdog also runs the tunnel preflight re-check on a slow cadence during league games so
  a dead ngrok session is detected before a turn deadline turns it into a technical loss.

---

## 6. 3-gate Gatekeeper (D5; Appendix F table 19; fixes reference gap #19)

`shared/gatekeeper.py` + `shared/gates.py`. Cumulative, fail-fast, in this order, in front of
**both** the Gmail path and the LLM path (`rate_limits.json` `services` map: `gmail`, `llm`):

1. **QuotaManager** — daily cap per service, persisted to `logs/state/quota_<service>.json`
   (survives restarts; resets at midnight Asia/Jerusalem). The last line before account
   suspension.
2. **TokenBucket** — `tokens ← min(C, tokens + r·Δt)`, `allow ⟺ tokens ≥ 1`; C and r derived
   from config (requests/min 30 min., parallel 2 min., queue depth 100 min. — all minimums,
   raisable only). Rate tokens ≠ LLM tokens ≠ OAuth tokens (brief §12 — three meanings, never
   conflated; LLM token metering lives in the provider, OAuth in `gmail_sender`).
3. **DosGuard** — circuit-breaker: rolling-window anomaly (calls/min above ceiling, or N
   consecutive failures) ⇒ OPEN (path locked entirely); cooldown ⇒ HALF_OPEN single probe ⇒
   CLOSED on success. Saves the account from our own infinite loop.

Failure semantics: HTTP 429 ⇒ mark failure, **sleep the configured `retry_after_seconds`**
(loaded AND honored — the reference loads it and never sleeps), max `retries_before_failure`
attempts, then surface a typed error to the Orchestrator. Never blind-retry.

---

## 7. Config schema (private vs shared vs per-game)

Zero hardcoded parameters; every value below has exactly one home.

### 7.1 `config/<role>/game.toml` — PRIVATE per peer (never shared, never signed)
```toml
schema_version = "1.0"                    # ours; validated at load
[identity]   group_id = "nis-yar1"  group_name / members / repos / mcp_servers
[network]    my_port = 8802  opponent_url = "http://…/mcp"  poll_seconds = 0.5
             connect_timeout = 60        # per-turn/watchdog timeouts come from SHARED config
[play]       seed = 0  step_speed = 0
[belief]     smell_trust_weight = 4.0    # sanctioned unsigned tuning knob
             zero_scent_weight / motion_model = "adversarial"   # our D6 knobs
[strategy]   police_class = "pursuit.strategy.police:CagePolice"
             thief_class  = "pursuit.strategy.thief:GhostThief"
[trash_talk] provider = "template"  model = "qwen2.5:7b"  every_n_steps = 3
             ollama_url = "http://localhost:11434/api/generate"
[email]      enabled = true  target = "rmisegal+uoh26finalgame@gmail.com"
             credentials_path = "…outside repo…"          # .gitignored (rules 39–40)
[gui] / [paths] / [fsm] max_illegal_events = 3
```

### 7.2 `config/<role>/game.json` — SHARED, byte-identical both peers, hashed + signed in the
handshake (mismatch = refuse to play). Appendix F blocks:
`board_and_agents` (7×7, starts, axis origin/index) · `world` (arena, hint_max_words 15) ·
`movement_and_barriers` (move_set `["N","S","E","W","STAY"]`, barriers 14, ceiling/survival 35)
· `scoring` (20/5, 5/10, tie 2, technical 0) · `pheromones` (0.9, ρ=0.10, 5×5, min_center,
**dialect**, **formula_sha256**) · `crypto` (**dialect**) · `network_and_league`
(num_games 6, token_budget 200000, response_timeout 30, watchdog 60) · `rate_limiter_gatekeeper`.
Unlike the reference, `shared_terms.py` translates **all** of it into runtime (gap fixed) and
asserts the fixed values against Appendix F constants at load.

### 7.3 Per-game generator (brief §10 config rules)
`uv run python -m pursuit configgen --game-id <gidA>-vs-<gidB> --sub NN`
→ writes `config/<role>/config_<game_id>_g<NN>.json` (the negotiated game.json snapshot) +
prints its `config_sha256` + emits the rule-23 formula-lock file. The per-game file is committed
to the repo before play and its commit hash emailed — per-game filenames the reference never
implemented (reference_map §6 traps).

### 7.4 `config/<role>/rate_limits.json` — private: `services.gmail` / `services.llm`
(requests/min, parallel, retry-delay, retries, queue depth, daily quota) — Appendix F table 19
minimums enforced upward-only.

---

## 8. Zero-Trust two-process runtime map (rules 1–2; D2)

```
 MACHINE A (or same machine, dev)              MACHINE B (or same machine, dev)
┌─────────────────────────────────┐          ┌─────────────────────────────────┐
│ OS PROCESS 1 — POLICE           │          │ OS PROCESS 2 — THIEF            │
│ uv run python -m pursuit peer \ │          │ uv run python -m pursuit peer \ │
│        --role police            │          │        --role thief             │
│ config/police/  (own game.toml, │          │ config/thief/   (own game.toml, │
│   game.json, rate_limits.json,  │          │   game.json, rate_limits.json,  │
│   config_<gid>_gNN.json)        │          │   config_<gid>_gNN.json)        │
│ logs/<own_group_id>/  (own)     │          │ logs/<own_group_id>/  (own)     │
│ FastMCP server :8802 ◄──────────┼──HTTP────┼─► FastMCP server :8801          │
│ fastmcp.Client ─────────────────┼──only!───┼── fastmcp.Client                │
│ own OwnGameState · own belief · │          │ own OwnGameState · own belief · │
│ own scent · own nonces · own GUI│          │ own scent · own nonces · own GUI│
└─────────────────────────────────┘          └─────────────────────────────────┘
        │ league play                                  │ league play
        ▼                                              ▼
  ngrok reserved domain #1                      ngrok reserved domain #2
  (police URL in declaration)                   (thief URL in declaration)
```

Enforcement, not convention:
- **Only channel** between the sides is MCP-over-HTTP through the 4 public tools. No shared
  files, no shared environment, no shared queues, no common log dir.
- All mutable state lives in per-process instances (`OwnGameState`, `BeliefGrid`, `ScentModel`,
  nonce store); `pursuit/` has **zero module-level mutable state** — a dedicated test imports
  every module and asserts it (instant-disqualification insurance for rule 2).
- Live GUI is per-process and structurally blind to the opponent (render API has no opponent
  position parameter — rules 8–9 satisfied architecturally, as in the reference).
- Dev self-play uses the injected in-process transport ONLY inside the test/lab harness — the
  shipped `peer` entry point cannot be configured into single-process play.
- The two deliverable repos deepen the split at distribution time: cop repo ships no thief brain
  and vice versa (plan.md §3), while the engine stays identical (D2).
