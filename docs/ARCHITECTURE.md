# Architecture — Pursuit (P2P Cops & Robbers)

C4-style, top-down. Group `nis-yar1`, Orchestration of AI Agents (Dr. Yoram Segal), book v3.0.0.
Companion to `README.md` (§2) and `planning/architecture.md`. Every game value is config-injected;
pure logic (`domain`) is I/O-free.

---

## 1. Context (C4 level 1)

Two independent agent systems play each other directly. **There is no referee** — enforcement
(physics, crypto, schema) is done locally by each peer; the opponent's server is never trusted to
validate anything. The only external systems are the opponent's MCP endpoint and (optionally) Gmail
for the mandatory result email and local Ollama for banter.

```
        ┌──────────────────────┐         MCP over FastMCP HTTP        ┌──────────────────────┐
        │   nis-yar1 peer      │  ◄───────  (4 tools, no referee)  ──►  │   opponent peer      │
        │  (police OR thief)   │     negotiate / receive_turn /        │  (reference-derived  │
        │                      │     submit_audit / receive_control    │   or another group)  │
        └───────┬──────────────┘                                       └──────────────────────┘
                │ send-only                        local, optional (0-token fallback)
                ▼                                             │
        ┌──────────────┐                             ┌────────▼────────┐
        │  Gmail API   │  result_*.json attachment   │  Ollama (local) │  banter + hint parse
        └──────────────┘                             └─────────────────┘
```

Trust boundary: everything left of the MCP link is our process; nothing crosses it in the clear
except sealed commits. Zero-Trust — no shared memory or state with the opponent, ever.

---

## 2. Container (C4 level 2)

A counted match is **two OS processes**, one per role, each with its own config dir and its own
FastMCP server. Each process is a `fastmcp.Client` toward the other's server; there is no central
container. The in-process **lab** collapses both peers into one process over a fake transport for
CI-safe self-play (no network, no LLM).

```
 ┌───────────────── OS process A: config/police ─────────────────┐   ┌──────── OS process B ────────┐
 │  FastMCP server  police-thief-police  :8802/mcp               │   │  FastMCP server  :8801/mcp   │
 │  ├─ inboxes: agreements · turns · audits · controls (no dedup)│   │  ├─ inboxes …                │
 │  ├─ PeerRuntime  ── FSM · deadlines · watchdog                │◄─►│  ├─ PeerRuntime …            │
 │  ├─ strategy: InterceptorPoliceBrain (moves = pure Python)    │   │  ├─ strategy: SurvivorThief  │
 │  ├─ Gatekeeper (quota → token-bucket → circuit-breaker)       │   │  ├─ Gatekeeper …             │
 │  └─ report: declaration/config/log/result JSON → logs/nis-yar1│   │  └─ report …                 │
 └───────────────────────────────────────────────────────────────┘   └──────────────────────────────┘
```

Every outbound call retries every 1.0 s until a per-tool deadline (60 s for turns, 10 s audit, 2 s
control); retries mean duplicate deliveries are possible and the runtime is idempotent to them.

---

## 3. Component (C4 level 3) — pursuit packages

```
 sdk (orchestrator) ─────────────────────────────────────────────────────────────────
   run_peer · run_lab · run_lab_versus         the ONE entry every caller uses
      │
      ├── peer ──────────────────────────────────────────────────────────────────────
      │     runtime · fsm · handshake · turn_handler · turn_sender · sealing
      │     agreement · inboxes · deadlines · watchdog · audit
      │
      ├── strategy ──────────────────────────────────────────────────────────────────
      │     base · police (InterceptorPolice) · thief (SurvivorThief) · greedy (baseline)
      │     talk · ollama_talk · resolve            (moves NEVER call the LLM)
      │
      ├── domain  (PURE, no I/O) ────────────────────────────────────────────────────
      │     board · rules · scoring · own_state · negotiation · protocol · protocol_audit
      │     game_ids           scent/ {base · reference · book · params}
      │     crypto/ {canonical · dialects · signing}
      │     belief/ {engine(BeliefV2) · likelihood · kernel · reliability}
      │
      ├── infra ─────────────────────────────────────────────────────────────────────
      │     mcp_server · transport · gatekeeper · ollama · email
      │
      ├── report ── artifacts · schema        (declaration/config/log/result, schema 1.1)
      ├── lab ────── arena · runner · stats · protocol       (in-process evidence machine)
      ├── interface ─ cli · cli_replay · live_view/live_game/board_view/window · replay_*
      └── shared ─── config · sysinfo · version
```

