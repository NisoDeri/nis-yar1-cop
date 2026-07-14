# PRD-3 — Blind Strategy on Full Information (Book Ch6; roadmap stage 3)

## Purpose
Wire an initial decision module on **full, exact information** — no scent, language, or deception
yet (brief §14.3). Isolates decision-core correctness from uncertainty noise: bugs here are pure
strategy bugs. Also stands up the **simulation lab** (D7), the evidence machine every later
strategy claim depends on.

## In scope
- The `[strategy]` extension seam exactly per Table 22 / reference contract (reference_map §4.1):
  `BrainBase`/`ThiefBrain`/`PoliceBrain`, `_pick_move(moves, state, belief)`,
  `_decide_move(state, belief, barriers_max)`, `Decision` dataclass,
  `load_brain_cls("module:Class")` with subclass check, `__init__(llm=None, rng=None, trash=None)`.
- Full-info heuristic brains v0 (true opponent position injected in place of belief argmax).
- Simulation lab v0: headless, in-process, injected fake transport, seeded RNG, hundreds of
  games/minute; win-rate tables + CSV output.
- Fallback discipline: illegal brain output force-degraded to HOLD (never stall the loop).

## Out of scope
Belief/scent (PRD-4 — brains consume `belief.most_likely()` so the same code later runs blind),
LLM (PRD-4), networking beyond the PRD-2 harness, Q-learning (optional add-on gated by lab
evidence, D6).

## Functional requirements
- **FR-3.1 Seam fidelity.** Brains load from private config `[strategy] police_class/thief_class`
  (Table 22); empty section ⇒ built-in default brain; a non-`BrainBase` class raises. Role
  alternation means both repos develop both classes; deliverable repos ship role-trimmed (D2).
- **FR-3.2 Policy track.** Book Ch6 track 2 — "your own heuristic algorithm" (belief + barriers +
  lookahead; reference_map §9 discrepancy #1). The LLM never picks the move (rule 25); we DECLINE
  the LLM-move exception in negotiation (D13).
- **FR-3.3 Cop brain v0.** BFS **true-distance** interception on the barrier-aware graph (not raw
  Manhattan through walls); target = exact thief cell (this stage) / belief argmax (later);
  flight-path prediction (intercept where the thief is going); principled barrier policy —
  funnel/quadrant cage placement replacing the reference's 15% coin flip (D6).
- **FR-3.4 Thief brain v0.** Mobility maximization: score moves by k-step reachable-cell count
  (never get jailed — capture rule 3 awareness); distance maximization from the cop; edge/corner
  discipline vs barrier traps (D6).
- **FR-3.5 Decision hygiene.** Every `Decision` carries move_type/direction plus placeholder
  hint/verdict fields (sealed later, PRD-6); `response_seconds` measured; deadline from config
  respected — brain overruns degrade to HOLD, never block (reference_map §2.4).
- **FR-3.6 Simulation lab v0.** `uv run … lab` runs N seeded self-play games (our cop vs our
  thief, and vs reference-default heuristics re-implemented as baselines), emitting win-rate,
  capture-type breakdown (land-on/barrier/jailed), mean steps-to-capture, and per-config-sweep
  tables (D7).
- **FR-3.7 Determinism.** Same seed + same config ⇒ identical game transcript (course gate:
  deterministic engine; enables regression tests on strategy changes).

## Acceptance criteria (testable)
1. **Runs end-to-end:** two localhost processes (PRD-2 infra) play a full 6-sub-game series with
   the v0 brains on full information; every game reaches a legal terminal state.
2. Lab: 500 seeded games complete headless in CI-feasible time with zero network/LLM; results
   reproducible bit-for-bit for a fixed seed.
3. Strategy floor: cop v0 beats a random-walk thief in >90% of lab games; thief v0 survives vs a
   random-walk cop in >90%; cop v0 strictly outperforms the reference-style 15%-coin-flip
   baseline on capture rate (numbers recorded in lab CSV, cited in STRATEGY.md).
4. Jail-awareness test: thief v0 never self-jails when a non-jailing legal move exists.
5. Seam test: swapping brain class via config only (no code change) changes play; bogus class
   path fails fast with a clear error.
6. Gates: ≤150 lines/file, ruff, coverage ≥85%.

## Dependencies
PRD-1 (physics), PRD-2 (turn loop + injectable transport for the lab).

## Risks
- Overfitting brains to full information → keep the belief interface as the only input surface so
  PRD-4 swaps in uncertainty without brain rewrites.
- Lab results not translating to real opponents → D13 warm-up games before counting anything.
