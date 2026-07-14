<!-- ROLE BANNER — prepended to the academic README in the nis-yar1-cop deliverable repo -->
# nis-yar1 · COP peer (Police)

**Group nis-yar1** (Nissim Deri, Yarden Tziar) · Orchestration of AI Agents, Dr. Yoram Segal, University of Haifa · Book v3.0.0

This repository is the **police (cop) peer** of our distributed P2P Cops-and-Robbers league agent.
Its sibling — the thief peer — lives at **[nis-yar1-thief](https://github.com/NisoDeri/nis-yar1-thief)**.

Per the Zero-Trust rule (ruling A4) the two peers share an **identical engine/SDK** but run as
**separate OS processes with separate config dirs and no shared live state**. This repo defaults to
the police role:

```bash
uv sync
# Windows PowerShell:  $env:PYTHONPATH="src"
uv run python -m pursuit peer --role police          # this peer
uv run python -m pursuit peer --role police --gui    # live belief-heatmap window
uv run python -m pursuit peer --role police --fake-opponent   # self-contained demo
```

The full academic report — architecture, the graded belief/brain core, league interop, creativity
edges, and the honest evaluation — follows below.

---

# Pursuit — a P2P Cops & Robbers agent (group `nis-yar1`)

**Course:** Orchestration of AI Agents · Dr. Yoram Segal · University of Haifa
**Group:** `nis-yar1` — Nissim Deri, Yarden Tziar
**Rule-book:** v3.0.0 (+ Appendix E/F) · **Release:** `v1.0.0` (`src/pursuit/shared/version.py`)
**Deliverable repos:** `nis-yar1-cop` (police brain) · `nis-yar1-thief` (thief brain) — one shared engine, role-trimmed strategy.

---

## Abstract

Two independent programs play the pursuit game *Cops & Robbers* on a 7×7 grid over a peer-to-peer
MCP wire — **there is no referee**. Each peer moves under partial observation (it never sees the
opponent's cell; it infers position from a decaying "scent" trail and free-text hints that *may
lie*), seals every move behind a SHA-256 commit, and audits the opponent's revealed log after the
game. We frame the problem as a **decentralized POMDP (Dec-POMDP)** and put the intelligence where
the grade lives: a recursive Bayesian **belief filter (BeliefV2)** that inverts the emission model
to decode position, treats missing scent as evidence, and — the mechanic the course reference
simulator lacks entirely — **detects lies** by scoring each verbal hint against the unfakeable scent
with a learned reliability coefficient. Moves are **pure Python** (BFS true-distance + exact pursuit
value-iteration); a local Ollama model touches only banter and hint interpretation, with a
guaranteed 0-token template fallback. Against the reference greedy baseline our brains win
**0.975–0.98** of games (p < 1e-21); mirror matches sit at 0.50 (balanced). A real two-process
localhost series completed with **all audits passing on both peers**.

---

## 1. The game and its Dec-POMDP framing

A **thief** tries to survive `max_steps` (35) valid moves; a **police** tries to capture it
(step onto its cell, wall it in, or drop a barrier on it). The thief moves first each round;
possession of the last `receive_turn` message *is* the turn token. Neither peer observes the other's
position. Each turn a peer emits (a) a **scent grid** — a 5×5 decaying fingerprint of its own recent
trail, broadcast whole, position never in the clear — (b) a ≤15-word **hint** in natural language
that is allowed to be false, and (c) a **commit** (SHA-256 of the sealed move). Barriers and capture
answers are, by rule, always truthful.

Formally a Dec-POMDP `⟨I, S, {A_i}, T, Ω, O, R⟩` (developed in `docs/RESEARCH-REPORT.md`):
state `S` = both positions, barrier set, step counters; each agent's action `A_i` = 4 moves + STAY +
5 barrier placements; the observation `O` = the opponent's scent snapshot + hint + declared barrier;
transitions `T` are deterministic given both moves. Because scent is *broadcast, not sensed*, there
is no "move closer to see better" — information gathering means **constraining where the opponent can
be**, which is exactly what the belief filter and the barrier doctrine do.

---

## 2. Architecture

Layered, dependency-inward. Pure game logic (`domain`) imports nothing from I/O layers; the network,
LLM and file I/O live only at the edges. One line per package:

- **`domain`** — pure rules: board/BFS, move & capture adjudication, scoring, scent dialects, the
  BeliefV2 filter, crypto (canonical JSON, commit-reveal dialects, Ed25519), `game_uid` derivation.
- **`peer`** — the turn FSM, sealed-log commit/reveal, handshake, deadline tracking, watchdog, and
  the runtime that drives one OS process through a full series.
- **`infra`** — FastMCP server + transport client, the 3-gate Gatekeeper, Gmail sender, Ollama client.
- **`strategy`** — the graded brains (`InterceptorPoliceBrain`, `SurvivorThiefBrain`), the greedy
  reference baseline, and the trash-talk / hint-interpretation layer.
- **`sdk`** — the single orchestrator entry (`run_peer` / `run_lab` / `run_lab_versus`) all callers use.
- **`lab`** — in-process self-play arena + paired-seed statistics (the evidence machine, no network).
- **`interface`** — argparse CLI, Tkinter live window (belief heatmap) and replay verifier viewer.
- **`report`** — the four JSON artifacts (declaration/config/log/result) and their schemas.
- **`shared`** — config loading/validation, machine-spec probe, and release constants (`version.py`).

```
                    ┌──────────────────────── interface (CLI · Tk GUI · replay) ─┐
                    │                                                            │
                    ▼                                                            ▼
   ┌─────────────────────────── sdk (orchestrator: run_peer / run_lab) ─────────────────────┐
   │                                        │                                               │
   ▼                                        ▼                                               ▼
 peer  ── FSM · sealing · handshake ──►  strategy  ── brains + talk ──►  report (4 artifacts)
   │        watchdog · deadlines           │  (moves = pure Python)          │
   │                                       ▼                                 │
   │                               domain (PURE: board·rules·scoring         │
   │                               ·scent·BeliefV2·crypto·game_ids)          │
   ▼                                                                         ▼
 infra ── FastMCP server/transport · Gatekeeper (3 gates) · Ollama · Gmail ──┘
   │
   └──►  the opponent's FastMCP server   (no central referee — two peers only)
```

---

## 3. The graded core (belief + brains)

BeliefV2 (`domain/belief/`) is a **drop-in** for the reference `BeliefGrid` call surface, so the
turn handler's update order is untouched, but its internals are a full recursive Bayes filter run in
four steps every opponent turn — **predict → observe → fuse → mask** (equations in the research
report):

- **Emission-profile inversion** (`likelihood.py`). Instead of the reference's crude
  `P *= (1 + trust·τ)` bump that smears the posterior along the whole trail, we *predict the snapshot
  the locked scent law would produce for each candidate cell* and score the residual against the wire.
  Under the reference scent dialect this collapses the posterior onto the true cell (argmax = position
  at exactly 0.800 — proof in `docs/RESEARCH-REPORT.md`).
- **Role-conditioned motion kernel** (`kernel.py`). The predict step diffuses belief through the
  opponent's *policy* (thief flees, cop chases — softmax over BFS-distance change), not the reference's
  uniform/king blur, so mass moves where an adversary actually goes. `η → 0` recovers the reference
  kernel for ablations.
- **Zero-scent as negative evidence** (`likelihood.py`). A candidate whose predicted fresh 5×5 stamp
  lands where the wire reads `0.000` is annihilated (weight `λ_zero ≥ 1`). This runs the brief's
  lie-detection arithmetic — *expected ≈ 0.81 vs measured 0.00* — for **every cell every turn**, not
  only when a hint prompts it.
- **Reliability-coefficient lie detection** (`reliability.py`) — *the flagship mechanic the reference
  simulator has no equivalent of.* Each opponent keeps a Beta ledger `(α, β)`; the reliability
  `r = α/(α+β)` rises when the peer's words agree with its unfakeable scent and collapses when they
  contradict it. Hints fuse as a reliability-weighted mixture `L_h = r·g_h + (1−r)·q`, so a caught
  liar's hints degrade to noise (or, optionally, to *inverted* evidence). Because scent is emitted by
  movement and cannot be suppressed, the ledger cannot be gamed verbally.

The **police brain** replaces greedy argmax-chasing with an exact pursuit solve `T*` (49×49×2 states,
value-iterated in milliseconds) and picks the move minimizing *expected capture time over the belief*;
its 14-barrier budget is spent by a value test (`ΔT* > 1 tempo`) and a cage planner — never the
reference's self-walling 15% coin flip. The **thief brain** maximizes a composite of `T*`-safety,
k-step mobility (never get jailed), scent-leak minimization, and jail-risk, dropping to exact
alternating minimax in the endgame. Both preserve the reference `_pick_move`/`_decide_move` seam and
take an **injected `random.Random`** for reproducibility.

---

## 4. Creativity edges (E1–E7)

Every edge stays inside the book and the league conformance kit; full justification in
`planning/CREATIVITY-DESIGN.md`.

| # | Edge | Why it wins |
|---|------|-------------|
| **E1** | Reliability-coefficient lie detection | the single biggest capability gap vs the reference (it has none); a scored integrity/adaptation axis |
| **E2** | LLM opponent-profiling across sub-games | profiles the opponent's *words* between games (no deadline) to seed the next trust prior; 0 mandatory tokens |
| **E3** | Active scent-decoy routing (thief) | shapes the uncontrollable scent into a weapon — pins the cop's argmax on an empty cell |
| **E4** | Barrier-cage doctrine (police) | value-tested finisher/tempo/quadrant walls replace the reference's self-walling coin flip |
| **E5** | Computational-fairness bonus | moves are pure Python; LLM optional with a 0-token fallback; a modest laptop declared honestly |
| **E6** | Step-0 asymmetric rule-delta negotiation | ships the *capability* to trade book-legal, crypto-locked term deltas; default terms stay conservative |
| **E7** | Academic-freedom, documented | where the release contradicts itself we pick the interop-sound reading and justify it (see §5) |

---

## 5. League interoperability

We wrote our own engine but treat the professor's reference simulator as the **de-facto wire
standard**: same four MCP tools (`negotiate` / `receive_turn` / `submit_audit` / `receive_control`),
same envelopes, same artifact schemas, same `game_uid` derivation (`planning/INTEROP.md` is the
standalone contract). Two book↔reference splits (commit-hash construction, scent law) are implemented
as **negotiable dialects** locked pre-series (rule 23).

- **Reference-dialect default (E7).** The release publishes three commit constructions; we default to
  the reference/pipe-appended form — the conformance-kit CORE, the one most opponents run, and the only
  published form that also binds the full record — because a hash mismatch scores **0/0 for both
  peers** and day-one interop is what the grade counts. The book dialect stays implemented and
  negotiable. This is an academic-freedom choice, stated and reasoned, not an accident.
- **Conformance-kit byte-exactness.** Against the CORE vectors of the league protocol kit
  (`Imreec/copthief-league-protocol`) our commit-reveal, `terms_signature`, `game_uid` and pheromone
  emit **reproduce byte-for-byte** (`tests/unit/test_conformance_kit.py`).
- **`ensure_ascii=False`.** Canonical JSON hashes non-ASCII (Hebrew) hints as raw UTF-8, so a peer
  using Python's default escaping would mismatch — we pin the raw-bytes form everywhere hashes are taken.

---

## 6. Evidence (honest numbers)

Agent-vs-agent in the in-process lab (BeliefV2 both sides), our brains vs the reference greedy
baseline, role-alternating paired seeds:

| Matchup | Games | Win rate (ours) | Points (ours–theirs) | Significance |
|---|---|---|---|---|
| InterceptorPolice + SurvivorThief **vs** reference greedy | 80–200 | **0.975 – 0.98** | ~1190 – 430 … ~2980 – 1060 | one-sided binomial **p < 1e-21** |
| **Mirror** (ours vs ours) | — | **0.50** | balanced | sanity: symmetric, non-degenerate |

**Real two-process MCP game (localhost, verified):** a full 6-sub-game series, thief-first, with
**all audits passing on both peers** — the commit-reveal chain re-verifies end to end and both
`result_*.json` files' `mutual_agreement.sha256` are byte-identical. The mirror-match 0.50 confirms
neither brain is winning on a coding artifact; the reference-baseline gap is the strategy edge.

---

## 7. Security & integrity

- **Commit-reveal.** Every move is sealed as `SHA-256(commit)` on the wire; the nonce is withheld
  until the end-of-game audit, so true position/move/intent are never in the clear during play.
- **Ed25519-signed declaration.** No staff key exists, so the team generates its own keypair; public
  keys are exchanged and locked into the signed pre-game declaration (and the step-0 hardware record),
  fixing the spec record so it cannot be altered mid-series. The counted-games count lives *inside*
  the signed declaration (rule 37).
- **Mutual post-game audit.** Each peer recomputes the opponent's every commit from the revealed
  payload+nonce; a tamper is detected locally (never trust the opponent's server to validate).
- **`technical_loss` 0/0.** Timeout, crash, or audit-caught forgery ⇒ result string `technical_loss`
  with scores **0/0** (overriding the reference's waiting-peer-wins); the audit still runs and the
  result is still emailed. Both groups must report a caught forgery or risk disqualification.

---

## 8. How to run

Prereqs: Python ≥ 3.11 and [`uv`](https://docs.astral.sh/uv/). The package is run from source
(`PYTHONPATH=src`) — a Hebrew path on the dev box breaks editable installs on Windows.

```bash
uv sync                                   # install deps into .venv
export PYTHONPATH=src                      # PowerShell: $env:PYTHONPATH = 'src'
```

**Self-contained peer demo** (in-process greedy opponent, no network, no LLM):

```bash
uv run python -m pursuit peer --role thief --fake-opponent
```

**Two real OS processes** (police + thief over localhost MCP) — one terminal each:

```bash
uv run python -m pursuit peer --role police --config-dir config/police
uv run python -m pursuit peer --role thief  --config-dir config/thief
```

**Simulation lab** — self-play, then agent-vs-agent (both `-b` brains ⇒ versus series):

```bash
uv run python -m pursuit lab --games 200 --seed 1 \
  --police 'pursuit.strategy.police:InterceptorPoliceBrain' \
  --thief  'pursuit.strategy.thief:SurvivorThiefBrain'
uv run python -m pursuit lab --games 200 --seed 1 \
  --police 'pursuit.strategy.police:InterceptorPoliceBrain' \
  --thief  'pursuit.strategy.thief:SurvivorThiefBrain' \
  --police-b 'pursuit.strategy.greedy:GreedyPoliceBrain' \
  --thief-b  'pursuit.strategy.greedy:GreedyThiefBrain'
```

**Replay a sealed log** (headless verify, `--no-gui` for verdict only) and **live GUI peer**:

```bash
uv run python -m pursuit replay 'logs/nis-yar1/log_<game_id>_g01.json' --no-gui
uv run python -m pursuit peer --role police --gui
```

All wiring (ports, opponent URL, terms) comes from `config/<role>/` — there are no port/URL flags.

---

## 9. Testing & quality

- **795 tests passing, 1 skipped** (needs a live Ollama), **coverage 93.97%** (gate ≥ 85%).
- **ruff clean** across `E,F,W,I,N,UP,B,C4,SIM`; **every source file ≤ 150 lines** (`scripts/check_line_budget.py`).
- **Advisory hardcoding scan:** `python tools/check_no_hardcoded.py` flags suspect Appendix-F literals
  outside config (advisory, always exits 0).
- **CI** (`.github/workflows/ci.yml`) runs ruff + the full suite on every push.

```bash
uv run pytest -q                          # full suite with coverage gate
uv run ruff check src tests
uv run python tools/check_no_hardcoded.py
```

---

## 10. Screenshots

Add before submission (captions describe what each must show):

- `docs/img/live_heatmap.png` — the Tk live window mid-game: the belief heatmap over the 7×7 board
  showing **local truth only** (own position + barriers + posterior mass), never the opponent's cell.
- `docs/img/replay_verified_ok.png` — the replay verifier over a real `log_*.json` with every step
  marked **`[verified OK]`** and the audit summary `passed: true, failed_steps: []`.

---

## 11. Quality note (ISO/IEC 25010)

Mapped to the product-quality model: **Functional suitability** — 795 tests pin rules, crypto and wire
vectors byte-exact. **Reliability** — watchdog + deadline tracking + `technical_loss` 0/0 make a
crash a defined outcome, not a hang. **Security** — commit-reveal, Ed25519 signing and mutual audit
(Zero-Trust: two OS processes, no shared state). **Interoperability** — conformance-kit byte-exactness
and negotiable dialects. **Maintainability** — layered dependency-inward design, ≤150-line modules,
ruff-clean, config-driven (zero hardcoded game values). **Performance efficiency** — moves are milli-
second pure-Python value iteration; a full series runs at 0 LLM tokens.

---

## Documentation map

`CONTRIBUTING.md` (development lifecycle & gates) · `docs/ARCHITECTURE.md` (C4 + FSM/sequence UML) ·
`docs/RESEARCH-REPORT.md` (Dec-POMDP formalization + belief math + lab methodology) ·
`docs/PROMPTS.md` (prompt log) · `planning/` (DECISIONS, STRATEGY, INTEROP, CREATIVITY-DESIGN).

*License: MIT (see `LICENSE`). Wire protocol interoperates with the course reference simulator
(`github.com/rmisegal/Game-P2P-Cop-Chase`) — studied, not copied; schemas reimplemented.*