Dependency rule: arrows point inward toward `domain`; `domain` imports no I/O package. `interface`
imports only `sdk` at top level (GUI/replay helpers are lazy) so the CLI stays a thin shell.

---

## 4. Turn FSM (text UML)

The per-turn state machine; illegal transitions are rejected (not silently ignored). One MOVE/BARRIER/
HOLD advances the sender's step counter; possession of the last `receive_turn` is the turn token.

```
        ┌─────────────┐  both agreements verified (terms ==, sig ok)
        │  HANDSHAKE  │ ───────────────────────────────────────────┐
        └─────────────┘                                            ▼
                                                          ┌──────────────────┐
   turn deadline / watchdog freeze  ┌────────────────────►│   AWAIT_TURN     │  (thief: skipped on move 1)
   ─► technical_loss 0/0            │                      └───────┬──────────┘
        ▲                           │            receive_turn (token acquired)
        │                           │                              ▼
  ┌─────┴──────┐   illegal move  ┌──┴───────────┐  belief updated  ┌──────────────┐
  │  TIMEOUT   │◄────────────────│   DECIDE     │◄─────────────────│   OBSERVE    │
  └────────────┘  reject+degrade │ pure-Python  │  predict→observe │ parse msg,   │
                                 │ move + seal  │  →fuse→mask       │ note barrier │
                                 └──────┬───────┘                   └──────────────┘
                                        │ send receive_turn (commit only)
                                        ▼
                              ┌────────────────────┐  capture / survival / opponent win_claim
                              │   CHECK_TERMINAL   │ ─────────────────────────────────────────►┐
                              └─────────┬──────────┘                                            ▼
                                        │ not terminal → AWAIT_TURN                    ┌──────────────┐
                                        └──────────────────────────────────────────►  │  END → AUDIT │
                                                                                       └──────────────┘
```

`END → AUDIT` runs even on timeout/crash (best-effort), then emits the result JSON and emails it.

---

## 5. Sealed-log commit-reveal (sequence UML)

Position/move/intent are never in the clear during play — only the `commit` (SHA-256 of the sealed
payload) rides the wire; nonces are withheld until the single end-of-game reveal, then each peer
re-audits the other's chain.

```
  Peer A (mover)                         wire                          Peer B (waiter)
  ──────────────                       ────────                        ───────────────
   decide move (pure Python)
   seal: nonce ← random16
         commit = SHA256(canon(payload)|nonce)      # reference dialect (default)
   append {payload, nonce, commit} to local log
        │  receive_turn { step, sender, hint, smell_grid, commit, ... }
        │ ─────────────────────────────────────────────────────────►  verify envelope, parse
        │                                                              BeliefV2.update(smell, hint)
        │                                                              decide + seal own move
        │  ◄───────────────────────────────────────────────────────── receive_turn { commit, ... }
       ...                          (repeat each turn)                        ...
   ── game terminal ──
        │  submit_audit { sender, result_claim, records:[{payload,nonce,commit}, …] }   (nonces REVEALED)
        │ ─────────────────────────────────────────────────────────►  for each record:
        │                                                                recompute SHA256(canon(p)|n)
        │  ◄───────────────────────────────────────────────────────── submit_audit { records … }
   for each opponent record:                                          == stored commit ?  → passed
     recompute & compare                                              mismatch/forgery → technical_loss 0/0
   write log_*.json (audit.passed, failed_steps[])                    (both peers still report)
   write + email result_*.json (mutual_agreement.sha256 byte-identical both sides)
```

Two canonical hashers are used deliberately: the **compact** hasher (`separators=(",",":")`,
`ensure_ascii=False`) for per-step commits / `config_sha256` / `game_uid`, and the **spaced** default
hasher for `consensus_signature` fields (declaration signatures, log/result `mutual_agreement.sha256`).
Mixing them silently fails verification — see `planning/INTEROP.md` §3.4.
