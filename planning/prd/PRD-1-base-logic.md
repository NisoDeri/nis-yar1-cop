# PRD-1 — Base Logic (Book Ch3; roadmap stage 1)

## Purpose
A pure, deterministic game core — board, movement, barriers, captures, scoring — proven in a
**single process with no networking and no AI** (brief §14.1). If two agents cannot move correctly
on a local board, networking is pointless. This layer is the physics contract both peers will
later enforce on each other.

## In scope
- `domain` package: board, own-state, rules, scoring, constants, exceptions (reference_map §2.1
  shapes, re-implemented per D1).
- Book-compliant physics fixing all reference deviations (D4).
- A single-process driver that plays two scripted/random agents to a legal game end.
- Config plumbing: every parameter loaded from config, per-game filename convention
  `config_<game_id>_g<NN>.json` (Appendix F config rules); zero hardcoded values.

## Out of scope
Networking/MCP (PRD-2), brains (PRD-3), scent/belief/language (PRD-4), crypto (PRD-6), UI/report
(PRD-7).

## Functional requirements
- **FR-1.1 Board.** N×N grid, N ≥ 7 (Table 13, minimum); cell `(row, col)`, 0-indexed, origin
  top-left, row grows down — origin/index/starts config-driven and negotiable (Table 13). Default
  starts: thief `(3,3)`, cop `(0,0)`.
- **FR-1.2 Movement.** One action per turn: step one cell orthogonally (N/S/E/W) **or** STAY
  (Table 15, fixed). **No diagonals** (rule 13). A bad/missing `move_set` raises `ConfigError` —
  never the reference's silent king-movement fallback (D4; reference_map gap #4).
- **FR-1.3 Barriers — 5 placement options.** Cop-only; on a turn it forgoes moving it may place a
  barrier on **its own cell or any of the 4 orthogonally-adjacent cells** (brief §4; D4 — the
  reference allows only 4). Barrier cells become impassable to both, irreversibly; quota
  `barriers_max` = 14 minimum (Table 15); placement on out-of-bounds/already-barriered cells
  rejected. Every placement is recorded for the mandatory truthful declaration (rules 14–15).
- **FR-1.4 Captures — all 3 rules.**
  1. **Land-on capture**: cop occupies the thief's cell (validated via capture-claim semantics in
     later stages; locally, position equality).
  2. **Barrier-on-thief**: barrier placed on the thief's current cell ⇒ captured (rule 46; absent
     from the reference — gap #1).
  3. **Jailed thief**: thief with no legal move (all neighbors barrier/edge-blocked) ⇒ captured
     (rule 47; absent from the reference — gap #2). Checked at the start of the thief's turn.
- **FR-1.5 Survival & step accounting.** Thief survives `max_steps` = 35 (minimum, Table 15) valid
  moves ⇒ survival result. Step-counting semantics (whose counter; HOLD/BARRIER counted) is a
  config term to be locked pre-series (reference_map landmine #5); default = reference behavior
  (thief's own counter, all action types count).
- **FR-1.6 Scoring.** From config, defaults asserted against Table 17 (fixed): capture 20/5,
  survival 5/10, tie 2/2, technical loss 0/0. Unknown result string ⇒ 0/0. Timeout/crash maps to
  technical loss 0/0, never waiting-peer-wins (D4; reference gap #5).
- **FR-1.7 Single legality gate.** All action types flow through one `apply_move`-style gate that
  leaves state untouched on rejection; illegal transitions are rejected, not patched (rules 4–5
  groundwork).
- **FR-1.8 Game-state machine.** Explicit state enum + transition table for the game lifecycle
  (SETUP→PLAYING→GAME_OVER + terminal reasons); every illegal transition raises (rules 4–5; D5).

## Acceptance criteria (testable)
1. **Runs end-to-end:** `uv run` driver plays a full scripted game in one process to each terminal
   outcome — land-on capture, barrier-on-thief, jailed thief, survival at 35 — with correct
   Table 17 scores.
2. Unit tests cover: diagonal rejected; STAY legal; barrier on own cell legal, 6th option (e.g.
   diagonal cell) rejected; quota exhaustion; irreversibility; jailed detection on all 4 walls
   incl. board edges; step counter parity between two locally-simulated peers.
3. Property test: from any legal state, every action either passes the gate or leaves state
   byte-identical.
4. Changing any parameter (board size 9, quota 20, max_steps 50) via config alters behavior with
   zero code edits; grep proves no hardcoded Appendix F value.
5. Gates: files ≤150 lines, ruff clean, coverage ≥85% for the package.

## Dependencies
None (first stage). Config loader may be minimal here and extended in PRD-2.

## Risks
- Step-counting semantics diverge from a partner's engine → locked as an explicit negotiated term
  (D13 checklist); tests parameterize both interpretations.
- Over-copying reference internals (EULA) → re-implement from the map, attribute adapted
  fragments in-code (D1).
