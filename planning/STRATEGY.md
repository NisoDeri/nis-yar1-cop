# STRATEGY — The Graded Core (Belief v2 + Brains + Deception + Lab)

Group **nis-yar1** (Nissim Deri, Yarden Tziar) · Final project, Dr. Yoram Segal · Status: ACCEPTED design, conforms to DECISIONS.md D1–D14 incl. the 2026-07-13 NotebookLM rulings log (A1–A9).

**Scope.** Deep design of the `[strategy]` extension point — the part the book grades (brief §9, ref-map §7 gap 22: *"both brains are baseline heuristics. This is where the grade is."*). Every mechanism binds to the reference APIs (ref-map §4.1) so it drops into implementation unchanged.

**Traceability tags:** *(brief §N)* = FINAL_PROJECT_BRIEF.md, *(ref-map §N)* = planning/reference_map.md, *(DN)* = planning/DECISIONS.md, *(rule N)* = Appendix E, *(book pN)* = PDF page.

**Split markers** (per D2 role-trimmed repos): **[SHARED]** ships in both deliverable repos; **[COP]** only in `nis-yar1-cop`; **[THIEF]** only in `nis-yar1-thief`.

---

## 1. Threat model [SHARED]

### 1.1 The default opponent: reference-derived greedy brains

Most groups will run the professor's simulator with the shipped brains (D1: *"most groups will run reference-derived peers"*). Their exact policies *(ref-map §2.2)*:

> **ThiefBrain**: maximize distance from `belief.most_likely()`, tiebreak unvisited.
> **PoliceBrain**: minimize distance; **15% random chance to BARRIER the cell it would have stepped onto.**

and their belief *(ref-map §2.2)*:

> `observe_smell(cells)` — `P *= (1 + trust·intensity)` then normalize (**scent is the ONLY evidence source — hints are never fused**); `diffuse()` — motion model (von Neumann+stay iff orthogonal=True, **else 3×3 king**).

Exploitable weaknesses, each mapped to one of our mechanisms:

| # | Reference weakness | Source | Our exploit |
|---|---|---|---|
| W1 | `Board.distance` is **Manhattan-through-walls** (stateless board, no barrier awareness) | ref-map §2.1 | BFS true distance (§3.1, §4.2) — we route around barriers they pretend don't exist |
| W2 | Belief bump `P *= (1+4τ)` multiplies the **whole trail** — posterior smears along history, lags the true cell | ref-map §2.2 | Emission inversion (§2.3) — our posterior collapses to the true cell every turn under the reference dialect |
| W3 | `diffuse()` defaults to **king-move** kernel even in an orthogonal game (`orthogonal=False` default) | ref-map §2.2, §7 gap 4 | Their belief leaks mass diagonally → extra lag; our kernel matches the locked physics |
| W4 | Cop barrier policy = **15% coin flip on its own next step cell** — it walls its own chase path 15% of the time | ref-map §2.2 | Pure gift of tempo; our thief's T*-safety metric (§4.2) prices each such blunder instantly |
| W5 | **Hints are never fused** into belief | ref-map §2.2 | vs reference-default peers our lies have zero mechanical effect → don't waste them (§5.2 probe decides); conversely their hints are free profiling data for us |
| W6 | Greedy argmax-only chase, no interception, no expected-time reasoning | ref-map §2.2 | Exact pursuit solve T* (§3.2) — we play the solved game, they play greedy |
| W7 | Deterministic policies given belief | ref-map §2.2 | Their motion kernel is fittable in ~5 observed moves (§2.4, §5.5) |

### 1.2 The information structure nobody in the reference league is using

Two facts about the wire *(ref-map §2.2, §3.2)* dominate all strategy:

1. **Scent is broadcast, not sensed.** The `smell_grid` in every TurnMessage is the opponent's **full own-trail snapshot** (all cells > 0), delivered regardless of where we stand. There is no "move closer to sense better." Information gathering ≠ positioning for sensors; it means *constraining where the opponent can be/go* (§3.4).
2. **Under the reference scent dialect the game is fully observable in practice.** Sender order is deposit(0.9 center, max-merge) → decay_all(−0.10) → send *(ref-map §2.2)*. So the sender's current cell reads **0.800** and every older cell has decayed at least twice from ≤0.9, i.e. ≤0.700. **The unique argmax of the received snapshot IS the opponent's current position, every turn** (proof in §2.3). Both sides enjoy this. The winner is therefore decided by *search quality on known positions* — exactly our T* solver — not by guessing.

Under the **book dialect** (multiplicative decay + additive deposit clamped to τ∈[0,0.9], *(brief §5, D3)*) stale stacked cells can pin at the 0.9 cap and tie with the fresh center → genuine ambiguity. Consequence for negotiation (D13): **the reference dialect favors the stronger searcher (us); the book dialect favors the stealthier thief.** The lab (§6, experiment E7) quantifies which dialect nets us more points across a 6-sub-game role-alternating series before we take a posture into LEAGUE-OPS.

### 1.3 The strong opponent

A peer that, like us, read the book carefully could:

