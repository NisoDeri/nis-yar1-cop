# Research Report — a Dec-POMDP treatment of P2P Cops & Robbers

Group `nis-yar1` (Nissim Deri, Yarden Tziar) · Orchestration of AI Agents, Dr. Yoram Segal ·
University of Haifa · book v3.0.0. This report formalizes the game, derives the belief-update and
lie-detection equations implemented in `src/pursuit/domain/belief/`, and reports the lab methodology
and honest results behind `README.md` §6. Design source: `planning/STRATEGY.md`, `planning/DECISIONS.md`.

---

## 1. Problem formalization

Two agents `I = {police, thief}` on an `n×n` grid (`n = 7` by config) play a zero-sum pursuit game
under partial observability, with no central controller. We model it as a **decentralized POMDP**
`⟨I, S, {A_i}, T, Ω, {O_i}, R, H⟩`.

**State `S`.** `s_t = (p^cop_t, p^thief_t, B_t, k_t)` — both cell positions, the barrier set `B_t ⊆ C`
(cells `C = {0..n−1}²`), and the thief's own valid-move counter `k_t`. Terminal when the thief is
captured (co-location, barrier-on-thief, or jailed = no legal move) or `k_t ≥ max_steps` (35, survival).

**Actions `A_i`.** Each agent chooses from up to 10 actions: move `{N,S,E,W}`, `STAY`, or place a
barrier on one of 5 cells (own cell + 4 orthogonal, ruling A3). Illegal actions (off-board, into a
barrier) are pre-filtered; the runtime degrades an empty choice to `HOLD`.

**Transition `T`.** Deterministic given both agents' actions and `B_t`. The thief moves first each
round (`ref-map §2.4`); barrier turns mutate `B_t` but do **not** advance `k_t`; MOVE/STAY/HOLD do.

**Observations `Ω`, `O_i`.** Crucially, an agent never observes the opponent's cell. After the
opponent's turn it receives `o_t = (S_t, h_t, b^decl_t)`:
- `S_t : C → [0, E0]` — the opponent's **scent snapshot**, a sparse `{"r,c": τ}` dict (missing ⇒ 0,
  3-dp rounded), broadcast whole. Position is never in the clear; the 5×5 fingerprint must be inverted.
- `h_t` — a free-text hint, `≤ hint_max_words`, which **may lie**.
- `b^decl_t` — a cop's truthful barrier declaration `[r,c]` on the turn it builds (rule 14), else null.

**Reward `R`.** Config scoring (`config/*/game.json`): capture ⇒ cop 20 / thief 5; survival ⇒ cop 5 /
thief 10; tie 2/2; `technical_loss` 0/0. `H` = `max_steps` = the survival horizon.

The agent's job is to maintain a posterior over the opponent's hidden position — the **belief**
`b_t(c) = P(x_t = c | o_{1:t})` — and act on it. Sections 2–3 derive that update; §4 the lab.

---

## 2. Belief update — predict → observe → fuse → mask

Let `x_t` be the hidden opponent cell and `b_t` the posterior. Each opponent turn runs four steps.
Notation: `d_BFS(a,b; B)` is barrier-aware shortest-path distance; `cheb` is Chebyshev distance.

### 2.1 Predict — role-conditioned adversarial motion kernel

The opponent moves by *policy*, not diffusion. Over its legal moves `c′ ∈ {c} ∪ legal(c, B_t)`:

```
K_t(c′ | c) = softmax_η { u_role(c → c′) }
u_thief(c→c′)  = [ d_BFS(c′, m_t) − d_BFS(c, m_t) ] + μ · mob_k(c′)     # flees us, keeps options
u_police(c→c′) = [ d_BFS(c, m_t) − d_BFS(c′, m_t) ]                     # chases us
b̄_t(c′) = Σ_c K_t(c′ | c) · b_{t−1}(c)
```

`m_t` = our own cell (the opponent knows it under the reference scent dialect — model them informed).
`η` (`belief.motion_eta_*`) is sharpness; `η → 0` recovers the reference's uniform kernel (ablation E6).
After each sub-game audit reveals the opponent's true positions, `η` and the policy family are re-fit.

### 2.2 Observe — emission-profile inversion + zero-scent evidence

The forward scent law (dialect-locked per rule 23) stamps a 5×5 fresh fingerprint centered at `x`:

