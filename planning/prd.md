# Master PRD — Distributed Cops-and-Robbers over a P2P Network

Group **nis-yar1** · Deadline 2026-08-12 · Sources: `FINAL_PROJECT_BRIEF.md` (book v3.0.0,
Appendix E/F binding), `planning/reference_map.md` (wire protocol), `planning/DECISIONS.md`
(D1–D13, all binding on this PRD). Stage detail lives in `planning/prd/PRD-1…7`.

---

## 1. Product

**Two deliverable agent repositories** — `nis-yar1-cop` and `nis-yar1-thief` (D2) — each a
complete, self-contained autonomous peer that plays a **refereeless P2P pursuit league** over
FastMCP/HTTP. One engine, developed in this workshop repo on feature branches, populated into the
two repos with role-trimmed strategy; Zero-Trust at runtime (two OS processes, `config/police/`
vs `config/thief/`, no shared live state — brief §2 rules 1–2). Physics is enforced locally by
each peer from a byte-identical, cryptographically-locked shared config; integrity comes from
SHA-256 Commit-Reveal + mutual audit, not authority.

## 2. Personas

| Persona | Needs from the product |
|---|---|
| **Us (nis-yar1)** — developers & league operators | A lab-tested brain we can trust in counted games; one-command peer launch (`uv run … peer --role X`); dialect switches to match any partner (D3); zero-token default so a series costs nothing (D8); clean docs trail for the 5th criterion (D11). |
| **Opponent groups** — peers on the wire | Exact reference interop: 4 MCP tools (`negotiate`/`receive_turn`/`submit_audit`/`receive_control`), reference envelopes and hash contracts (reference_map §3), out-of-band negotiation checklist (D13) that pins dialects, coordinates, starts, and counting before the series. |
| **Lecturer's grader agent (Dr. Segal)** — consumes email + repos | Signed result JSON as an attachment to `rmisegal+uoh26finalgame@gmail.com` (never free text, rule 33); two accessible cross-linked repos with academic README (Dec-POMDP, MCP dilemmas, strategies, screenshots — brief §13); replay app proving "Verified OK"; Step-0 declarations enabling the computational-fairness normalization. |

## 3. Functional requirements — grouped by the book's success metrics (brief §2)

### Coordination (turn management, P2P protocol)
- **FR-C1** Each peer is simultaneously a FastMCP HTTP server and a client of the opponent's URL; fully symmetric, no referee (brief §0; reference wire §3).
- **FR-C2** Signed-terms negotiation with exact dict equality of shared terms; mismatch = refuse to play (reference_map §3.1; rule 11).
- **FR-C3** Guarded turn/game state machine that rejects every illegal transition (rules 4–5); deadline tracking on every wait (rule 6); timeout ⇒ technical loss 0/0 with the audit still run (D4).
- **FR-C4** Six sub-games per series with role alternation; fresh runtime + re-negotiation per sub-game (Table 18; reference_map §2.4).

### Adaptation (belief under uncertainty via scent)
- **FR-A1** Scent emission/decay per the locked formula; both dialects (book multiplicative-additive / reference subtractive-max-merge) selectable and hash-locked pre-series (Table 16; rule 23; D3).
- **FR-A2** Belief v2: emission-profile inversion, zero-scent-as-evidence, adversarial motion-model diffusion, barrier masking, **hint fusion with a named reliability coefficient** (book p.63; D6).
- **FR-A3** All-Python move policies behind the `[strategy]` seam (`BrainBase`, `_pick_move`/`_decide_move` — Table 22): trapping cop (BFS interception + barrier cages), evasive thief (mobility maximization + planned deception) (D6).
- **FR-A4** Simulation lab: headless in-process self-play harness producing win-rate tables and heatmaps backing every strategy claim (D7).

### Integrity (anti-cheat via hashing)
- **FR-I1** Commit-Reveal on every step with fresh `secrets` nonce, secret until final audit (rules 17–18); **both hash dialects** (nonce-outside-pipe reference / nonce-inside-JSON book) config-selected (D3).
- **FR-I2** End-of-game mutual audit; any mismatch ⇒ tamper forfeit 0 for the cheater (rule 19); truthful capture response and barrier declarations (rules 14–15, 21, 46).
- **FR-I3** Step-0 signed hardware declaration incl. `github_commit`, LLM model, group, sub-game number; token metering locked (rules 24, 53).
- **FR-I4** Replay verifier that re-checks the full commit chain from a log and displays a prominent "Verified OK" (rule 20; mandatory screenshot).