- **Run the same argmax inversion** (W2 fixed) — then belief quality is a wash and the contest moves to §3/§4 search depth and barrier doctrine. This is why our core is a solver, not a better guesser.
- **Fuse our hints** (book p.63) — then our deception layer (§5) has a real target; their reliability coefficient punishes clumsy lies within 1–2 turns *(brief §5: expected fresh trail ≈ 0.9·0.9 ≈ 0.81 vs measured 0.00)*, so we lie rarely, plausibly, at high-value moments only.
- **Lie to us** — bounded damage by construction: our hint likelihood is a mixture gated by reliability r_t learned from scent-contradiction (§2.5); a caught liar's hints degrade to (at worst) noise, and optionally to *inverted* evidence.
- **Exploit protocol slack** (duplicate messages, no dedup, timeout games — ref-map §2.4, §10): handled at the runtime layer (D4: timeout = 0/0 both, audit always runs; D5 watchdog/FSM), not in the brains. Out of scope here; noted so nobody "fixes" it in strategy code.
- **Negotiate hostile terms** (bigger board helps the thief; dialect choice per above). We answer with lab-derived negotiation cards (§6) — never accept a term we haven't measured. Roles alternate across the 6 sub-games (*ref-map §2.4: odd = natural role*), so board-size effects nearly cancel; dialect effects don't (E7).
- **Mine the audit.** All sealed records — including our `intent` (truth/lie) per hint and our exact positions — are revealed at end-of-game audit *(ref-map §2.3, §4.1: verdict/prompt/reasoning are SEALED into the audited record)*. A strong opponent profiles us between sub-games exactly as we profile them (§5.5). Counter: per-sub-game strategy jitter from config (§7), never a fixed lie cadence.

---

## 2. Belief engine v2 [SHARED] (D6)

Replaces the reference `BeliefGrid` internals while keeping its call surface (`most_likely() / as_matrix() / diffuse() / observe_smell() / exclude()`, *ref-map §4.1*) so `TurnHandler`'s update order — `belief.diffuse()` → `belief.observe_smell(msg.smell_grid)` → `smell_field.absorb(...)` → `smell_field.decay_all()` *(ref-map §2.2)* — is untouched. V2 additionally consumes the hint and the declared barrier via a new `fuse_hint(hint_geometry)` / `note_barrier(cell)` called from the same handler seam. Ablation switch `belief.impl = "v2" | "reference"` (§7) keeps the reference math available for lab baselines.

### 2.1 Notation and evidence

- Grid cells `C`, board n×n (n=7 default). Barrier set `B_t` = `OwnGameState.barriers` (own + opponent-declared via `note_barrier`, truthful by rule 14) *(ref-map §2.1)*.
- Hidden opponent position `x_t`. Belief `b_t(c) = P(x_t = c | e_1..e_t)`.
- Evidence per opponent turn: snapshot `S_t : C → [0, 0.9]` (sparse `{"r,c": float}` dict, missing key ⇒ 0, values rounded 3dp — *ref-map §2.2, §3.2*); hint `h_t` (≤15 words, may lie); `barrier_placed` (cop opponent, truthful); `capture_claim` / `claim_response` traffic.

### 2.2 Forward scent model (dialect-parameterized, D3)

The locked-per-series law *(rule 23)*. Fresh stamp centered at `x`, for cells `d` in the 5×5 window (`cheb(x,d) ≤ 2`, in bounds):

```
F_x(d) = round(max(0, E0 − (E0 / (half+1)) · cheb(x, d)), 3)      # E0=0.9, half=2 → rings 0.9 / 0.6 / 0.3
```

*(ref-map §2.2: falloff `intensity/(half+1)` per Chebyshev ring, 3dp)*. Snapshot evolution, per the sender's deposit→decay→send order:

```
reference dialect:  S_t(d) = max(0,  max(S_{t-1}(d), F_{x_t}(d)) − ρ)                # max-merge, subtractive
book dialect:       S_t(d) = clamp((1−ρ)·S_{t-1}(d) + F_{x_t}(d), 0, τ_cap)          # additive, multiplicative; τ_cap=0.9, clamp semantics NEGOTIATED
```

ρ = 0.10, all constants from the signed shared config *(Appendix F Table 16; ref-map §10 landmine 4: clamp/rounding are part of the rule-23 lock)*. The engine implements **both**; `pheromones.dialect` selects.

### 2.3 The inversion theorem (why v2 crushes W2)

**Claim (reference dialect):** the unique argmax of `S_t` is `x_t`, at exactly 0.800.
**Proof sketch:** `x_t` receives `F = 0.9` this turn, then one decay → 0.800. Any other cell last received ≥ its current value at some turn ≤ t−1 with peak ≤ 0.9 and has decayed ≥ 2 times since its last refresh could be at most 0.9 → 0.8 → 0.7... formally: a cell's value exceeds 0.700 only if it was a deposit **center** (0.9) decayed exactly once — i.e., the current position. Max-merge never raises a stale cell above a fresh 0.9 center. ∎

So under the reference dialect `argmax(S_t)` is a **deterministic position decoder**. V2 still runs the full Bayes filter below (identical code path) because: (a) the book dialect breaks uniqueness (cap-plateau decoys, §1.2); (b) packet loss/duplication forces resync from an absolute-map likelihood; (c) the posterior *variance* (not just argmax) drives the cop's expected-time move rule (§3.3) and the reliability update (§2.5).

### 2.4 Recursive Bayes filter

Per opponent turn: **predict** (motion) → **update** (scent) → **fuse** (hint) → **mask** (barriers).

