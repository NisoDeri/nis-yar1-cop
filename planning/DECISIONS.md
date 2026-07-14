# Architecture Decision Record — Final Project (P2P Cops & Robbers)

Group **nis-yar1** (Nissim Deri, Yarden Tziar) · Course: Orchestration of AI Agents (Dr. Yoram Segal)
Deadline: **2026-08-12 23:59** (Moodle; no late submission). Book v3.0.0 + Appendix F are binding.
Status: ACCEPTED (2026-07-13). Every planning doc must conform to these decisions.

---

## D1. Build approach: HYBRID (own code, reference-compatible wire)

We write **our own two deliverable repos** (originality axis + EULA safety), but we treat the
professor's reference simulator (`rmisegal/Game-P2P-Cop-Chase`, v3.0.0) as the **de-facto league
interop standard**: same 4 MCP tools (`negotiate` / `receive_turn` / `submit_audit` /
`receive_control`), same message envelopes, same artifact schemas (`schema_version 1.1`), same
`game_uid` derivation. Rationale: most groups will run reference-derived peers; a private protocol
guarantees cross-group failure. We do NOT fork: we re-implement in our own style, fixing the
reference's book deviations (below). Where we adapt a fragment, we attribute in-code.

## D2. Two repos, one engine, Zero-Trust runtime

- Deliverables: **`nis-yar1-cop`** and **`nis-yar1-thief`** (final names confirmed at repo
  creation; cross-linked READMEs; shared with rmisegal@gmail.com or public).
- Development happens in this workshop repo (`Orchestration-final-project`) on **feature
  branches** (book Appendix C mandates branch-per-capability); the two deliverable repos are
  populated from it with **role-trimmed strategy**: cop repo ships only the police brain,
  thief repo only the thief brain. The engine (domain/peer/infra/shared) is identical in both —
  **CONFIRMED legal by NotebookLM A4 (2026-07-13)**: the two repos may share an identical
  engine/SDK package; Zero-Trust requires separate OS processes, separate config dirs and no
  shared memory/live state — not independently-developed code.
- Zero-Trust at **runtime**: two OS processes, two config dirs (`config/police/`,
  `config/thief/`), no shared live state, ever.

## D3. Negotiable-dialect engine (the interop insurance)

Two known dialect splits exist between the book and the reference. We implement **both sides of
each**, selected by the signed shared config and **locked pre-series** (rule 23):

- **Commit hash construction**: `reference` = sha256(canonical_json(payload) + "|" + nonce);
  `book` = sha256(canonical_json({...payload, nonce})). Default: **`book`** — NotebookLM ruling
  A1 (2026-07-13): the book construction (nonce INSIDE the canonical JSON, chapter-5 schema) is
  authoritative for league cross-audits; the reference's pipe-appended form is a "simplified
  sketch". We keep the `reference` dialect implemented for stock-reference partners, selected
  only by explicit negotiation + rule-23 lock.
- **Scent model**: `reference` = subtractive decay + max-merge deposit; `book` =
  τ(t+1)=max(0,(1−ρ)·τ+Δτ) multiplicative + additive. Default: **`book`** — NotebookLM ruling
  A2 (2026-07-13): the book equation is the reference standard; adopting the reference dialect
  is a LEGAL mutually-agreed upgrade if exchanged + cryptographically locked at Step-0 (rule 23).
  Either way, priority = both peers byte-identical: **numeric worked example + SHA-256 lock**
  before every series.

Everything else negotiable (coordinate system, starts, arena, hint cap, minimums) sits in
`game.json` per Appendix F, generated per game as `config_<game_id>_g<NN>.json`.

## D4. Book-compliant physics (fixing the reference's deviations)

Our engine enforces, regardless of dialect: 4-orthogonal + STAY only (no king fallback, fail-fast
on bad `move_set`); barrier placeable on **own cell + 4 adjacent** (5 options); **barrier-on-thief
= capture**; **jailed thief = capture**; timeout/crash = **technical loss 0/0** (never
waiting-peer-wins) with the audit still run and reported; barrier quota 14 (min), move ceiling /
survival 35 (min); scoring 20/5, 5/10, tie 2, technical 0/0 — all from config, nothing hardcoded.

