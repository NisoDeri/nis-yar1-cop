# Initial — Idea Document

Group **nis-yar1** (Nissim Deri, Yarden Tziar) · "Orchestration of AI Agents", Univ. of Haifa, Dr. Yoram Segal
Final project (40% of course grade) · Deadline **2026-08-12 23:59** (Moodle, no late submission)
Governing sources: rule-book v3.0.0 (Appendix F parameters, Appendix E 55 rules) as distilled in
`FINAL_PROJECT_BRIEF.md`; reference simulator mapped in `planning/reference_map.md`; our accepted
decisions D1–D13 in `planning/DECISIONS.md`.

---

## 1. Mission

Build two symmetric autonomous agents — a **Cop** and a **Thief** — that play a pursuit game on a
7×7 grid with **no central server or referee** (brief §0). Each agent is simultaneously a FastMCP
server and client (true P2P), sees only the opponent's **decaying scent trail** and **possibly-false
verbal hints**, and maintains a **Bayesian belief matrix** over the opponent's location. Integrity
is mathematical, not social: a **SHA-256 Commit-Reveal** protocol with secret nonces makes any
tampering provably detectable in a post-game mutual audit (technical loss 0/0 to the cheater,
rule 19). The agents play a **live league** against other groups over the public internet
(ngrok tunneling, rule 10) and autonomously report signed result JSON via the Gmail API
(rules 32–35). Deliverable: **two separate GitHub repos** — one Cop, one Thief (brief §13).

## 2. What winning means

1. **League placement (75–100 band).** The base league score plus per-game points
   (capture 20/5, survival 5/10, tie 2, technical 0/0 — Table 17), the fixed **diversity reward
   of 10 per win vs a new opponent** (Table 18), and the pass-gate of **≥2 counted games vs
   different groups** (max 10 counted, one counted game per opponent). The exact 75→100 mapping
   comes from Moodle/lecture, not the book (reference_map §9); our posture is D13 — warm up free,
   count only when stable, target 3 counted wins across the WhatsApp pod.
2. **Computational-fairness bonus.** The lecturer normalizes results to reward efficient
   algorithms on modest hardware (rule 24/53, brief §7). Our signed Step-0 hardware declaration
   (laptop, RTX 3500 Ada) + zero-token Ollama/template play + an all-Python heuristic brain is
   exactly the profile this bonus pays (D8, D9). Skipping Step-0 forfeits only this bonus
   (reference_map §9), so we never skip it.
3. **HW6 bonus (up to 10).** Course-level bonus credited toward the final grade — banked
   separately from the league; we protect it by keeping the final-project submission clean.

## 3. The grading axes

Four graded axes (brief §2), plus a fifth criterion the PDF adds (reference_map §9):

| Axis | What the grader looks for | Our answer |
|---|---|---|
| **Coordination** | Turn management, P2P protocol, negotiation | Reference-compatible wire (D1): 4 MCP tools, same envelopes, guarded turn FSM (D5) |
| **Adaptation** | Belief under uncertainty via scent | Belief v2 (D6): emission inversion, zero-scent evidence, adversarial diffusion, hint reliability coefficient |
| **Integrity** | Anti-cheat via hashing | Dual-dialect Commit-Reveal (D3), mutual audit, replay verifier, Step-0, truthful declarations |
| **Architecture** | Gatekeeper + Orchestrator + fail-safe code | Single SDK entry, 3-gate Gatekeeper, watchdog, local-truth-only UI, timeout = 0/0 (D4, D5) |
| **5th: Software excellence** | Dr. Segal's course-intro file applies in full | ≤150-line files, ruff, pytest ≥85%, config-driven, uv, CI, feature branches, docs lifecycle (D11) |

## 4. Our thesis (the differentiator)

- **Own code, reference-compatible wire (D1).** We re-implement in our own style (originality +
  EULA safety) but freeze the reference simulator's interop surface — tool names, envelopes,
  `game_uid` derivation, artifact schemas — because most opponents will run reference-derived
  peers. A private protocol guarantees cross-group failure.
- **Interop insurance (D3).** Both hash dialects and both scent laws implemented, selected by the
  signed shared config and locked pre-series (rule 23). We can play a literal-book peer AND a
  reference-clone peer.
- **Belief + brains is where the grade is (D6, D7).** The reference ships a crude belief bump, a
  15% coin-flip barrier policy, and **no hint fusion at all** (reference_map gap #22). We build
  belief v2, a trapping cop, a mobility-maximizing deceptive thief — and prove every claim with
  the self-play simulation lab.
- **Fix the reference's book violations (D4).** Barrier-on-thief capture (rule 46), jailed-thief
  capture (rule 47), 5 barrier placement options, orthogonal-only fail-fast physics,
  timeout = 0/0 — deviations that would otherwise cost technical losses.

## 5. Scope anchor

Seven build stages in book Ch10 order, each running end-to-end before the next (brief §14):
base logic → localhost FastMCP → blind strategy → language+scent+belief → cloud/tunnel →
crypto/audit → reporting/UI. One PRD per stage under `planning/prd/`. Timeline per D12
(W1 stages 1–3 … buffer Aug 10–12).