**Predict — role-conditioned adversarial kernel (not the reference's uniform/king diffuse).** The opponent moves by policy, not by diffusion. Transition kernel over its legal moves incl. STAY (barrier-aware, orthogonal — matching locked physics):

```
K_t(c′ | c) = softmax_η { u_role(c → c′) }   over  c′ ∈ {c} ∪ {cell for (dir, cell) in board.legal_moves(c, B_t)}

u_thief(c→c′)  = [ d_BFS(c′, me_t) − d_BFS(c, me_t) ] + μ_mob · mob_k(c′)      # they flee us + keep options
u_police(c→c′) = [ d_BFS(c, me_t) − d_BFS(c′, me_t) ]                          # they chase us
```

`me_t` = our own position (which the opponent knows under the reference dialect, §1.2 — model them as informed). `η` = sharpness (config `belief.motion_eta_*`); `η=0` recovers the reference's uniform diffuse for ablations. `d_BFS` from §3.1. After each sub-game audit, `η` and the policy family are **re-fit from the opponent's revealed positions** (§5.5).

```
b̄_t(c′) = Σ_c K_t(c′ | c) · b_{t−1}(c)
```

**Update — emission-profile inversion + zero-scent as negative evidence.** For each candidate `c`, predict the snapshot the locked forward law would produce if `x_t = c`:

```
Ŝ_c = forward_step(S_{t−1}, c)            # §2.2, the LOCKED dialect
L(S_t | x_t = c) ∝ exp( − Σ_{d ∈ supp(S_t) ∪ supp(Ŝ_c)}  w(d) · (S_t(d) − Ŝ_c(d))² / (2σ_obs²) )
w(d) = λ_zero  if S_t(d) = 0 and Ŝ_c(d) > 0   else 1
```

- The `λ_zero ≥ 1` branch is **zero-scent as evidence** (D6): a candidate whose predicted fresh stamp lands where the wire says 0.000 is annihilated — this is precisely the brief's lie-detection arithmetic (*expected ≈ 0.81, measured 0.00*, brief §5) done for every cell every turn, not only when a hint prompts it.
- With the deterministic locked law and 3dp rounding, small `σ_obs` collapses `L` to the candidates reproducing the snapshot exactly (one cell in the reference dialect; the cap-plateau set in the book dialect). `σ_obs` (config) absorbs partner rounding drift so a 1-ulp mismatch degrades gracefully instead of zeroing the filter.
- Cheap: `Ŝ_c` differs from `decay(S_{t−1})` only inside the 5×5 window around `c` → evaluate the residual on ≤ 25 cells + the predicted-support complement. 49 candidates × ~25 cells, trivial per turn.

**Fuse — §2.5. Mask —**

```
b_t(c) ∝ b̄_t(c) · L(S_t | c) · L_h(c) ;   b_t(c) = 0  ∀ c ∈ B_t ;  renormalize
```

**Resync rule:** if `S_t` is inconsistent with `decay(S_{t−1})` beyond tolerance for *every* candidate (lost/duplicated message — duplicates are legal, ref-map §3 retry semantics), refit from the absolute snapshot alone: the trail is self-contained, so one clean message restores the filter.

**Free localization beacons [THIEF]:** every truthful `barrier_placed = (r,c)` proves the cop was within one orthogonal step of `(r,c)` at placement time (own-cell-or-adjacent reach, D4). Fold as an exact likelihood: `L_barrier(c) = 1[manhattan(c, barrier_cell) ≤ 1]`.

### 2.5 Hint fusion with reliability coefficient r_t (book p.63 — the mechanic no reference peer has)

Maintain a per-opponent Beta ledger `(α_t, β_t)`, prior `(α₀, β₀)` from config, initialized from the cross-sub-game profile (§5.5) when we've met this `group_id` before.

```
r_t = α_t / (α_t + β_t)                                    # reliability coefficient ∈ (0,1)
```

**Hint geometry.** The Ollama classifier (§5.4) maps `h_t` to a footprint `G_h ⊆ C` (direction half-plane relative to the trail centroid, arena-landmark region from the config landmark table, or ∅ = uninformative). `g_h(c) = 1[c ∈ G_h] / |G_h|`.

**Fusion — mixture likelihood, bounded damage by construction:**

```
L_h(c) = r_t · g_h(c) + (1 − r_t) · q(c)
q(c) = 1/n²                                   # default: an unreliable hint carries no information
q(c) = (1 − 1[c ∈ G_h]) / (n² − |G_h|)        # optional lie-inversion: config belief.lie_inversion,
                                              # enabled only when r_t < belief.lie_inversion_below
```

**Reliability update from scent-contradiction events.** After the scent-only posterior `b_scent` (predict×update, no hint) is available:

```
q_consist = Σ_{c ∈ G_h} b_scent(c)                         # how much unfakeable evidence agrees with the words
α_{t+1} = λ_r·α_t + q_consist ;  β_{t+1} = λ_r·β_t + (1 − q_consist)
```

`λ_r ≤ 1` (config) forgets slowly so an opponent who *changes* lying policy mid-series is tracked. The brief §5 example is the extreme case: claim "north", northern cells read 0.000 while the mass sits south-east → `q_consist ≈ 0` → β jumps → `r` collapses → their next hints are noise (or inverted evidence). Scent is unfakeable — a faked `smell_grid` contradicts the sealed positions and is proven in audit *(brief §5; ref-map §2.3 sealed `position`)* — so this ledger cannot be gamed verbally.

### 2.6 Pseudocode [SHARED]

```python
class BeliefV2:                                  # drop-in for BeliefGrid at the TurnHandler seam
    def __init__(self, board, cfg, dialect, profile=None):
        self.b = uniform(board.size); self.alpha, self.beta = profile_or(cfg, profile)
        self.S_prev = {}                          # opponent trail model
    # --- reference-compatible surface (ref-map §4.1) ---
    def most_likely(self): return argmax_cell(self.b)
    def most_likely_p(self): return argmax_cell(self.b), max(self.b)      # v2 extra: prob for §3.3/§3.6
    def as_matrix(self): return self.b.copy()
    def exclude(self, cell): self.b[cell] = 0.0; normalize(self.b)
    def diffuse(self):                            # PREDICT: adversarial kernel, not uniform
        self.b = apply_kernel(self.b, kernel(self.role_model, self.me, self.barriers, self.cfg.motion_eta))
    def observe_smell(self, cells):               # UPDATE: emission inversion + zero-scent
        S_t = sparse(cells)
        L = {c: likelihood(S_t, forward_step(self.S_prev, c, self.dialect), self.cfg) for c in candidates()}
        if max(L.values()) < self.cfg.resync_floor: L = absolute_fit(S_t, self.dialect)   # lost-message resync
        self.b = mask_barriers(normalize(self.b * L), self.barriers); self.S_prev = S_t
    # --- v2 extensions, called from the same handler ---
    def fuse_hint(self, footprint):               # FUSE: reliability-weighted mixture (book p.63)
        q = sum(self.b[c] for c in footprint.cells)                      # b here == b_scent (post-update)
        self.alpha, self.beta = self.cfg.lam_r*self.alpha + q, self.cfg.lam_r*self.beta + (1-q)
        self.b = normalize(self.b * mixture(self.r(), footprint, self.cfg))
    def r(self): return self.alpha / (self.alpha + self.beta)
    def note_barrier(self, cell):                 # mask + [THIEF] cop-adjacency beacon (§2.4)
        self.barriers.add(cell); self.b = mask_barriers(self.b, self.barriers)
        if self.role_model == "police": self.b = normalize(self.b * adjacency_likelihood(cell))
```

Implementation split (150-line gate, D11): `belief/engine.py` (facade), `belief/forward.py` (dialects), `belief/likelihood.py`, `belief/kernel.py`, `belief/reliability.py`.

---

## 3. Police brain [COP]

Replaces *(ref-map §2.2)* "minimize distance; 15% random chance to BARRIER the cell it would have stepped onto." Plugs in via `[strategy] police_class = "nis_yar1.brains:CopBrain"`, `__init__(self, llm=None, rng=None, trash=None)` signature preserved *(ref-map §4.1)*.

### 3.1 True distance (kills W1)

`d_BFS(a, b; B_t)`: BFS on the orthogonal grid minus barriers. One BFS per source cell on demand, memoized until `B_t` changes (barriers are rare events). Never `state.board.distance` for tactics — Manhattan lies whenever a wall stands between (its only remaining use: the reference brains we simulate in the lab).

### 3.2 Exact pursuit solve T* (kills W6)

49 cells → the *known-positions* pursuit game is exactly solvable every turn. State `(c, x, mover)` = (cop cell, thief cell, who moves); thief moves first each round *(ref-map §2.4)*. `T*(c, x)` = number of cop turns to force capture under optimal play, assuming no further barriers (so T* is thief-optimistic; barrier value is measured as ΔT*, §3.5):

```python
def solve_pursuit(board, barriers, horizon):          # value iteration, ~49·49·2 states × ≤5 actions
    T = {s: 0 for s in states if captured(s)}         # cop==thief; thief jailed (rule 47)
    repeat until fixpoint (≤ horizon sweeps):
        T[c, x, COP]   = 1 + min(T[c2, x, THIEF] for c2 in moves(c) )     # capture if c2 == x → total 1
        T[c, x, THIEF] =     max(T[c, x2, COP]   for x2 in moves(x) )     # moves() = legal ∪ {stay}, barrier-aware
    return T                                          # non-converged states → INF (thief evades forever)
```

Milliseconds in Python at this size; recomputed only when `B_t` changes. `INF` states are the map of *where barriers are still needed*.

### 3.3 Move rule: expected capture time over the belief (not argmax-only)

```python
def _pick_move(self, moves, state, belief):           # moves pre-filtered legal (ref-map §4.1)
    T = self.pursuit.tables(state.barriers)
    def cost(cell): return sum(p * min(T[cell, x, THIEF], H) for x, p in belief.items())
    return min(moves, key=lambda m: (cost(m[1]), d_BFS(m[1], belief.centroid())))
```

Argmax-chasing is the `p→1` special case; when belief is spread (book dialect / post-resync), this automatically chases the *mode that is cheapest to finish*, not the nearest. Horizon `H = min(pursuit_horizon, moves_left)`: a thief cell with `T > moves_left` is already worth 0 to chase — the clock is in the objective from turn one.

### 3.4 Information-gathering when entropy is high

Scent is broadcast (§1.2) — we cannot "move to sense." When `H(b_t) > entropy_threshold_bits` (book dialect plateaus, resync turns), the expected-T objective §3.3 already implements the right instinct — *mode covering*: minimize Σ p·T, which favors cells with low capture time to **several** modes (BFS-central positions, corridor mouths). Two explicit additions:

- **Partition pressure:** prefer moves keeping all high-mass modes in one cop-reachable region; never commit through a choke point while ≥ `mode_mass_min` sits behind us.
- **Hint interrogation** (verbal, free): when entropy is high, our own trash-talk turn asks a leading question / provokes a directional reply — any answer feeds §2.5 at zero token cost in template mode.

### 3.5 Barrier doctrine (the 14-charge budget replaces the 15% coin)

A barrier costs one tempo (the cop forgoes moving, brief §4) and one of 14 charges — 14 tempi vs a 35-move clock. Every placement must buy back more than it costs. All candidates come from the 5-option reach: own cell + 4 orthogonal *(D4; wire `barrier_placed=[r,c]` unchanged, ref-map §10 landmine 10 — 5-option must be in the signed terms)*.

**Unified value test.** For each in-reach candidate `w`:

```
gain(w) = Σ_x b(x) · [ min(T*_B(pos,x), H) − min(T*_{B∪{w}}(pos,x), H) ]      # expected cop-turns saved
place iff  max_w gain(w) > 1 + barrier_margin   and   charges_left > barrier_reserve
```

The `> 1` term is the tempo self-financing condition. "Never wall own path" needs no special case: a self-harming barrier has negative gain and is rejected by the same test (contrast W4 — the reference walls its own next step 15% of the time).

**Cage-building (multi-barrier plans).** Greedy ΔT* misses walls whose value appears only when complete. Planner, run when `T* > moves_left` for the main mode (chase alone cannot win):

1. Compute the thief's region `R` (BFS from mode, minus barriers). Enumerate short cut-sets `W` (|W| ≤ `cage_max_cut`) anchored on edges/existing barriers that split `R`, leaving the thief in the smaller side `R'`.
2. Feasibility race: build cost = |W| placements + cop travel between placement-adjacent cells; the thief's escape time through the remaining gap must exceed it. Build **far-from-gap first, close the door last**, with the cop body guarding the gap (the cop is itself a mobile wall).
3. Score = (moves_left − t_close) vs `T*` inside `R'` after closure; commit the cheapest plan that makes `T*_{R'} + t_close < moves_left`. Iterate: each closed cage shrinks `R'` → quadrant → corridor → finisher.
4. Abort rule: replan whenever the thief exits the target side before closure (his moves are observable, §1.2).