## D5. Architecture rules 1–10 implemented for real

Single **Orchestrator** entry (SDK); explicit **turn state machine** with illegal-transition
rejection; **deadline tracking** on every wait; **watchdog** (60s freeze threshold) with
controlled log extraction on crash; **3-gate Gatekeeper** (daily quota → token-bucket →
DOS/circuit-breaker) in front of Gmail AND the LLM; live UI shows **local truth only**;
**public tunneling** with preflight
checks — provider decided at Stage 5: fresh ngrok account or a free named Cloudflare tunnel
(the old paid ngrok account was deleted; both paths documented in LEAGUE-OPS §2).

## D6. The graded core: belief + brains (all-Python moves)

- **Belief v2**: invert the known 5×5 emission profile into a position likelihood (not the
  reference's crude multiplicative bump); treat **zero-scent as evidence**; adversarial
  **motion-model diffusion** (thief flees / cop chases, not uniform); barrier masking; and the
  book's flagship mechanic the reference lacks entirely — **hint fusion with a reliability
  coefficient**: verbal hints Bayes-combined with weight learned from scent-contradiction
  (lie detection). 
- **Police brain**: BFS true-distance interception (barrier-aware, predicts flight), belief-mass
  herding, and **barrier cages** (funnel + quadrant sealing) replacing the 15% coin flip.
- **Thief brain**: mobility maximization (k-step reachable-cell count — never get jailed),
  scent-aware routing (minimize information leaked to the cop's belief), edge discipline vs
  barrier traps, and **planned deception** (lie when the expected belief-error gain is highest).
- Track per book Ch6 = "your own heuristic algorithm" (belief + scent + barriers + lookahead);
  optional Q-learning add-on only if the simulation lab shows it beats the heuristic (then
  learning curves go in the README).

## D7. Simulation lab (the evidence machine)

A local self-play harness (no network, both peers in-process against the same engine) that runs
hundreds of games: our brains vs reference-default brains, ablations, parameter sweeps. Outputs
win-rate tables + heatmaps for README/STRATEGY claims — every strategy claim artifact-backed.

## D8. LLM policy: Ollama, zero mandatory tokens

Moves never use the LLM. Trash-talk + **incoming-hint interpretation** (classify claim, extract
direction/landmark, feed the reliability coefficient) run on **local Ollama** (qwen2.5:7b
default; aya-expanse:8b fallback), `every_n_steps` throttled, template fallback on any
error/deadline — a full series can always run at 0 tokens. `claude_cli`/API modes stubbed but
off (course rule: Login-not-API-key; no paid keys).

## D9. Reporting + artifacts

Port HW6's **Gmail OAuth send-only** sender (credentials outside repo, .gitignored; send target
`rmisegal+uoh26finalgame@gmail.com`). Emit the four JSON artifacts byte-compatible with the
reference schemas, but **fixed**: real `github_commit` per sub-game, all 4 repo links, real token
totals both sides, mutual-agreement SHA. Step-0 signed hardware declaration (keeps the
computational-fairness bonus; our modest laptop + efficient algorithm is exactly what it rewards).

## D10. UI: Tkinter parity + web dashboard extension

Implement the required live window (belief heatmap, local truth only) + replay verifier
("Verified OK" screenshot is mandatory). Creativity extension: port HW6's web replay UI to render
finished games from `log_*.json` (post-game only → no info-leak rule risk).

## D11. Process (the 5th grading criterion)

Vibe-Coding lifecycle: initial → PRD (master + 7 stage PRDs) → plan → TODO (500–1000) → verify →
execute → push. Feature branches per capability, granular conventional commits, ruff clean,
pytest ≥85% coverage, every file ≤150 lines, README = academic report (Dec-POMDP, MCP dilemmas,
strategies, screenshots, cross-link), `.env-example`, CI, annotated tag `v1.0-submission`.

## D12. Timeline (deadline 2026-08-12)

- **W1 (Jul 13–19)**: stages 1–3 — engine core, localhost P2P, blind-info brains, self-play lab v0.
- **W2 (Jul 20–26)**: stage 4 — scent + belief v2 + hints/LLM + deception; brains v1 tuned in lab.
- **W3 (Jul 27–Aug 2)**: stages 5–6 — ngrok remote play, commit-reveal + audit + replay verifier.
- **W4 (Aug 3–9)**: stage 7 — Gmail + artifacts + GUI polish; **warm-ups then counted games** vs
  the WhatsApp pod (3 opponents available; ≥2 counted required).
- **Buffer (Aug 10–12)**: two deliverable repos finalized, tags, screenshots, Moodle PDFs.

## D13. League posture

Warm-up first with every opponent (free), count the game only when we're stable. Declare counted
games truthfully. Diversity reward (10/win vs new opponent) → target 3 counted wins across the
pod. Negotiation checklist (LEAGUE-OPS.md) pins: dialects (D3), coordinate system, starts,
arena/hint cap, LLM-move exception (we DECLINE it — our edge is the algorithm), token budget,
who counts this game. Book p.34: contract is a floor — legal, mutually-agreed upgrades and
loophole play are encouraged; the lab (D7) is our loophole detector.

## D14. Ed25519 declaration signing (per NotebookLM A7/A9, 2026-07-13)

No staff-distributed key exists. We generate a **team Ed25519 keypair** (`cryptography` lib,
private key outside the repo); public keys are **exchanged with the partner and locked into the
signed pre-game declaration** (`"ed25519:base64-signed-blob"` in the declaration schema) before
play, so the spec record cannot be altered mid-series. The key signs the declaration AND the
step-0 record (SHA-256 commit-reveal of the hardware record still satisfies computational
fairness; declaration signing = Ed25519). The **counted-games-so-far declaration goes INSIDE the
cryptographically signed declaration JSON** (rule 37, A9b — prevents diversity-reward resets and
counted-game-limit bypass). Audit-caught forgery ⇒ the sub-game is adjudicated
**`technical_loss` 0/0** in the result JSON; both groups must still report — failing to report a
caught forgery risks total disqualification (A9a).

---

## Rulings log (NotebookLM, 2026-07-13)

- **A1 hash**: book construction (nonce INSIDE the canonical JSON) is authoritative for league cross-audits; the reference's pipe-append is a "simplified sketch" → D3 hash default flipped to `book`.
- **A2 scent**: book multiplicative τ(t+1)=max(0,(1−ρ)·τ+Δτ) is the reference standard; the reference subtractive/max-merge dialect is a LEGAL upgrade if exchanged + crypto-locked at Step-0 (rule 23); priority = byte-identical peers.
- **A3 rules**: cop has 5 barrier placement options (own cell + 4 orthogonal); rules 46/47 (barrier-on-thief and jailed-thief captures) are MANDATORY in league play — implement even vs stock-reference peers (confirms D4).
- **A4 repos**: an identical engine/SDK package across both repos is allowed; Zero-Trust = separate OS processes, config dirs and no shared state — not independent code (confirms D2).
- **A5 survival**: STAY/HOLD count toward the thief's 35; the cop's barrier turns do NOT; adjudicated on the thief's OWN valid-step counter.
- **A6 timeout**: on timeout/crash the surviving peer MUST still run the audit and email the result JSON; result string `technical_loss`, scores 0/0 (confirms D4).
- **A7 step-0 key**: no staff key — teams use their own Ed25519 keypair; pubkeys exchanged + locked in the signed pre-game declaration → D14.
- **A8 4-stage**: the compressed flow is compliant — stages 1–3 (Commit/Ack/Reveal) sequential every turn; stage 4 = single end-of-game reveal of all nonces.
- **A9 forgery + ledger**: (a) audit-caught tampering ⇒ sub-game `technical_loss` 0/0, both groups still report (unreported forgery risks total disqualification); (b) rule 37: the counted-games-so-far count goes INSIDE the signed declaration JSON.
