# Master PLAN — P2P Cops & Robbers Final Project

Group **nis-yar1** (Nissim Deri, Yarden Tziar) · Dr. Yoram Segal, "Orchestration of AI Agents", Univ. of Haifa
Deadline **2026-08-12 23:59** (Moodle, no late submission). Binding spec: `FINAL_PROJECT_BRIEF.md`
(book v3.0.0 + Appendix F/E). Architecture: `planning/architecture.md`. All decisions per
`planning/DECISIONS.md` (D1–D13). Interop ground truth: `planning/reference_map.md`.

Package working name: **`pursuit/`**. Workshop monorepo: `Orchestration-final-project` (private).
Deliverables: **`nis-yar1-cop`** + **`nis-yar1-thief`** (D2).

---

## 1. Milestones (D12) with per-week exit criteria

Build order follows the book's 7-stage roadmap (brief §14): each stage runs end-to-end before the
next is added, one PRD per stage.

### M1 — Week 1 (Jul 13–19): Stages 1–3 — engine core, localhost P2P, blind brains, lab v0
Covers PRD-1 (Base Logic), PRD-2 (FastMCP infra), PRD-3 (Blind Strategy).

**Exit criteria (all must hold):**
- E1.1 Full local game on a 7×7 board: orthogonal+STAY only (fail-fast on bad `move_set`, no
  king fallback — D4), barrier quota 14 with all **5** placement options (own cell + 4 adjacent),
  **barrier-on-thief = capture**, **jailed thief = capture**, survival at 35, scoring 20/5, 5/10,
  tie 2, technical 0/0 — every value from config (brief §4, §10; D4).