**Finisher.**

```python
def _decide_move(self, state, belief, barriers_max):
    x, p = belief.most_likely_p()
    if p >= cfg.finisher_threshold and in_barrier_reach(state.position, x) \
       and state.my_barriers < barriers_max:
        return (MoveType.BARRIER, toward(x))          # barrier-on-thief = capture (rule 46, D4)
    if cage.active and cage.next_cell_in_reach(state): return (MoveType.BARRIER, cage.next_dir())
    w = best_barrier(state, belief)                    # unified value test
    if w: return (MoveType.BARRIER, w.dir)
    return (MoveType.MOVE, self._pick_move(state.board.legal_moves(state.position, state.barriers),
                                           state, belief)[0])
```

Under the reference dialect `p = 1` after every thief move (§2.3): **any thief that ends its move inside our 5-cell barrier reach is captured on the spot.** Also the endgame jail-seal: when the thief's region is a corridor, the last barrier is placed on his cell or his sole exit — jailed = captured *(rule 47)*.

**Reserve:** `barrier_reserve` (default 3) charges are never spent on speculative gains — kept for finisher/jail-seal.

### 3.6 Capture-claim decision rule

The wire makes claiming costless and automatic: `capture_claim` = our landing cell rides **every** MOVE message, and the thief is crypto-obligated to answer truthfully *(ref-map §2.1, §3.2; rule 21)*. A "false claim" in the auditable sense is impossible for us by construction — the claim is always our real landing cell. The genuine decision is **pounce timing**: committing our move onto the believed cell.