### Architecture (Gatekeeper, Orchestrator, fail-safe code)
- **FR-R1** Single Orchestrator/SDK entry point to all subsystems (rule 3); watchdog with 60s freeze threshold + controlled log extraction on crash (rule 7).
- **FR-R2** 3-gate Gatekeeper — daily quota, token-bucket, DOS circuit-breaker — in front of Gmail and the LLM; 429 backoff (rules 28–29; Table 19; D5).
- **FR-R3** Live UI shows local truth only, never the objective board (rules 8–9); belief heatmap rendered (mandatory screenshot).
- **FR-R4** Public exposure via a stable-hostname tunnel — provider decided at Stage 5 per D5 (fresh ngrok account with reserved domains, or free named Cloudflare tunnel; the old paid ngrok account was deleted) — with preflight checks (rule 10; D5).
- **FR-R5** LLM strictly at the verbal edge (trash-talk + incoming-hint interpretation) on local Ollama, template fallback, zero-token full series possible (rules 25–27; Table 21; D8).

### Reporting & league (cross-cutting, serves Integrity + Architecture)
- **FR-L1** Four JSON artifacts per game (declaration/config/log/result), reference schema 1.1, with real `github_commit`, all 4 repo links, real token totals both sides, symmetric mutual-agreement SHA (Table 20; D9).
- **FR-L2** Autonomous Gmail OAuth **send-only** report of the result JSON as attachment to `rmisegal+uoh26finalgame@gmail.com`; both groups send separately (rules 30, 32–35, 49, 52).
- **FR-L3** League bookkeeping: truthful counted-game declaration, one counted game per opponent, ≤10 counted, diversity tracking (Table 18; D13).

## 4. Non-functional requirements (course hard gates — all pass/fail)

Every src `.py` file ≤150 lines · ruff clean (E,F,W,I,N,UP,B,C4,SIM) · pytest ≥85% coverage with
**injected fakes only** (no network/model in CI) · zero hardcoded parameters — everything from
config, per-game files `config_<game_id>_g<NN>.json` (Appendix F config rules) · `uv`-managed ·
CI on every push · feature-branch-per-capability + granular conventional commits (Appendix C) ·
docs lifecycle initial→PRD→plan→TODO→verify→execute→push · no secrets ever committed
(rules 39–40) · LLM only at the edges, deterministic engine (D8) · self-score covers code
quality only (rule 55). (D11.)

## 5. Decomposition — 7 stages (book Ch10; one PRD each, `planning/prd/PRD-N-*.md`)

1. **Base logic** — 7×7 board, orthogonal+STAY moves, 5-option barriers, all 3 capture rules, scoring; single process, no networking, no AI.
2. **FastMCP P2P infra** — two processes, 4-tool servers/clients, negotiation, turn loop, FSM, watchdog; localhost, numeric geometry.
3. **Blind strategy** — brain seam + full-information heuristic cop/thief brains; simulation lab v0.
4. **Language + scent + belief + LLM** — dual-dialect scent, belief v2 with reliability coefficient, Ollama verbal layer, deception.
5. **Cloud + tunnel** — ngrok reserved domains, remote-machine play, latency/disconnect resilience.
6. **Security + crypto** — dual-dialect Commit-Reveal, nonces, mutual audit, tamper forfeit, Step-0 declaration.
7. **Reporting + UI** — Gmail OAuth send, 3-gate Gatekeeper, 4 artifacts, live GUI, replay verifier, web-replay extension.

## 6. Acceptance — submission checklist (Appendix C, Table 6) + league gate

- [ ] Two accessible repos (public or shared with `rmisegal@gmail.com`)
- [ ] Cross-linked READMEs + two links in Moodle (+ 4 links in result JSON)
- [ ] Annotated tag `v1.0-submission` pushed in both repos
- [ ] README components complete in both repos: Dec-POMDP, FastMCP dilemmas, strategies, learning curves (if RL), screenshots, companion link
- [ ] Belief-map (live GUI) screenshot
- [ ] Replay app "Verified OK" screenshot
- [ ] **≥2 counted games vs different groups played and reported**
- [ ] Both sides emailed separate, matching result JSON per counted game
- [ ] No secrets committed (`.gitignore` verified: `credentials.json`, `token.json`, keys)
- [ ] Moodle form PDF per member + unique 8-char group code; self-score = code quality only

Additionally: all §4 gates green in CI, and each stage PRD's "runs end-to-end" acceptance met in
order (no stage starts before its predecessor's gate passes).
