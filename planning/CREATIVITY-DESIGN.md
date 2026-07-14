# Creativity & Bonus Design — rules-safe edges that decide the league

Group **nis-yar1**. Everything here is **inside the book** (v3.0.0 + Appendix E/F) and the league
conformance kit. Each edge cites *why it is legal* and *how it wins points*. Source: our own
analysis + a NotebookLM exchange on where the lecturer left room for creativity (the assignment is a
systems-building task, not a coding drill; the tighter the wire spec, the more freedom in strategy,
deception, and architecture — and there are explicit bonuses for **computational fairness** and
creativity).

The organizing principle: **the wire is frozen (so we conform byte-exactly), which is exactly why the
strategy, deception, and resource-efficiency layers are where the game is actually won.**

---

## E1 — Reliability-coefficient lie detection (the flagship graded mechanic)

**What:** every incoming verbal hint is Bayes-fused into the belief map with a *learned* trust weight
`r ∈ [0,1]` (Beta ledger). `r` falls when a peer's words repeatedly contradict its own scent trail
(the scent is emitted automatically by movement — rule: it is *uncontrollable*, so it is ground
truth the liar cannot suppress). Caught liars get their hints **inverted** into negative evidence.

**Why legal:** book p.63 explicitly describes hint fusion with a reliability weight; hints are
free-form and *may* lie (book allows deception). We only *read* what is broadcast.

**Why it wins:** the lecturer's **reference simulator implements no lie-detection at all** — it treats
hints as decoration. This is the single biggest capability gap between "correct" and "smart," and it
is a *scored* axis (Integrity/Adaptation). Status: `domain/belief/reliability.py` +
`BeliefV2.fuse_hint` already built; strengthen into a **per-opponent, cross-sub-game profile** (E2).

## E2 — LLM opponent-profiling across sub-games (psychological warfare)

**What:** between sub-games (no turn deadline there), a local LLM reads the *revealed* transcript of
the just-finished game and profiles the opponent's LLM/agent: does it always lie about "north"? does
it get more truthful near barriers? does it reuse phrasings when cornered? The profile seeds the next
sub-game's trust prior `r₀` and a per-direction lie-bias vector.

**Why legal:** uses only post-game *revealed* logs (no hidden-info leak); the book permits an LLM to
analyze hint "psychology." Between-game analysis has no deadline, so it is free of the p95 wall.

**Why it wins:** an opponent's *LLM* is far less predictable than its physics — but far more
*patterned* than it looks. Profiling the words beats profiling the moves. Zero mandatory tokens
(local Ollama; template fallback). Status: build `strategy/profiler.py` (Workflow B).

## E3 — Active scent-decoy routing (thief)

**What:** the thief does not only flee. When it has tempo, it walks a short **geometric loop** that
deposits a broad, ambiguous scent cloud in region X, emits a *relatively-credible* verbal hint
pointing the cop toward X's center, then slips out of X's edge on the following turn. Goal: pin the
cop's belief argmax on an empty cell.

**Why legal:** movement is fully ours to choose; the scent is a *consequence* of legal moves, not a
forbidden signal we fabricate. The hint is free-form (deception allowed).

**Why it wins:** turns the "uncontrollable" scent into a *weapon* — we can't suppress emission, so we
*shape* it. Directly attacks the opponent's belief map (the same map we invert with E1). Status: add
a `decoy` mode to `SurvivorThiefBrain` gated by an EV test (only when flight-safety margin is high).

## E4 — Barrier-cage doctrine (police)

**What:** replace the reference's 15%-coin "wall the cell I'd step onto" (its self-walling blunder W4)
with a **value-tested** barrier budget: finisher walls (rule-46 capture when the mode is in reach),
tempo walls (seal the thief's best wallable escape lane, never lengthening our own route), and
**quadrant sealing** (funnel the thief into a shrinking region using the 14-barrier budget).

**Why legal:** 5 placement options (own cell + 4 orthogonal, ruling A3); barrier-on-thief and
jailed-thief captures are mandatory (rules 46/47). All book-native; the reference omits both captures
and the own-cell option — we implement them.

**Why it wins:** the reference cop cannot use its most powerful tools (it never places a capturing
barrier). Status: finisher + tempo built in `strategy/police.py`; extend to multi-step cage plans.

## E5 — Computational-fairness bonus (algorithm > brute force)

**What:** **moves are pure Python** (BFS true-distance, belief filter, EV gates) — never an LLM. The
LLM touches only banter/among interpretation and always has a 0-token template fallback. We declare a
**modest laptop** in the signed Step-0 hardware record and report real token totals (mostly 0).

**Why legal:** the book's computational-fairness principle explicitly rewards efficient solutions; the
declaration is a required signed artifact.

**Why it wins:** the lecturer promises bonuses for teams that win on *lean* resources. Beating a team
that burns a heavy remote model with a rank-and-file laptop + a tight algorithm is the exact story the
bonus rewards — and it *lifts league rank beyond the dry game score*. Status: architecture already
enforces this; showcase it in the declaration + README + a token-accounting table.

## E6 — Step-0 asymmetric rule-delta negotiation (opt-in, conservative)

**What:** the handshake can *propose* and *accept* book-legal parameter deltas (e.g. trade a higher
`max_moves` for a higher `token_budget`) — a "package deal" that fits our algorithm's strengths — but
only when the opponent agrees, cryptographically locked in the signed declaration (rule 23/37).

**Why legal:** the book permits mutually-agreed rule upgrades at Step-0; *minimums are never lowered*;
everything is signed and transparent. This is the "signed agreements allowed" clause the kit cites.

**Why it wins (carefully):** double-edged — locking a custom field can backfire. So we ship the
*capability* and keep **default terms conservative**; only propose a delta when the sim-lab shows it
strictly helps us and is plausibly acceptable. Status: negotiation carries dialect+terms already; add
an optional `rule_deltas` block behind a config flag (Workflow B), default off.

## E7 — Academic-freedom, documented (turn contradictions into features)

**What:** where the release contradicts itself, we pick the tactically- and correctness-sound reading
and **document the choice with justification** in the README. Live example: the **commit dialect** —
the release publishes three constructions; we adopt the reference/pipe-appended form (kit CORE, binds
the full record, what opponents run) over NotebookLM's "book-authoritative" reading, because a
hash-mismatch scores 0/0 for both and *interop is what the grade counts*.

**Why legal:** the book's clarification page makes printed listings non-binding and grants academic
freedom on contradictions *provided the choice is stated and reasoned*.

**Why it wins:** converts a spec landmine into evidence of deep understanding (a scored rigor axis) —
and, concretely, keeps every match scorable.

---

## Where each lands in the code

| Edge | Module(s) | State |
|---|---|---|
| E1 lie-detection | `domain/belief/reliability.py`, `belief/engine.fuse_hint` | built; wired in belief |
| E2 profiler | `strategy/profiler.py` (new) | Workflow B |
| E3 scent-decoy | `strategy/thief.py` (+`decoy` mode) | Workflow B |
| E4 barrier-cage | `strategy/police.py` | finisher/tempo built; cage extend |
| E5 comp-fairness | `shared/sysinfo.py`, declaration, README | architecture done; showcase |
| E6 rule-deltas | `domain/negotiation.py` (+flag) | Workflow B, default off |
| E7 academic-freedom | `config/*/game.json`, README | dialect choice done |

**Non-negotiables preserved by all of the above:** moves never LLM-decided (rule 25); byte-exact
conformance to the league kit; ≤150-line files; ruff-clean; ≥85% coverage; honest measurements only.