```
pounce iff  p(x̂) ≥ pounce_threshold  and  T*[here → x̂] == 1
```

A missed pounce costs exactly 1 tempo and telegraphs our read; with `p ≈ 1` (reference dialect) the threshold is moot, under book-dialect ambiguity the expected value `20·p` vs one tempo of a 35-turn clock sets `pounce_threshold ≈ 0.5` (default; lab-swept). Below threshold, §3.3 keeps herding — shrinking `T*` is worth more than a coin-flip lunge.

---

## 4. Thief brain [THIEF]

Replaces *(ref-map §2.2)* "maximize distance from `belief.most_likely()`, tiebreak unvisited." Objective: **survive 35 valid moves** (brief §4 scoring: survival 10 vs capture-concession 5). Counting semantics **RESOLVED (NotebookLM A5, 2026-07-13)**: STAY/HOLD are valid moves and count toward the thief's OWN 35-counter; the cop's barrier turns do NOT add to it; survival is adjudicated on the thief's own valid-step counter — still worth CONFIRMING per-series at onboarding (ref-map §10 landmine 5), but the book default is now known.

### 4.1 Composite move score

```python
def _pick_move(self, moves, state, belief):            # moves pre-filtered legal
    y = belief.most_likely()                           # cop cell — near-exact under reference dialect (§1.2)
    T = self.pursuit.tables(state.barriers)
    if moves_left(state) <= cfg.endgame_plies: return minimax_survival(moves, state, y, T)   # §4.5
    def score(cell):
        return ( cfg.w_safety   * min(T[y, cell, COP], moves_left(state))   # cop-turns I cost him from here
               + cfg.w_mobility * mob_k(cell, state.barriers, cfg.mobility_k)
               - cfg.w_leak     * leak(cell, self.own_trail)                 # §4.3
               - cfg.w_jail     * jail_risk(cell, state, cop_charges_left) )
    return max(moves, key=lambda m: score(m[1]))
```

`T[y, cell, COP]` (cop to move next — we move first each round, ref-map §2.4) is the exact number of cop turns capture takes from this configuration: the same solver as §3.2, used defensively. Survival test: keep `T > moves_left` and we mathematically cannot be caught without new barriers — the barrier-adjusted risk lives in `jail_risk` and §4.4.

### 4.2 Mobility and the jail rule (rule 47 is the thief's death clause)

```
mob_k(c) = |{cells BFS-reachable from c within k steps, barrier-aware}|
exits(c) = len(board.legal_moves(c, barriers))
jail_risk(c) = LARGE  if  cop_charges_left > 0  and  ( exits(c) < 2
               or region_after_worst_single_barrier(c) < cfg.min_region_cells )
```

Never enter a cell the cop can convert to a tomb with charges he still owns: a single barrier must never reduce us below `min_region_cells` of territory, and a cul-de-sac (`exits < 2` counting our arrival direction) is banned outright while he has charges. When his quota hits 0 (observable — every placement is truthfully declared, rule 14), `jail_risk ≡ 0` and corners become legal terrain again.