```
F_x(d) = round( max(0, E0 − (E0/(half+1))·cheb(x,d)), 3 )     # E0=0.9, half=2 → rings .9/.6/.3
reference dialect:  S_t(d) = max(0, max(S_{t−1}(d), F_{x_t}(d)) − ρ)          # max-merge, subtractive
book dialect:       S_t(d) = clamp((1−ρ)·S_{t−1}(d) + F_{x_t}(d), 0, τ_cap)  # additive, multiplicative
```

For each candidate `c` we predict the snapshot the *locked* law would produce and score the residual:

```
Ŝ_c   = forward_step(S_{t−1}, c)
L(S_t | x_t=c) ∝ exp( − Σ_d w(d) · (S_t(d) − Ŝ_c(d))² / (2 σ_obs²) )
w(d)  = λ_zero   if S_t(d)=0 and Ŝ_c(d)>0   else 1
```

The `w = λ_zero ≥ 1` branch is **zero-scent as negative evidence**: a candidate whose predicted fresh
stamp lands where the wire reads 0.000 is annihilated. `σ_obs` absorbs partner rounding drift so a
1-ulp mismatch degrades gracefully instead of zeroing the filter. Only ~25 cells (the 5×5 window)
differ from `decay(S_{t−1})`, so evaluation is trivial across all 49 candidates.

