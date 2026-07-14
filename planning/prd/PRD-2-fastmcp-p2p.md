# PRD-2 — Basic FastMCP P2P Infrastructure (Book Ch2; roadmap stage 2)

## Purpose
Split the game into **two separate OS processes**, each a symmetric FastMCP HTTP server + client,
exchanging **pure numeric geometry over localhost** (brief §14.2). Goal: prove the pipe works
before loading complex content. This stage freezes our league interop surface (D1).

## In scope
- FastMCP server per peer with **exactly the reference's 4 tools** and param keys:
  `negotiate`/`receive_turn`/`receive_control` (key `message`), `submit_audit` (key `payload`)
  (reference_map §3); mailbox-queue inboxes, zero in-tool validation, all enforcement local.
- MCP client transport: per-call connect, retry-until-deadline semantics (1s/60s negotiate,
  10s audit, 2s control), duplicate tolerance.
- Signed-terms negotiation handshake and `game_id`/`game_uid` derivation (byte-exact reference
  formula, reference_map §3.5.2).
- Turn loop with implicit turn token (possession of the TurnMessage), thief moves first.
- Orchestrator/SDK single entry point (rule 3); CLI `peer --role {police,thief}`.
- Deadline tracking, watchdog, timeout ⇒ technical loss 0/0 (rules 6–7; D4/D5).
- Two config dirs `config/police/` + `config/thief/`; shared `game.json` vs private `game.toml`
  split (reference_map §6); Zero-Trust: no shared live state (rules 1–2).

## Out of scope
Scent/hints (PRD-4 — TurnMessage ships with placeholder hint + empty smell grid here), real
brains (PRD-3), crypto content of `commit` (PRD-6 — field carried opaquely), tunneling (PRD-5),
Gmail/UI (PRD-7).

## Functional requirements
- **FR-2.1 Symmetric peers.** Each process runs its own FastMCP HTTP server (default ports:
  thief 8801, police 8802, path `/mcp`) and a client to the opponent URL from private config;
  no referee, no strong side (brief §2 rule 1).
- **FR-2.2 Wire fidelity.** Tool names, argument keys, envelope fields, and required-field
  validation exactly per reference_map §3.2–3.4; `from_dict` hard-fails on missing required
  TurnMessage fields; ControlMessage drops unknown keys.
- **FR-2.3 Negotiation.** Signed agreement `{terms, nonce, signature, identity}`; `verify_peer`
  requires exact terms equality (types included) then signature re-check; mismatch = refuse to
  play (rule 11). REQUIRED_TERMS fail-fast, no code defaults (reference_map §2.3).
- **FR-2.4 game_uid.** `UUID(sha256(canonical_json(terms) + "|" + gid1 + "|" + gid2)[:16])`,
  gids sorted — byte-identical to the reference (D1; landmine #3).
- **FR-2.5 Guarded FSM.** Internal game/turn states driven by an explicit transition table
  (architecture.md §4); illegal transitions rejected and logged (rules 4–5; reference gap #16);
  states projected onto the reference's 7 wire status labels
  (WAITING/THINKING/PLAYING/PAUSED/STOPPED/GAME_OVER/QUIT) for control-channel compatibility.
- **FR-2.6 Deadlines + watchdog.** Per-turn deadline from config (`response_timeout` 30s,
  Table 19); watchdog with 60s freeze threshold monitors the loop and the opponent, triggers
  controlled log extraction on crash (rules 6–7). **Timeout result = technical loss 0/0** for the
  frozen side and the audit still runs (D4; reference gaps #5, #17).
- **FR-2.7 Orchestrator.** `SimulationSdk`-style facade is the only entry to transport, runtime,
  config, and (later) LLM/report; CLI + tests go through it (rule 3). Transport injectable so CI
  runs both peers in-process with a fake (course gate: no network in tests).
- **FR-2.8 Series scaffold.** `num_games` from shared config (book fixes 6, Table 18); role
  alternation odd=natural; fresh runtime + full re-negotiation per sub-game (reference_map §2.4).
- **FR-2.9 Dual-run.** `uv run python -m <pkg> peer --role police` / `--role thief` in two
  terminals plays a full localhost sub-game with stub moves.

## Acceptance criteria (testable)
1. **Runs end-to-end:** two OS processes on localhost negotiate, alternate turns to a terminal
   result, and both exit cleanly with per-step JSON logs.
2. In-process integration test (injected fake transport): full series of 6 sub-games with role
   alternation, zero sockets, deterministic seed.
3. FSM test: every undeclared transition raises; fuzzing random status sequences never corrupts
   state.
4. Timeout test: silent opponent ⇒ our peer records technical loss 0/0 (both sides), watchdog
   extracts the log; killed-process test leaves a recoverable log on disk.
5. Wire test: recorded tool calls match reference_map §3 field-for-field (golden JSON fixtures),
   including the `payload` key oddity on `submit_audit`.
6. Zero-Trust check: no module holds state for both roles; process list shows two PIDs.
7. Gates: ≤150 lines/file, ruff, coverage ≥85%, no hardcoded ports/URLs/timeouts.

## Dependencies
PRD-1 (domain core is the physics both peers enforce).

## Risks
- Duplicate deliveries (sender retries, no dedup in reference receivers) desync the implicit turn
  token → we add idempotent handling on OUR receive path (step-number dedup) without changing the
  wire (contract-is-a-floor, book p.34).
- Private `turn_timeout` silently overriding agreed 30/60s (reference gap: `_translate_shared`
  subset) → our config manager wires ALL shared fields to runtime and validates `schema_version`.