### 4.3 Scent management (route families that starve the cop's posterior)

We cannot mute the emitter — deposit fires on every MOVE/HOLD *(brief §5; ref-map §2.2 turn_sender)*. We can control the **innovation** our stamp adds over our own stale trail. The brain mirrors its own `SmellField` (deterministic from our history) and prices each candidate:

```
leak(c) = Σ_d max(0, F_c(d) − R̂(d))        # R̂ = our decayed residual trail; F_c = §2.2 stamp
```

- **Reference dialect:** the argmax exposes us regardless (§2.3) — but only to argmax-grade opponents. Against **reference-default belief** (`P *= (1+4τ)` over the whole trail), low-leak routes — re-walking the 5×5 envelope of our stale trail — keep their posterior smeared along history instead of concentrating on us. Weight `w_leak` is profile-gated (§5.5): high vs reference-belief peers, ~0 vs an inversion-grade cop (don't pay distance for stealth that can't work).
- **Book dialect:** additive stacking pins revisited cells at the 0.9 cap = fresh-center intensity → **cap-plateau decoys**. Loop families through our own trail manufacture multi-cell argmax plateaus; `stay_bias` (config, dialect-conditional) even rewards STAY on a stacked cell when `T`-safety permits. This is why the thief votes `book` in dialect negotiation (§1.2, E7).
- **STAY discipline:** under the reference dialect STAY stacks a max-refresh on one cell and buys no distance — priced by `leak` + zero mobility gain, so it emerges only when already `T`-safe.

### 4.4 Anti-cage play

Barriers are truthfully declared the moment they're placed *(rule 14 — quote: "the cop must openly declare every barrier placement and its exact location")*: the cage is built in the open. Standing monitor, every turn:

1. **Cut watch:** compute min vertex cut κ between our current region-side and the largest open region. Alarm when `κ ≤ cop_charges_left` **and** cop's closing tempo (κ placements + travel, from his known position §1.2) ≤ our BFS time to cross the cut.
2. **Pattern read:** ≥2 declared barriers colinear/anchored on an edge or each other → treat as wall-in-progress; project its completion line.
3. **Exit rule:** on alarm, escape **through the gap now** — override `w_leak`/`w_mobility`, run `T`-safe shortest path to the open side. The race math is the mirror of §3.5 step 2; being early is everything because the door closes last.
4. **Post-alarm:** re-enter the abandoned side only if the wall was completed and the *open* side is larger (his charges are sunk — quota-burn is our win condition too).

### 4.5 Endgame clock

`moves_left = max_steps − state.step_number` *(OwnGameState counter, ref-map §2.1)*. The counter semantics are settled per A5: our own STAY/HOLD increment it (run-out-the-clock oscillation is safe and counts), the cop's barrier turns do not touch it, and adjudication is on OUR counter — no shared-turn-count ambiguity. When `moves_left ≤ endgame_plies` (default 8): full alternating minimax on the exact state (positions known §1.2; else over belief top-k), value = survive-yes/no, thief maximizes the worst case. No leak/mobility aesthetics — only moves whose entire game subtree survives. When `T[y, here, COP] > moves_left` already holds, prefer STAY/oscillation in the safest 2-cell — zero new risk, run out the clock.

---

## 5. Deception layer [SHARED]

LLM touches **only** this layer (brief §8; D8: Ollama qwen2.5:7b, template fallback, zero-token guarantee). Lying via the hint is legal — the protocol seals an `Intent ∈ {truth, lie}` flag per step *(brief §7; ref-map §4.1 `verdict`)*. Lying about barriers or capture answers is disqualification (rules 14–15, 21) and is structurally impossible in our code (§8).

### 5.1 When to lie — the EV gate

```
lie this turn iff  φ̂ · Δerr · V_role  >  cost_r      and  lie_rate_so_far < lie_rate_cap
```

- `φ̂` = P(opponent fuses hints) — estimated by probe (§5.3) and profile (§5.5). **Vs reference-default peers φ̂ ≈ 0** (*hints are never fused*, W5): lies are mechanically worthless — stay truthful, bank camouflage and audit optics for the counted games that matter.
- `Δerr` = expected shift of their posterior off our true cell if fused — highest at decision forks: cage-escape turns [THIEF], pre-pounce herding turns [COP].
- `cost_r` = the reliability we burn: scent contradicts a fresh-area lie within 1–2 turns at ρ=0.10 (*brief §5: expected ≈ 0.81 vs 0.00*), and a p.63-grade opponent's `r` ledger discounts all our future hints. Burned honesty is not recoverable inside a sub-game.

### 5.2 Lie content: plausible-adjacent misdirection

Absurd claims are free calibration data for the enemy's `r` ledger. A lie must survive its 1–2-turn scent window: claim only geometry consistent with our **stale trail envelope** — directions/regions where our residual τ is still ≥ `plaus_tau_min`, typically the branch not taken at a fork. Under the book dialect, lies pointing into our own cap-plateau (§4.3) are *scent-supported* lies — the strongest available. Landmark phrasing from the arena table keeps it inside the 15-word cap and the free-NL rule (numeric coordinates forbidden, rule 27).

### 5.3 Truthful-hint camouflage + probe

Default stream is truthful (`lie_rate_cap` ≈ 0.2, config): every truthful hint raises `r` in their ledger, so the rare lie lands at full mixture weight — the mostly-true stream *is* the weapon. **Probe:** at a low-stakes early turn (config `probe_turns`), send one controlled directional lie and measure the opponent's next-2-move divergence from their fitted kernel (§2.4): divergence → they fuse (`φ̂` up) → deception budget unlocks; no divergence → reference-grade (`φ̂` down) → pure-truth mode, zero deception overhead.