- E1.2 Two OS processes exchange a complete game over localhost FastMCP using the reference's
  exact 4 tools and message envelopes (`reference_map.md` §3); duplicate-message dedup by
  `(sender, step)` in place (landmine #8/#10 mitigation).
- E1.3 Guarded FSM live: every state transition validated against the transition table, illegal
  transitions rejected and logged (rules 4–5; D5) — the reference has none (gap #16).
- E1.4 Blind brains (full information, no scent) play legal games via the `[strategy]` seam with
  the reference's `BrainBase` contract (`_pick_move`/`_decide_move`, `__init__(llm, rng, trash)`).
- E1.5 Simulation lab v0 (D7): both peers in-process via injected transport, N seeded headless
  games, win-rate table emitted.
- E1.6 Gates green: ruff (E,F,W,I,N,UP,B,C4,SIM) clean, pytest ≥85% coverage, every `.py` ≤150
  lines, CI running on every push.

### M2 — Week 2 (Jul 20–26): Stage 4 — scent + belief v2 + hints/LLM + deception
Covers PRD-4 (Language + Scent) — "the big leap" (brief §14.4) and the graded core (D6).

**Exit criteria:**
- E2.1 Both scent dialects implemented and config-selectable (D3): `reference`
  (subtractive decay, max-merge deposit, Chebyshev rings 0.9/0.6/0.3, 3-dp) and `book`
  (τ(t+1)=max(0,(1−ρ)τ+Δτ), additive). Numeric worked example generated + SHA-256-lockable per
  rule 23.
- E2.2 Belief v2: emission-profile inversion, zero-scent-as-evidence, adversarial motion model,
  barrier masking, and **hint fusion with a reliability coefficient** (lie detection — the book's
  flagship mechanic the reference lacks; gap #22, PDF p.63).
- E2.3 Brains v1: cop BFS interception + barrier cages; thief mobility maximization + scent-aware
  routing + planned deception (D6). Lab evidence: brains v1 beat reference-default brains over
  ≥200 seeded games; ablation table saved to `lab/results/`.
- E2.4 Ollama trash-talk + incoming-hint parser wired (qwen2.5:7b, `every_n_steps`, template
  fallback on any error/deadline); a full series completes at **0 tokens** in template mode (D8).
- E2.5 Dialect matrix tests green (§5.3 below). Gates green (E1.6).

### M3 — Week 3 (Jul 27–Aug 2): Stages 5–6 — tunnel, commit-reveal, audit, replay verifier
Covers PRD-5 (Cloud + Tunnel), PRD-6 (Security + Crypto).

**Exit criteria:**
- E3.1 Remote game over a public tunnel (provider per D5 — fresh ngrok reserved domains or free
  named Cloudflare tunnel; the old paid ngrok account was deleted) between our two machines;
  tunnel preflight check in the Orchestrator (rule 10; D5).
- E3.2 Commit-reveal in both hash dialects (D3), nonce secrecy until final audit (rule 18),
  end-game mutual audit; forgery, timeout and crash endings = **`technical_loss` 0/0 with the
  audit still run and reported** (NotebookLM A6/A9a; fixes reference gaps #5, #11–12).
- E3.3 Step-0 signed hardware declaration incl. **real `github_commit`** (`git rev-parse HEAD`)
  and the rule-23 scent-formula lock hash (fixes gaps #13–14).
- E3.4 Watchdog live: 60s freeze threshold, crash-triggered controlled log extraction (rule 7;
  gap #17).
- E3.5 Replay verifier steps a saved log, re-verifies every commit, and shows a prominent
  **"Verified OK"** banner (mandatory screenshot; rule 20).
- E3.6 **Interop smoke passed** vs an UNMODIFIED reference peer on localhost (§5.5).
- E3.7 Deliverable repos `nis-yar1-cop`/`nis-yar1-thief` created and populated (first release
  cut — required now because every counted game must email the commit hash actually played,
  brief §10 config rules + rules 24/53). Gates green.

### M4 — Week 4 (Aug 3–9): Stage 7 — reporting shell + league play
Covers PRD-7 (Reporting + Visualization).

**Exit criteria:**
- E4.1 Gmail OAuth **send-only** sender ported from HW6; result JSON as **attachment** to
  `rmisegal+uoh26finalgame@gmail.com`; secrets .gitignored (rules 30, 32–35, 39–40; D9).
- E4.2 3-gate Gatekeeper (daily quota → token-bucket → DOS/circuit-breaker) in front of Gmail
  AND the LLM path; 429 → honored backoff (D5; fixes gap #19).
- E4.3 All four artifacts byte-compatible with schema 1.1 and **fixed**: real per-sub-game
  `github_commit`, all 4 repo links in the result, real token totals both sides,
  symmetric-subset mutual-agreement SHA (D9; fixes gaps #14–15).
- E4.4 Live GUI (belief heatmap, local truth only — rules 8–9) + web replay dashboard extension
  (D10) done; belief-map screenshot captured.
- E4.5 League: warm-ups with every WhatsApp-pod opponent, then **≥2 counted games vs different
  groups** (target 3 wins for diversity reward — D13); per-game
  `config_<game_id>_g<NN>.json` committed and hash emailed per game.

### M5 — Buffer (Aug 10–12): submission freeze
- E5.1 Both deliverable repos final: README = academic report (Dec-POMDP, MCP dilemmas,
  strategies, both mandatory screenshots, cross-link), `config/`, PRDs, PLAN, TODOs,
  `docs/STRATEGY.md`, `docs/RESEARCH-REPORT-Performance-Analysis.md` (brief §13, §15; rule 50).
- E5.2 Annotated tag `v1.0-submission` pushed on both repos; Appendix C checklist walked item by
  item; Moodle PDF per member + 8-char group code; self-score (code quality only, rule 55 —
  scored modestly and evidence-backed).

---

## 2. Work breakdown → the 7 PRDs

One PRD per stage (brief §14; D11 lifecycle: initial → PRD → plan → TODO → verify → execute →
push). PRD files live in `docs/prd/PRD-<n>-<slug>.md` in the monorepo. Module names refer to
`planning/architecture.md` §2.

| PRD | Stage (brief §14) | Modules built | Key rules/decisions discharged |
|---|---|---|---|
| **PRD-1 Base Logic** | 1 | `domain/board,own_state,rules,scoring,game_ids,constants,exceptions`; `shared/config,shared_terms` | D4 physics (rules 13–16, 46–47); Appendix F tables 13/15/17; config-driven everything |
| **PRD-2 FastMCP Infra** | 2 | `infra/mcp_server,mcp_client`; `domain/protocol,negotiation`; `peer/runtime,fsm,handshake,controls`; `sdk/sdk,series`; `interface/cli` | Rules 1–6 (two processes, Orchestrator entry, guarded FSM, deadlines); wire protocol frozen per reference_map §3; D1, D5 |
| **PRD-3 Blind Strategy** | 3 | `strategy/__init__,base,thief,police,pathing,barriers`; lab v0 (`lab/` harness) | `[strategy]` seam contract (Appendix F table 22); D6 skeleton, D7 |
| **PRD-4 Language + Scent** | 4 | `domain/scent/*` (both dialects), `domain/belief/*` (incl. hint fusion), `strategy/trash_talk,providers,hint_parser,deception` | Rules 23, 25–27 (free NL only, no numeric protocol); Appendix F tables 14/16/21; D3 scent seam, D6, D8 |
| **PRD-5 Cloud + Tunnel** | 5 | `infra/tunnel`; network config surface (public URLs in `game.toml`); remote-play runbook | Rule 10; D5 (ngrok reserved domains) |
| **PRD-6 Security + Crypto** | 6 | `domain/crypto/*` (both dialects), `peer/sealing,step0,audit,watchdog`; replay verifier core (`interface/gui/replay_*`) | Rules 7, 17–24 (commit-reveal, nonce secrecy, audit, replay verifier, step-0, scent lock); D3 hash seam, D4 timeout=0/0 |
| **PRD-7 Reporting + Viz** | 7 | `infra/gmail_sender`; `shared/gatekeeper,gates,config_gen`; `report/*`; `interface/gui/live_*`; web dashboard | Rules 8–9, 28–35, 48–54; Appendix F tables 18–20; D5 gatekeeper, D9, D10 |

Cross-cutting from day 1 (not a PRD): CI, ruff, coverage, 150-line check, conventional commits,
TODO ledger (500–1000 items, D11), `LEAGUE-OPS.md` negotiation checklist (D13, reference_map §10).

---

## 3. Two-repo release strategy (D2)

**Model: workshop monorepo → role-trimmed deliverable repos.**

1. **Workshop monorepo** `Orchestration-final-project` (private): all development, all branches,
   the lab, both brains, planning docs. Never submitted; may stay private forever.
2. **Release cut** (`scripts/release.py`, itself ≤150 lines, config-driven via
   `release_manifest.toml`): copies an allowlist into each deliverable repo working tree —
   - **`nis-yar1-cop`**: full engine (`pursuit/` minus `strategy/thief.py` and thief-only
     deception tuning) + `config/police/` + role-specific README + shared docs (PRDs, PLAN, TODO,
     STRATEGY, RESEARCH-REPORT).
   - **`nis-yar1-thief`**: full engine minus `strategy/police.py`/barrier planner internals +
     `config/thief/` + role-specific README + shared docs.
   - The engine (domain/peer/infra/shared/report/interface) is identical in both — sanctioned by
     the reference being one codebase for both roles (D2; risk LOW, pending NotebookLM confirm).
3. **Gates on the trimmed tree**: the release script re-runs ruff + pytest (role-appropriate test
   subset) + the 150-line check **inside the trimmed tree** before pushing — a trim that breaks
   imports can never ship.
4. **Cross-links**: each README links the companion repo (rule 49); both repos shared with
   `rmisegal@gmail.com` (or public). The **four** links (both groups' cop+thief) go in the result
   JSON; **two** links go in Moodle (brief §13).
5. **Cadence**: first cut end of W3 (E3.7) so every counted league game plays a real, pushed
   commit whose hash goes into step-0 and the result JSON (rules 24/53). Re-cut after any engine
   change between games; the hash is updated per game.
6. **Freeze**: `git tag -a v1.0-submission -m "Final submission: Police-Thief P2P, group nis-yar1"`
   + `git push origin v1.0-submission` on **both** deliverable repos (brief §13). The monorepo
   gets a matching `v1.0-submission-workshop` tag for traceability.
7. **Attribution**: adapted fragments credited in-code per the GTAI EULA posture
   (reference_map "License"; D1) — re-implemented, not forked.

---

## 4. Branch plan (D11; book Appendix C p.133 mandates feature-branch-per-capability)

- **`main`** is always releasable; direct pushes forbidden (branch protection).
- **Naming**: `feat/s<stage>-<capability>` for PRD work (e.g. `feat/s1-board`,
  `feat/s4-belief-hint-fusion`, `feat/s6-commit-reveal`); `fix/<slug>`, `docs/<slug>`,
  `lab/<experiment>`, `release/<repo>-<date>` for release cuts.
- **One capability per branch**, granular conventional commits
  (`feat(domain): jailed-thief capture per rule 47`), no squashing away the story.
- **Merge gates (CI-enforced, all required)**:
  1. `ruff check` clean (E,F,W,I,N,UP,B,C4,SIM);
  2. `pytest` all green, **coverage ≥85%**;
  3. 150-line check: no `src/**/*.py` exceeds 150 lines (custom CI step);
  4. no secrets (gitleaks-style scan; `credentials.json`/`token.json` patterns hard-blocked);
  5. conventional-commit lint on the branch.
- Tests use **injected fakes only** — no network, no model, no Ollama in CI (transport/LLM/email
  are constructor-injected seams, reference_map §4.3).
- Weekly: milestone review against §1 exit criteria; unmet criteria block the next stage
  (book: each stage runs end-to-end before the next, brief §14).

---

## 5. Test strategy

### 5.1 Unit tests (per module)
Every `pursuit/` module gets a sibling test file. Pure-domain modules (board, rules, scoring,
scent, belief, crypto) are property-tested with seeded RNG. Special fixed-value tests assert
Appendix F constants against loaded config (scoring 20/5/5/10/2/0, scent 0.9/0.10/5×5, quota 14,
ceiling 35) so a bad config can never silently mis-score (reference gap #8).

### 5.2 Protocol golden-file tests (vs the reference's sample run)
Fixtures: `reference/Game-P2P-Cop-Chase/docs/sample-run/` — `declaration_…json`,
`config_…_g01.json`, `log_…_g01.json`, `result_…json` (professor-generated ground truth).
Copied into `tests/golden/` with attribution. Assertions:
- our artifact parsers load all four files without loss;
- our `game_uid`, `config_sha256` (compact hasher) and `consensus_signature` (spaced hasher)
  re-derive the values embedded in the goldens byte-identically (reference_map §3.5 — two
  different canonical hashers, replicated exactly per field);
- our reference-dialect `CommitReveal.verify` re-verifies every sealed record in the golden log
  (nonce pipe-appended outside the JSON, `ensure_ascii=False`);
- our emitters, fed the golden inputs, reproduce the symmetric mutual-agreement subset
  byte-identically.

### 5.3 Dialect matrix tests (D3)
Parametrized grid over `{hash: reference, book} × {scent: reference, book}`:
- same-dialect peers: full in-process game verifies clean, audits pass;
- **cross-dialect peers: negotiation must refuse to play** (terms hash mismatch), never a
  mid-game silent corruption;
- scent dialects validated against hand-computed numeric worked examples (the same examples we
  exchange + SHA-lock with partners under rule 23).

### 5.4 Self-play integration tests (D7 harness doubles as CI integration)
Both peers in-process via injected transport (`run_peer(transport=...)`, reference_map §4.3),
template trash-talk (0 tokens), fixed seeds. Asserts: full 6-sub-game series with role
alternation completes; all four artifacts emitted and schema-valid; audit passes; FSM saw zero
illegal transitions; capture rules 46/47 and timeout-0/0 paths each exercised by a scripted brain.

### 5.5 Interop smoke test (NOT in CI — scripted, run at E3.6 and before every league game)
Against an **UNMODIFIED** reference peer (`uv run` inside `reference/Game-P2P-Cop-Chase/`,
`--stub-llm --no-gui`) on localhost, reference dialect, both role assignments:
- negotiation succeeds (terms exact-equal, signature verifies);
- full sub-game completes; their audit of us passes and ours of them passes;
- fixed literals honored ("You got me.", "(silence)", fallback hint; thief moves first;
  `submit_audit` param key `payload` — reference_map §10);
- artifacts from both sides agree on the symmetric result subset.
Known deltas are *expected* and documented (reference lacks capture rules 46/47, timeout
semantics differ): the smoke asserts interop of the wire + crypto, not rule parity; rule deltas
are handled in pre-series negotiation (D13, `LEAGUE-OPS.md`).

### 5.6 Verification artifacts
Each PRD closes with a `docs/verify/VERIFY-<n>.md` (D11 lifecycle "verify") recording commands
run, seeds, outputs, screenshots. Lab results land in `lab/results/` and back every strategy
claim in README/STRATEGY (D7: "every strategy claim artifact-backed").

---

## 6. Risk register (top risks from `reference_map.md` §7/§10 + schedule)

| # | Risk | Impact | Mitigation | Owner |
|---|---|---|---|---|
| R1 | **Hash-dialect mismatch with partner** (nonce-in-JSON book snippet vs reference pipe-append) → cross-audit fails, game voided | Counted game lost | D3 dual dialect, default `book` (nonce-inside-JSON, authoritative per NotebookLM A1 2026-07-13; `reference` only by explicit negotiation); pinned in `LEAGUE-OPS.md` pre-series checklist item 1; dialect matrix tests | Nissim |
| R2 | **Scent-law mismatch** (subtractive/max-merge vs multiplicative/additive) violating rule 23 | Game voided | D3 dual scent impl; exchange formula + numeric worked example + SHA-256 lock before every series | Yarden |
| R3 | **Timeout-semantics dispute** (reference: waiting peer wins + audit skipped; book: 0/0 + audit) | Contradictory reports → both groups 0 (rule 34) | Our engine: 0/0 with audit always run (D4); pinned pre-series; result agreed in mutual log audit before either side emails | Nissim |
| R4 | **Opponent runs unpatched reference** missing capture rules 46/47 and 5-option barriers | Rule disputes mid-game | Pre-series negotiation pins all landmines (reference_map §10 items 5, 10); contract-is-a-floor upgrades agreed in writing | Yarden |
| R5 | **League scheduling** — partners unavailable late; ≥2 counted games is a pass/fail gate | Fail the project | Warm-ups start first days of W4 (D12/D13); 3 pod opponents available; counted only when stable | Both |
| R6 | **Gmail OAuth failure/quota** at reporting time | Missing report → 0 for both groups | Port proven HW6 sender early in W4; 3-gate Gatekeeper; dry-run against our own address before league play | Nissim |
| R7 | **Hygiene regressions late** (150-line, coverage) discovered at submission | Hard-gate loss | CI gates from day 1 (§4); files trending >140 lines split immediately (architecture.md budget headroom) | Yarden |
| R8 | **Tunnel/latency instability** (rule 10; new failure class vs localhost) | Timeout losses | Stable-hostname tunnel per D5 (fresh ngrok reserved domains or free named Cloudflare tunnel — old paid account deleted); preflight check; W3 remote test between our own machines before any league game | Nissim |
| R9 | **Turn-token desync** — no dedup in reference; retries duplicate messages (reference_map §3 retry semantics) | Deadlock/desync → technical loss | Inbox dedup by `(sender, step)`; FSM rejects out-of-order steps; watchdog catches residual freezes | Yarden |
| R10 | **EULA/originality** — grader sees reference code copied | Originality axis loss / EULA breach | D1 hybrid: own re-implementation, wire-compatible; in-code attribution for adapted fragments; goldens used as fixtures with attribution | Both |

---

## 7. Definition of done — per stage

A stage/PRD is DONE only when ALL of:
1. **Exit criteria** for its milestone row in §1 demonstrably met (commands + outputs in
   `docs/verify/VERIFY-<n>.md`).
2. **Merged to `main`** through gated feature branches (§4) — ruff clean, pytest green,
   coverage ≥85%, all files ≤150 lines, no secrets.
3. **End-to-end demo runs** from a clean checkout: `uv sync` + the stage's documented
   `uv run python -m pursuit …` command works on both roles.
4. **Docs current**: PRD status updated, TODO items closed, README sections touched by the stage
   drafted (Dec-POMDP after PRD-1/4; MCP dilemmas after PRD-2/5; strategy after PRD-3/4;
   screenshots after PRD-6/7).
5. **No regression**: full self-play integration suite (§5.4) still green; from M3 on, interop
   smoke (§5.5) re-run if the wire surface was touched.
6. **Config-driven check**: zero new hardcoded parameters (reviewed in PR; constants only in
   `config/` or Appendix-F assertion tables).

Stage-specific additions: PRD-4 adds the lab evidence bar (E2.3); PRD-6 adds the "Verified OK"
screenshot; PRD-7 adds a live Gmail dry-run and one full dress-rehearsal game over ngrok between
our two machines producing all four artifacts + both emails.

---

## Verification

**Consistency-review pass — 2026-07-13.** Ground truth: `FINAL_PROJECT_BRIEF.md`,
`planning/reference_map.md`, `planning/DECISIONS.md` (D1–D13). Scope: every file under
`planning/` incl. `planning/prd/`.

**Checked:**
- D1–D13 conformance across initial/prd/PRD-1…7/plan/architecture/todo/STRATEGY/LEAGUE-OPS/INTEROP
  (dialect strategy D3, two-repo split D2, timeline D12, physics fixes D4) — no contradictions
  remain after the fixes below.
- Appendix F numbers everywhere: 7×7, barriers 14, moves/survival 35, scent 0.9/ρ 0.10/5×5,
  scoring 20/5/5/10/tie 2/technical 0, 6 sub-games, timeouts 30 s/60 s, gatekeeper 30/2/5 s/3/100,
  diversity 10, ≥2/≤10 counted, token budget 200 000, hint cap 15 — all consistent.
- TODO coverage vs PRD FRs spot-checked for stages 1, 4, 6; task-count claim recounted by script
  (`grep -c '^- \[ \]'`): 617 tasks, per-stage counts match the header, stage-1 numbering contiguous.
- Cross-references resolve (brief/reference_map/DECISIONS/architecture paths; sample-run fixtures
  exist under `reference/Game-P2P-Cop-Chase/docs/sample-run/`).
- STRATEGY.md mechanisms use only reference_map-documented APIs (`_pick_move`/`_decide_move`
  signatures, BeliefGrid surface, sealed-record fields, TurnHandler update order, wire literals);
  INTEROP.md dialect hash vectors (A `b578bc30…`, B `93a63ddd…`) and the `game_uid` worked example
  (`7132f6ae-…`) recomputed and reproduced byte-for-byte.

**Fixed in this pass:**
- todo.md T0.2/T2.76: package name `police_thief` → `pursuit` (plan/architecture working name).
- todo.md T2.83/T4.87/T5.22/T6.62/T7.67: PRD doc slugs aligned to the actual `planning/prd/` filenames.
- todo.md T2.74: removed CLI `--port/--opponent-url` overrides (contradicted PRD-5 FR-5.3
  config-only addressing); replaced with a config-only assertion test.
- todo.md T2.33/T2.39 + PRD-2 FR-2.5: FSM restated as the internal guarded state machine of
  architecture.md §4 projected onto the 7 wire labels (was: labels-as-states).
- todo.md stage 1: added T1.89–T1.91 (game-lifecycle FSM per PRD-1 FR-1.8 + barrier-on-thief
  harness game per PRD-1 acceptance 1); tail renumbered; header count 614 → 617 (S1 93 → 96).
- architecture.md: dialect config keys unified to `crypto.dialect` / `pheromones.dialect`
  (matching todo.md and STRATEGY.md).

**Open items (structural, not fixed here):** dialect-ids-in-signed-terms vs the reference's
strict 14-key terms equality (see review report); module-layout naming drift between
todo.md/STRATEGY.md and architecture.md §2 (architecture is canonical at implementation time);
watchdog build stage split between PRD-2 (basic, T2.43) and plan §2/E3.4 (hardened in W3).
