# PRD-4 — Language + Scent + Belief + LLM (Book Ch4+Ch6; roadmap stage 4)

## Purpose
The big leap (brief §14.4): replace exact coordinates with **free natural language**, implement
the **pheromone emission/decay equations**, and give each agent a **Bayesian belief** fusing
unfakeable scent with possibly-false hints. This is where the project's core uncertainty is born
and where the **Adaptation grade** is earned. Belief v2 per **D6** is the group differentiator.

## In scope
- Scent field (emission + decay), **both dialects** (D3), rule-23 lock artifacts.
- Belief v2 engine (D6, all four mechanisms below).
- Verbal layer: template + Ollama trash-talk, incoming-hint interpretation, deception policy.
- Brains v1: PRD-3 brains re-targeted from true position to belief; lab-tuned.

## Out of scope
Crypto sealing of hints/intent (PRD-6 — fields produced here, sealed there), Gmail/GUI (PRD-7;
the belief heatmap data structure is produced here, rendered there), tunneling (PRD-5).

## Functional requirements

### Scent (Table 16 — all fixed: intensity 0.9, ρ=0.10, 5×5 field)
- **FR-4.1 Emission.** Every move/stay deposits a 5×5 field centered on the agent: center 0.9,
  radial falloff (reference detail: Chebyshev rings 0.9/0.6/0.3, 3-dp rounding — a rule-23
  exchange item, reference_map landmine #4).
- **FR-4.2 Dual-dialect decay/merge (D3).** Config-selected, locked pre-series:
  `book` = τ(t+1)=max(0,(1−ρ)·τ+Δτ) multiplicative decay + **additive** deposit;
  `reference` = max(0, τ−0.10) subtractive decay + **max-merge** deposit. Default = whatever the
  partner runs. Update ordering matches the reference pipeline (diffuse→observe→absorb→decay;
  reference_map §2.2).
- **FR-4.3 Rule-23 lock.** Pre-series artifact: full formula text + a concrete numeric worked
  example, SHA-256 hashed and exchanged; the hash recorded in the negotiated terms/log. Any
  later deviation is detectable (rule 23).
- **FR-4.4 Wire format.** `smell_grid` as `{"r,c": float}` string-keyed dict, cells > 0 only
  (reference_map §3.2); `min_center_intensity` anti-decoy floor honored when configured.

### Belief v2 (D6 — MUST implement all four; book Ch6 + p.63)
- **FR-4.5 Emission inversion.** Likelihood `P(observed smell_grid | opponent at cell s)` computed
  by inverting the known 5×5 emission profile + decay history — not the reference's crude
  `P *= (1 + trust·intensity)` bump.
- **FR-4.6 Zero-scent as evidence.** Cells whose expected fresh trail (≈0.81 one turn later at
  ρ=0.10, brief §5) is absent get their posterior mass actively reduced — silence is information.
- **FR-4.7 Adversarial motion-model diffusion.** Belief diffuses per a role-aware motion model
  (thief flees the cop's known position / cop chases), orthogonal+stay kernel only — never the
  reference's uniform king-kernel default; barrier cells masked to zero, renormalized.
- **FR-4.8 Hint fusion with a reliability coefficient (book p.63, מקדם מהימנות).** Each incoming
  hint is parsed into a spatial likelihood, Bayes-combined with weight = a named per-opponent
  reliability coefficient, initialized from config and **updated online from scent-contradiction**
  (hint says north, scent mass south ⇒ coefficient drops ⇒ future hints discounted). This is the
  book's flagship lie-detection mechanic, absent from the reference (gap #22).

### Verbal layer (Tables 14, 21; rules 25–27)
- **FR-4.9 Free NL only.** Hints ≤ `hint_max_words` (15, negotiable); arena landmarks from config
  (`"New York"` default; London/Paris supported); **no numeric-coordinate protocol** (rule 27) —
  an outbound-hint linter blocks coordinate-looking strings.
- **FR-4.10 LLM at the edge only.** Provider modes per Table 21 behind the `[trash_talk]` seam:
  `template` (default, 0 tokens) and `ollama` (local qwen2.5:7b, fallback aya-expanse:8b, D8)
  implemented; `claude_api`/`claude_cli` stubbed but off (course zero-API-key rule).
  `every_n_steps` throttling; ANY provider error/deadline ⇒ template fallback; a full series can
  run at 0 tokens. The move is ALWAYS Python (rule 25).
- **FR-4.11 Hint interpretation.** Incoming hints classified (claim type, direction, landmark) by
  Ollama with a deterministic keyword fallback, feeding FR-4.8; interpreter output never touches
  move legality.
- **FR-4.12 Planned deception (thief).** Lie/truth chosen per turn (`Intent` flag) by expected
  belief-error gain — lie when it moves the cop's inferred belief most, aware that scent will
  contradict blatant lies (D6). Cop hints support misdirection about barrier plans while barrier
  DECLARATIONS stay truthful (rules 14–15).
- **FR-4.13 Token metering.** Per-step and cumulative LLM token counts recorded (feeds Step-0
  lock + result JSON, rules 24/54); template mode reports 0.

## Acceptance criteria (testable)
1. **Runs end-to-end:** full localhost series where neither peer receives true coordinates —
   only smell_grid + hints — and games still terminate legally; template mode series = 0 tokens.
2. Scent golden tests: both dialects reproduce hand-computed numeric examples (the same examples
   used in the rule-23 lock artifact); dialect switch via config only.
3. Belief calibration (lab): with truthful hints, mean posterior mass on the true cell strictly
   exceeds the reference-style bump baseline; with 100% lying opponent, the reliability
   coefficient converges low and final belief error is not worse than scent-only.
4. Lie-detection test: scripted "moved north"+south scent scenario drops the coefficient below
   its prior within N turns (N from config).
5. Blind-vs-blind lab: belief-v2 cop captures the PRD-3 thief significantly more often than a
   scent-argmax-chasing cop (Ch6 policy family 1 baseline); numbers in STRATEGY.md.
6. Hint linter test: numeric/coordinate hint blocked; 16-word hint truncated/regenerated.
7. CI uses injected fake LLM only (no Ollama in tests); gates: ≤150 lines, ruff, coverage ≥85%.

## Dependencies
PRD-1 (board masks), PRD-2 (TurnMessage carries smell_grid+hint), PRD-3 (brains + lab).

## Risks
- Partner runs a third scent interpretation → rule-23 worked-example exchange catches it
  pre-series; both dialects + config-driven falloff give negotiation room.
- Ollama latency blowing the 30s step deadline → `every_n_steps`, hard deadline, template
  fallback (loop never stalls).
- Emission-inversion cost on 7×7 is trivial, but keep it O(N²) per update for bigger negotiated
  boards (computational-fairness story, D9).