### 5.4 Reading opponent hints (the intake pipeline)

```
hint text → Ollama classify (JSON: {claim_type: direction|landmark|region|none, payload, confidence})
          → geometry: footprint G_h via arena landmark table (config) / half-plane from trail centroid
          → BeliefV2.fuse_hint(G_h)          # reliability-weighted mixture, §2.5
```

`[trash_talk] provider="ollama", model="qwen2.5:7b", every_n_steps` throttled *(ref-map §4.2)*; regex-direction template fallback on any error/deadline — the pipeline can never stall the turn loop and never costs API tokens (D8). An unparseable hint yields `G_h = ∅` → `L_h ≡ uniform` → no-op by construction.

### 5.5 Behavioral profiling across sub-games

The end-of-game audit hands us the opponent's full sealed history: **positions, `intent` truth/lie flags per hint, `random_move` markers** *(ref-map §2.3 sealed_step_record)*. Between the 6 sub-games of a series we:

- fit their motion kernel (η̂, policy family) from revealed positions → sharper §2.4 predict;
- compute their exact lie rate & lie-context pattern → initialize `(α₀, β₀)` for the next sub-game;
- log barrier habits (spend curve, cage shapes) [THIEF] and evasion habits (edge affinity, STAY rate) [COP];
- persist per `group_id` (identity block of the negotiate handshake, ref-map §3.1) under `profiles/<group_id>.json` — warm-ups (free, D13) are farming runs.

Symmetric warning: they mine **us** the same way. Per-sub-game jitter of lie cadence and weight vectors comes from config (§7), seeded per sub-game — never a fixed fingerprint.

---

## 6. Simulation lab [SHARED] (D7 — the evidence machine)

In-process harness on the transport-injection seam (`SimulationSdk.run_peer(transport=...)`, *ref-map §4.3*): both peers, same engine, fake transport, no network/LLM (template mode) — CI-safe, hundreds of games/minute. Every strategy claim in README/STRATEGY ships with a lab artifact (D7).

### 6.1 Experiment list

| ID | Question | Setup | Primary metric |
|---|---|---|---|
| E1 | Baseline replication | ref-cop vs ref-thief, both dialects | capture rate, mean capture step |
| E2 | Our cop's edge | our-cop vs ref-thief | capture rate Δ vs E1 |
| E3 | Our thief's edge | ref-cop vs our-thief | survival rate Δ vs E1 |
| E4 | Mirror stability | our vs our | non-degenerate play, clock health |
| E5 | Is default 7×7/14/35 cop-win under strong play? | our vs our, sweeps board 7/9/11 | capture rate by geometry → negotiation card |
| E6 | Ablations (one feature off at a time): belief v2→reference, kernel η→0, BFS→Manhattan, barrier doctrine→15% coin, hint fusion off, deception off, cage planner off | our vs ref + our vs our | win-rate delta per feature |
| E7 | Dialect value | reference vs book scent law, per role | points/series by dialect → D13 negotiation posture |
| E8 | Parameter sweeps | smell_trust (v1 compat) {1,2,4,8}, σ_obs, η {0,.5,1,2,4}, barrier_margin/reserve/spend curve, pounce/finisher thresholds, mobility_k, w-vector, lie_rate {0,.1,.2,.3}, probe on/off | win rate + secondary metrics |
| E9 | Robustness | duplicated/dropped turn messages, partner 4-option barriers, rounding drift | resync success, no-crash, win rate |

### 6.2 Metrics

Per game: winner, capture step / survival, barriers spent, missed pounces, mean posterior error `Σ_c b(c)·d_BFS(c, x_true)`, rank of true cell, log-loss, entropy trace, `r_t` trajectory vs actual opponent `intent` flags (lie-detection ROC), tokens (must be 0 in template mode). Per experiment: win rate ± Wilson interval, paired-seed deltas.

### 6.3 Promotion rule (nothing ships on vibes)

Candidate brain/parameter change vs incumbent: **N ≥ 400 paired-seed games** (same seeds, both dialects, both roles — role-alternating like the real series). Let `w` = candidate wins among the `m` decisive paired games (ties dropped). Ship iff one-sided exact binomial `P(W ≥ w | p = 0.5, m) < 0.05` — i.e., *a brain change ships only if the lab win rate improves at p < 0.05*. Regressions on any hard guardrail metric (crash, illegal decision, token > 0 in template mode) veto regardless of win rate. Promotion log committed with the config diff (D11 granular commits).

---

## 7. Config surface [SHARED]

Zero hardcoding (course gate; brief §10 "Config rules"). **Shared** keys live in the signed `game.json` terms (Appendix F names, byte-identical both peers, hashed in the handshake — ref-map §6). **Private** keys live in our `game.toml` — the sanctioned unsigned tuning surface (ref-map §4.3: `smell_trust_weight` precedent). Strategy knobs are never in shared config: they are our weapon, not a term.