**Inversion theorem (reference dialect).** *The unique argmax of `S_t` is `x_t`, at exactly 0.800.*
Sketch: `x_t` receives `F = 0.9` this turn, then one decay ⇒ 0.800. Any other cell was last refreshed
at a turn `≤ t−1` with peak `≤ 0.9` and has decayed at least twice since, so it cannot exceed 0.700;
max-merge never lifts a stale cell above a fresh 0.9 center. ∎ The full filter still runs (the book
dialect breaks uniqueness via cap-plateau decoys; packet loss forces resync from the absolute snapshot;
posterior *variance* drives the cop's expected-time move rule).

### 2.3 Fuse — hint mixture with a reliability coefficient (the reference lacks this)

A hint's geometry `G_h ⊆ C` (direction half-plane / landmark region, or ∅ for uninformative) is
classified by the local LLM (template fallback). Fuse it as a **reliability-weighted mixture**:

```
r_t   = α_t / (α_t + β_t)                       # reliability coefficient ∈ (0,1)
g_h(c)= 1[c ∈ G_h] / |G_h|
L_h(c)= r_t · g_h(c) + (1 − r_t) · q(c)
q(c)  = 1/n²                                     # unreliable hint carries no information
q(c)  = (1 − 1[c ∈ G_h]) / (n² − |G_h|)          # optional lie-inversion when r_t < threshold
```

Bounded damage by construction: an unreliable hint (`r → 0`) collapses `L_h` to uniform (a no-op) or,
optionally, to inverted evidence — a clumsy lie *helps* us.

### 2.4 Mask + renormalize

```
b_t(c) ∝ b̄_t(c) · L(S_t | c) · L_h(c) ;   b_t(c) = 0  ∀ c ∈ B_t ;   Σ_c b_t(c) = 1
```

Resync rule: if no candidate is consistent with `decay(S_{t−1})` (dropped/duplicated message — legal,
no dedup), refit from the absolute snapshot alone; the trail is self-contained, so one clean message
restores the filter.

---

## 3. Reliability math — lie detection from unfakeable scent

The reliability ledger is a per-opponent Beta distribution updated from **scent-contradiction events**.
After the scent-only posterior `b^scent_t` (predict×observe, no hint) is available:

```
q_consist = Σ_{c ∈ G_h} b^scent_t(c)            # how much unfakeable evidence agrees with the words
α_{t+1} = λ_r · α_t + q_consist
β_{t+1} = λ_r · β_t + (1 − q_consist)
r_{t+1} = α_{t+1} / (α_{t+1} + β_{t+1})
```

`λ_r ≤ 1` (`belief.reliability_forget`) forgets slowly, so an opponent who *changes* its lying policy
mid-series is still tracked. The extreme case is the brief's worked example: a peer claims "north"
while its scent mass sits south-east, so `q_consist ≈ 0`, `β` jumps, and `r` collapses within 1–2
turns — thereafter its hints fuse at (at most) noise weight. Scent is emitted by movement and cannot be
suppressed; a faked `smell_grid` contradicts the sealed positions and is proven in audit — so the
ledger cannot be gamed verbally. The reference simulator fuses no hints at all, so this whole axis is
capability the baseline does not have.

Priors `(α_0, β_0)` (`belief.hint_alpha0/beta0`, default 1/1 = uniform trust) are seeded per opponent
`group_id` from the cross-sub-game profile when we have met them before (creativity edge E2).

---

## 4. Lab methodology and results

### 4.1 The evidence machine

`src/pursuit/lab/` runs both peers **in one process over a fake transport** — no network, no LLM
(template mode) — so hundreds of games run per minute, deterministically, in CI. Randomness is an
injected `random.Random` seeded from config; every game is reproducible. This is the only place a
strategy claim is allowed to originate (`planning/STRATEGY.md` §6): *nothing ships on vibes.*

**Promotion rule.** A candidate brain/parameter change ships against the incumbent only if, over
`N ≥ 400` paired-seed games (same seeds, both dialects, both roles — role-alternating like a real
series), the one-sided exact binomial test on decisive games gives **p < 0.05**. Any hard-guardrail
regression (crash, illegal move, tokens > 0 in template mode) vetoes regardless of win rate.

### 4.2 Metrics per game

winner; capture step / survival length; barriers spent; missed pounces; **mean posterior error**
`Σ_c b_t(c)·d_BFS(c, x_true)`; rank of the true cell; log-loss; belief-entropy trace; the `r_t`
trajectory versus the opponent's actual `intent` flags (a lie-detection ROC); token count (must be 0).

### 4.3 Honest results

Agent-vs-agent, BeliefV2 both sides, our brains versus the reference greedy baseline:

| Matchup | Games | Win rate (ours) | Points (ours – theirs) | Test |
|---|---|---|---|---|
| InterceptorPolice + SurvivorThief **vs** reference greedy | 80 – 200 | **0.975 – 0.98** | ~1190 – 430 … ~2980 – 1060 | one-sided binomial **p < 1e-21** |
| **Mirror** — ours vs ours | — | **0.50** | balanced | symmetry / non-degeneracy sanity |

Reading: the mirror match at exactly 0.50 confirms the harness is balanced and neither brain wins on a
coding artifact; the ~0.98 gap over the greedy baseline is therefore attributable to the strategy — the
`T*` solver over an inverted, lie-aware belief versus greedy argmax-chasing over a smeared, hint-blind
one. Ablations (E6: belief→reference, `η→0`, BFS→Manhattan, barrier→coin, hint-fusion off) each recover
part of the baseline, isolating the contribution of every mechanism in §2–3.

### 4.4 End-to-end validation beyond the lab

A **real two-process localhost series** (thief-first, full 6 sub-games) completed with the commit-reveal
chain re-verifying end to end and **all audits passing on both peers**; both independently-emitted
`result_*.json` files carry a byte-identical `mutual_agreement.sha256`. Against the league conformance
kit (`Imreec/copthief-league-protocol`) our commit-reveal, `terms_signature`, `game_uid` and pheromone
emit reproduce the CORE vectors byte-for-byte. Suite: **795 passed, 1 skipped** (live Ollama),
coverage **93.97%**, ruff clean, every source file ≤ 150 lines.

---

## 5. Discussion

The wire is frozen, so byte-exact conformance is table stakes; the game is actually won in the belief,
strategy, and resource-efficiency layers. Two structural facts dominate: scent is *broadcast, not
sensed* (so information gathering means constraining the opponent, not repositioning a sensor), and
under the reference dialect the argmax of the received snapshot *is* the opponent's position (so the
contest reduces to search quality on known positions — an exact `T*` solve — not guessing). Our edge is
therefore a solver, not a better guesser, wrapped in a lie-aware filter the baseline cannot match. All
of it runs in milliseconds of pure Python at 0 LLM tokens — the exact profile the course's
computational-fairness bonus rewards.

*References: `planning/STRATEGY.md` (full derivations + traceability tags), `planning/INTEROP.md`
(wire/hash contract + golden vectors), `planning/DECISIONS.md` (D1–D14 + NotebookLM rulings A1–A9),
`FINAL_PROJECT_BRIEF.md` (book v3.0.0 distillation).*