| Key | Default | Scope | Used in |
|---|---|---|---|
| `pheromones.dialect` (+ ρ, E0, 5×5, clamp/rounding lock) | `book` (A2 ruling; `reference` by locked agreement) | **shared** (rule 23 lock, D3) | §2.2 |
| `belief.impl` | `"v2"` | private | §2 (ablation) |
| `belief.sigma_obs` | 0.02 | private | §2.4 |
| `belief.zero_scent_weight` (λ_zero) | 2.0 | private | §2.4 |
| `belief.motion_eta_thief` / `motion_eta_police` | 2.0 / 2.0 | private | §2.4 |
| `belief.kernel_mobility_mu` | 0.3 | private | §2.4 |
| `belief.hint_alpha0` / `hint_beta0` | 1.0 / 1.0 | private | §2.5 |
| `belief.reliability_forget` (λ_r) | 0.95 | private | §2.5 |
| `belief.lie_inversion` / `lie_inversion_below` | true / 0.25 | private | §2.5 |
| `belief.resync_floor` | 1e-9 | private | §2.4 |
| `belief.smell_trust_weight` | 4.0 | private | v1-compat ablation only |
| `police.pounce_threshold` | 0.5 | private | §3.6 |
| `police.finisher_threshold` | 0.8 | private | §3.5 |
| `police.entropy_threshold_bits` | 2.0 | private | §3.4 |
| `police.mode_mass_min` | 0.2 | private | §3.4 |
| `police.barrier_margin` | 1.5 | private | §3.5 |
| `police.barrier_reserve` | 3 | private | §3.5 |
| `police.cage_max_cut` | 4 | private | §3.5 |
| `police.pursuit_horizon` | 60 | private | §3.2–3.3 |
| `thief.mobility_k` | 3 | private | §4.2 |
| `thief.min_region_cells` | 6 | private | §4.2 |
| `thief.w_safety / w_mobility / w_leak / w_jail` | 1.0 / 0.4 / 0.3 / 10.0 | private | §4.1 |
| `thief.stay_bias` | 0.0 (ref) / 0.2 (book) | private | §4.3 |
| `thief.endgame_plies` | 8 | private | §4.5 |
| `deception.lie_rate_cap` | 0.2 | private | §5.1 |
| `deception.plaus_tau_min` | 0.2 | private | §5.2 |
| `deception.probe_enabled` / `probe_turns` | true / [3,4] | private | §5.3 |
| `deception.jitter_seed_per_subgame` | true | private | §5.5 |
| `[trash_talk] provider / model / every_n_steps` | ollama / qwen2.5:7b / 3 | private (Table 22) | §5.4 |
| `profile.enabled` / `profile.dir` | true / `profiles/` | private | §5.5 |
| `lab.min_games` / `lab.promotion_alpha` / `lab.seed_base` | 400 / 0.05 / from config | private | §6.3 |
| `arena.landmark_table` | per-arena map file | private | §5.2, §5.4 |

Board/starts/steps/barriers/scoring/hint-cap/arena remain exactly the Appendix F shared terms (brief §10) — consumed, never duplicated, by the brains through `state`/config injection. All defaults above are lab-sweep subjects (E8), not sacred numbers.

---

## 8. Compliance guardrails [SHARED]

Hard constraints wired into code, not policy documents:

1. **Moves only from `legal_moves`.** `_pick_move` selects exclusively from its pre-filtered `moves` argument *(ref-map §4.1)*; `_decide_move` barrier candidates only from the agreed 5-option reach, validated via `board.step` before returning. Internal planner failure → return first legal move; the runtime's force-degrade-to-HOLD *(ref-map §2.1)* is the backstop, never the plan.
2. **LLM never picks the move** (rule 25 posture; brief §8). We **DECLINE the book p.66 LLM-move exception in every negotiation (D13)** — our edge is the algorithm; granting an opponent LLM-moves grants them nothing we fear and us nothing we need. The Decision's `move_type/direction` fields are written only by §3/§4 Python; the LLM contributes `hint/verdict/reasoning` strings only.
3. **Hint word cap enforced mechanically:** post-generation truncation to the negotiated `hint_max_words` (15 default, Table 14) in the trash-talk layer for template AND LLM output; free NL only, never numeric coordinates (rules 26–27).
4. **Barrier declarations always truthful** (rules 14–15): `barrier_placed` is emitted by the turn sender from the applied move, not by the brain — the brain cannot lie about it even by bug.
5. **Capture answers always truthful** (rule 21): `claim_response` computed by domain `rules.is_captured(state, claim)` *(ref-map §2.1)*; no strategy code on that path.
6. **Zero-Trust evidence diet** (rules 1–2, 8–9; D2): BeliefV2 consumes only wire-legal inputs — opponent `smell_grid`, `hint`, `barrier_placed`, claims — plus own state. No import path exists from one role's process to the other's state; the live UI renders local truth + belief heatmap only.
7. **Zero-token guarantee** (D8): template fallback on every LLM path; a full series must complete at 0 tokens with deception intake degraded, never the turn loop.
8. **Determinism for the lab and audit:** `rng` injected via the preserved `__init__(self, llm=None, rng=None, trash=None)` signature, seeded from config `[play] seed` — every lab game reproducible, every shipped brain lab-promoted (§6.3).
9. **Sealed honesty:** our `verdict` intent flags are truthful labels of our own hints (lying is legal; mislabeling the flag corrupts our audit story) — the flag is set by the same code that decides the lie (§5.1), one source of truth.
10. **File-size / quality gates** (D11): every mechanism above maps to a ≤150-line module (`belief/*`, `brains/cop/*`, `brains/thief/*`, `deception/*`, `lab/*`), ruff-clean, ≥85% coverage with injected fakes — the lab harness doubles as the integration-test rig (no network, no model in CI).

---

## Delivery mapping

- **W1 (D12):** §3.1–3.3 + §4.1–4.2 on full information (roadmap stage 3 "blind strategy", brief §14), lab E1–E4 v0.
- **W2:** §2 full filter + §5 intake + §4.3–4.5 + §3.4–3.6 (stage 4), lab E5–E8, first promotions.
- **W3–W4:** frozen brains; only E9 robustness and profile-driven retuning between warm-ups (D13).
- **Repo split:** [SHARED] sections → both repos' `docs/STRATEGY.md`; §3 → cop repo only; §4 → thief repo only; §5 role-relevant halves each (D2 role-trimmed strategy).
