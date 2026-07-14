# LEAGUE-PROTOCOL-REVIEW.md — Technical review of Team ImreEyal's `copthief-league-protocol` v0.3-draft

Group **nis-yar1** (Nissim Deri, Yarden Tziar) · 2026-07-13
Reviewed against: **book v3.0.0** (`FINAL_PROJECT_BRIEF.md` distillation, Appendix E 55 rules, Appendix F
parameter tables), the professor's reference simulator wire protocol (`planning/reference_map.md` §3/§5/§10),
our byte-verified interop spec (`planning/INTEROP.md`), and the authoritative NotebookLM answers A1–A9
(2026-07-13, professor's book/code chatbots).

**Checker result:** `python verify_vectors.py` (stdlib only) run in
`reference/copthief-league-protocol/` on 2026-07-13 — **ALL VECTORS PASS** (53/53: 5 canonical-JSON,
4 position-commit, 5 state-hash, 30 derive-starts, 1 match-card, 2 joint-seed, 4 float-rejections,
2 binding pairs). The kit is internally consistent, regenerable (`gen_vectors.py`), and CI-gated.
The engineering quality is genuinely high; the conflicts below are about the *published rules*, not
about their craft.

---

## 1. What the SPEC gets right — endorse in our response

### League services (Appendix B)

| Item | Why we endorse it |
|---|---|
| **Lobby / registry as a GitHub repo** | Zero hosting, no single owner, public timestamped coordination trail; degrades to hand-exchanged match cards. Book v3.0.0 does not constrain league services (their §11 Q4 — and the book p.34 explicitly says the contract is a floor: mutually-agreed upgrades and undefined-space conventions are "permitted and even desirable"). This directly de-risks the book's out-of-band negotiation requirement (terms are agreed off-wire and typed identically into both configs — reference `verify_peer` exact-equality). |
| **Demo league + `stage` interlock** | The single best idea in the draft. Book rules 32–35 make the report email the highest-stakes byte in the project (free-text = 0; contradictory reports = 0 to BOTH). A mechanically-enforced `stage:"demo"` gate that keeps the lecturer's inbox untouchable until every team jointly opens the season, plus a report sink that auto-checks schema + byte-identity of both teams' reports, certifies the *entire* pipeline (email leg included) before the first counted game. With one-counted-game-per-opponent (rule 44/52) and the rule-37 counted-games declaration, "your first counted game should never be your first game ever" is exactly right. |
| **Synchronized fixture rounds** | The book's scoring IS order-sensitive: diversity reward (10, fixed) for each NEW opponent, ≤10 counted games, ≥2 to pass, one counted game per opponent (Appendix F Table 18). A deterministic circle-method round-robin derivable from the roster alone removes scheduling luck and gives every team the same diversity-reward opportunity surface. |
| **Sparring server** | The biggest testing gap in EX06 and in this project too: cross-team behavior cannot be tested alone. An always-on conformant opponent is the league-scale version of our own localhost smoke test against the unmodified reference peer (INTEROP §6.2). Passive, executes no shared game logic — Zero-Trust compatible (A4). |

### Wire discipline (§5, §8, §9, §2)

| Item | Why we endorse it |
|---|---|
| **Hold-don't-advance** (§5.2) | "A parser mis-classifying a message and advancing" is precisely the class of bug the reference is also exposed to (no dedup, duplicate deliveries possible — INTEROP §1). This rule is the correct receiver posture regardless of transport dialect, and it maps onto book rules 4–6 (guarded state machine, reject illegal transitions, never freeze). |
| **Byte-identical resend + dedup by commit** (§8.2) | The reference retries every 1 s with no receiver dedup; idempotent-receive is a hole we already flagged (INTEROP landmine 8). Their rule ("never construct a *different* trailer for the same ply") is the right fix and we should adopt the same invariant on the reference wire. |
| **`prev`/`prev_recv` transcript DAG** (§5.2) | A real cryptographic upgrade over both the book and the reference: the book's commit-reveal proves each *record* wasn't altered, but nothing in the reference chains the transcript *ordering* — their interlocked DAG makes a re-forged history contradict the opponent's later acknowledgments, roots chains in `config_sha256` (no cross-match replay), and makes committed logs self-authenticating. Legal as a mutually-agreed upgrade (book p.34 floor-not-ceiling; same logic as A2's ruling on scent-law upgrades) provided it is locked at Step 0. |
| **Email-exact-bytes lesson** (§9) | "Graders compare emails, not hashes" — an EX06 series nearly scored 0 on a pretty-printed re-serialization. The book sharpens this further: the result must be a **JSON attachment** (rule 33; free text = 0), so the rule becomes "the *attachment* MUST be the exact canonical bytes that were hashed." The lesson (never re-serialize between hash and send) stands verbatim and both our teams should encode it as an invariant. The reference's matching trick — hash only the symmetric outcome subset so both independently-emitted results agree byte-identically (INTEROP §5.4) — is the complementary half. |
| **No-floats-in-hashes warning** (§2) | The *diagnosis* is correct and hard-won (a hand-typed `7.5` nearly cost a series; float repr drifts across languages). We endorse the warning while disputing the blanket rejection (conflict (c) below) — the book's own signed config contains floats, so the fix must be "pin float bytes," not "ban floats." |
| **`agreement`/`transport` split** (§4.1) | Hashing only the rules and letting tunnel URLs/schedule float is exactly right — tunnel restarts must not brick a handshake (we lost our paid ngrok account; named Cloudflare tunnels restart). The concept ports directly into the book's declaration flow: signed terms vs. unsigned identity (the reference already does the same split — `identity` is deliberately unsigned). |
| **Fail at ply zero** (§1, §4.3) | Identical philosophy to the reference's `verify_peer` (terms mismatch = CryptoError, refuse to play) and book rules 4–5. |
| **Secretless servers, LLM in the orchestrator, two servers per team** (§3) | Matches the book's architecture rules 1–3 and A4's Zero-Trust ruling (separate processes/config dirs; sharing an engine package is fine). Bearer-token transport auth is an additive hardening the book doesn't require but doesn't forbid. |

---

## 2. Conflicts with the binding book (precisely cited)

Precedence reminder: book + Appendix F + Appendix E override everything, including the professor's own
reference repo (brief, "Source of truth"); the NotebookLM answers A1–A9 are the professor's-chatbot
rulings on the ambiguities.

### (a) Mode A cleartext moves destroy the graded Dec-POMDP — positions must NEVER be on the wire

- **Their spec:** §7 Mode A ("EX06-proven, default"): every ply's trailer carries cleartext
  `"move":[3,4]` plus an immediately-revealed nonce; both engines stay in lockstep on full information.
  §7 Mode B still reveals exact positions, just lagged by `k` plies.
- **The book:** the environment is a Dec-POMDP whose observations {Ωᵢ} are *only* the opponent's
  decaying scent trail + verbal declarations (brief §3); "Neither agent sees the other." Rule 27
  forbids numeric-location protocols; rule 26 allows free natural language only. The wire-level
  observability channel in the reference protocol is the broadcast **5×5 decaying scent grid**
  (`smell_grid`, Appendix F Table 16: 0.9 center, ρ=0.10, 5×5) + the ≤15-word hint; the true
  position/move/intent live ONLY inside the sealed commit, and exact positions are revealed **only at
  the final audit** via the end-of-game nonce reveal (A8 stage 4; rule 18 keeps nonces secret until then).
- **Why it matters for grade:** **Adaptation (scent-based belief under uncertainty) is one of the four
  graded axes** (brief §2). Mode A deletes the entire uncertainty layer — no belief matrix, no lie
  detection, no scent. Mode B is closer but is a *different observability model* (exact-but-stale
  positions vs. a noisy decaying intensity field) and its capture detection is self-admittedly unsolved.
- **Resolution:** v1.0 needs a **Mode C — scent-grid broadcast**: each TurnMessage carries the sender's
  own decayed 5×5 `smell_grid` (that IS the observation), the hint, and the commit; nonces are withheld
  until the single final audit. This is exactly the reference simulator's wire, so it costs nothing new.
  Mode A remains valid as a *debug/sparring* disclosure level, never for counted games.

### (b) Position commit `{nonce,pos}` vs the book's mandatory H_commit over `{state,move,intent,nonce}`

- **Their spec:** §6.2 `commit(pos, nonce) = sha256_canonical({"nonce": nonce, "pos": [r,c]})` — commits
  the position only; §7 Mode A reveals the nonce in the same message.
- **The book:** Ch5 (brief §7): `H_commit = SHA256(State ‖ Move ‖ Intent ‖ Nonce)` with the **nonce as a
  key INSIDE the canonical JSON** — confirmed authoritative by **A1** (the reference repo's pipe-appended
  form is a "simplified sketch"; the chapter-5 schema governs cross-audits). The sealed record is richer
  still: step, state string, position, move, **intent (`truth`/`lie`) AND its duplicate `verdict`**, hint,
  prompt_discussion, model, token counters (reference sealed payload, INTEROP §2.2).
- **Why intent cannot be omitted:** sealing the truth/lie flag *before* the hint is read is the entire
  lie-detection mechanic — the audit later proves "you committed to lying while claiming X," which is what
  makes verbal deception a scored, auditable game element rather than noise. A position-only commit
  audits the trajectory but not the deception layer, i.e., it drops a graded mechanic (Integrity +
  Adaptation both touch it).
- **Also:** immediate nonce reveal (Mode A) violates **rule 18** (nonce absolutely secret until the final
  audit) and collapses the 4-stage protocol; **A8** rules the compliant flow is Commit → Acknowledge →
  Reveal (move/hint, nonce withheld) every turn, with stage 4 = one end-of-game nonce reveal.
- **One more byte-level trap:** their canonical form is `ensure_ascii=True` (§2); the reference wire
  hashes with `ensure_ascii=False` (Hebrew hints hash as raw UTF-8 — INTEROP §3). Same payload, different
  digests for any non-ASCII hint. Whichever is chosen must be pinned in the rule-23 lock.
- **Resolution:** adopt the book's sealed-payload schema and dialect-B (nonce-inside) construction as the
  v1.0 default; we already implement both dialects with worked byte-level vectors (INTEROP §3.1:
  same payload → `b578bc30…` pipe-appended vs `93a63ddd…` nonce-inside — nothing shared; an unnegotiated
  mismatch = every audit step "fails" = false tamper_forfeit).

### (c) `MUST reject floats` vs the book's float parameters

- **Their spec:** §2 — implementations MUST reject any float anywhere in a hashed object; enforced by
  `vectors/negative.json` (`0.1` is literally one of the rejected fixtures).
- **The book:** Appendix F Table 16 (all FIXED): source intensity **0.9**, decay rate ρ **0.10**; the
  reference adds `min_center_intensity: 0.5`, ring falloff 0.9/0.6/0.3 (3-dp floats on the wire in every
  `smell_grid`), and hardware specs like `ram_gb: 63.5`. These values sit inside the **signed shared
  config** whose `config_sha256` the handshake and the config artifact both cover (Appendix F "config
  rules": identical, cryptographically locked) — and inside the signed agreement terms
  (`decay_per_step: 0.1` is in the reference's exact-equality-checked terms dict, INTEROP §2.1).
  A conformant-to-their-spec implementation **must reject the league's own mandatory config.**
- **Resolution (propose both, pick one at the league table):**
  1. **Documented pinned-float exemption** (our preference — zero deviation from the professor's
     simulator): floats are allowed in hashed objects when produced by JSON round-trip
     (`json.loads` → `json.dumps`), which pins Python/ECMAScript shortest-repr semantics (`0.10` → `0.1`);
     INTEROP §3.2 already documents and verifies this ("load terms through JSON, never hand-construct").
     Scent intensities are additionally pinned by 3-dp rounding at deposit.
  2. **Scaled-integer convention**: express Table-16 values in per-mille ints (`emit_millis: 900`,
     `decay_permille: 100`, `intensity_millis` in scent grids). Cleaner cross-language, but byte-
     incompatible with an unmodified reference peer and with the professor's sample-run artifacts —
     it would need every team plus (effectively) the professor to migrate, so it can only be a
     league-wide locked upgrade per rule 23 / A2's mutual-agreement standard.
  - Their no-floats rule remains 100% right for *their own trailer values* (positions, counters — all ints).

### (d) Match card + single settlement email vs the book's four mandatory artifacts

- **Their spec:** §4.1 one match card (agreement + transport); §9 one report whose *body* is the canonical
  bytes, destination from the card; report schema TBD (§11 Q3); transcripts committed to the repo
  (SHOULD).
- **The book (Ch9, Appendix F Table 20):** four files per game, common `game_uid`, per-game filenames:
  1. `declaration_<game_id>.json` — pre-game, **cryptographically signed**: teams, members, both repo
     URLs, both MCP URLs, hardware specs, LLM model, token cap. **A7:** signing = each team's own
     **Ed25519 keypair** (`ed25519:base64-signed-blob` in the declaration schema); public keys exchanged
     and locked into the declaration before play (no staff key; SHA-256 commit-reveal covers only the
     hardware record's computational-fairness commitment). **Rule 37 / A9(b):** the
     **counted-games-so-far declaration MUST appear INSIDE this signed JSON** (anti diversity-reward
     reset / 10-game-cap bypass).
  2. `config_<game_id>_g<NN>.json` — per-sub-game locked parameters, committed to the repo.
  3. `log_<game_id>_g<NN>.json` — the sealed commit-reveal chain with post-audit nonces.
  4. `result_<game_id>.json` — **the mandatory JSON attachment emailed by BOTH groups separately** to
     `rmisegal+uoh26finalgame@gmail.com` (rules 32–35, 49, 52; attachment, never free text, else 0;
     missing/contradictory report = 0 to both). Must carry all 4 repo links, per-sub-game commit hashes,
     total tokens.
- **Gaps in the card:** no members/repos/MCP URLs/hardware/LLM/token cap (declaration fields), no
  Ed25519 signature, no counted-games declaration, no per-game config files, no sealed log artifact, and
  the report is a body not an attachment with a card-supplied destination. The `stage` interlock is the
  right *safety* layer but the official destination is fixed by Appendix F — when `stage:"official"`,
  implementations must verify `report_email` equals the official address, not merely obey the card.
- **Resolution:** keep the card's agreement/transport split as the *negotiation front-end*, then compile
  it into the four book artifacts: agreement → signed config; transport + identity + counted-games count
  → Ed25519-signed declaration; their two-phase `report_sha` confirm → the mutual-agreement gate before
  both sides email `result_<game_id>.json` as an attachment.

### (e) Appendix-F fixed/minimum values vs placeholders

Their §4.1 admits the values are placeholders; here is what v1.0 must pin (Appendix F status law:
**fixed** = never change; **minimum** = negotiable upward only):

| Card field (example value) | Appendix F | Verdict |
|---|---|---|
| `grid: [10,10]` | Table 13: board **7×7 minimum** | legal (≥ min); note the §6.4 fixtures include n=5 boards — fine as math vectors, illegal as league cards |
| `rounds: 25` | Table 15: move ceiling / survival threshold **35 minimum** | **illegal — below minimum**; also wrong *unit*: the book counts the **thief's OWN valid-step counter** (A5: STAY/HOLD count toward the 35; the cop's barrier turns do NOT add to it), not "rounds = thief ply + cop ply" |
| `max_barriers: 0` | Table 15: barrier quota **14 minimum**, cop-only | **illegal — barriers cannot be disabled**; the cop's asymmetric power is core mechanics. **A3:** 5 placement options (own cell + 4 orthogonal), and rules **46** (barrier-on-thief = capture) and **47** (jailed thief = capture) are **MANDATORY** in league play — our engines must implement them even against reference-based peers that lack them |
| scoring (absent from card) | Table 17: **all fixed** — capture 20/5, survival 5/10, tie 2/2, technical loss 0/0 | must appear in the signed config and be asserted, not trusted |
| `num_games: 6` | Table 18: **fixed 6** | already correct — keep |
| `timeouts: 120 s/ply, 1800 s/sub-game` | Table 19: per-request timeout **30 s** (negotiable), watchdog freeze **60 s** (negotiable) | negotiable, so 120/1800 are *legal if agreed* — but a stock book/reference peer watchdogs at 60 s while a card-peer thinks it has 120 s → false timeout losses. Pin explicitly per match; book defaults unless both sides opt up |
| gatekeeper values (absent) | Table 19 minimums: 30 req/min, 2 parallel, 5 s retry, 3 retries, queue 100 | must be carried in the shared config (`rate_limiter_gatekeeper` block in the reference schema) |
| §8.3 void → re-run | Table 17 + **A6**: timeout/crash = result string `"technical_loss"`, scores **0/0**, and the surviving peer **MUST still run the audit and email the result JSON** | void-and-rerun silently erases a book-mandated 0/0 outcome and its mandatory report. Keep re-runs for *pre-game* failures (nothing began, per their own §4.3 logic); once a sub-game has started, a technical failure is recorded as technical_loss 0/0, audited, and reported. **A9(a):** audit-caught tampering = adjudicated technical loss 0/0, both groups must still report; failing to report a caught forgery risks total disqualification |

### (f) Role alternation: `swap_at` midpoint vs the reference's odd/even

- **Their spec:** sub-games `0..swap_at-1` = group_1 cop, then swap (§4.1, card `swap_at: 3` → AAABBB).
- **The reference simulator:** alternation every sub-game — odd sub-games = natural role, even = swapped
  (ABABAB; reference_map §2.4). The book fixes 6 sub-games but does not fix the alternation pattern —
  **negotiable, but it must be pinned in the signed config**: a mismatch means both peers boot as cop
  (or both as thief) in sub-game 2 and the series deadlocks or desyncs undetectably until the audit.
- **Resolution:** add `role_pattern: "alternate" | "halves"` to the agreed terms; default `alternate`
  (what stock reference peers do without modification).

### (g) `deliver_message` single-tool mailbox vs the reference 4-tool wire

- **Their spec:** one public tool `deliver_message(text) -> ack`; prose + fenced single-line JSON trailer;
  all typing (`hello`/`move`/`report_sha`) inside the trailer.
- **The reference simulator (the wire the professor's own code speaks, and the default for every team
  that builds on it):** exactly 4 tools — `negotiate` / `receive_turn` / `submit_audit` (param key
  `payload`!) / `receive_control`, structured dict bodies, strict `from_dict` parsers
  (TurnMessage **rejects unknown top-level keys**), signed-terms handshake with exact dict equality
  (reference_map §3; INTEROP §2).
- **Can both coexist?** Technically yes — both are dumb-mailbox-over-FastMCP with local-only enforcement,
  and transport is per-pair (a match card could name the dialect). But practically the league cannot
  carry two wire dialects: a stock reference peer cannot parse a fenced-trailer string, and their client
  cannot call `receive_turn`. Every pairing would re-open the negotiation their repo exists to kill.
- **Assessment: v1.0 should rebase onto the reference 4-tool wire as the de-facto baseline.**
  Reasons: (1) it is what the professor's simulator speaks — the only implementation every team can test
  against today; (2) teams that extend the reference get conformance for free, so it minimizes
  league-wide work; (3) we have already byte-verified its every hash against the professor's sample-run
  artifacts (INTEROP §3, §6.1 — 19/19 log records, declaration/log/result signatures, config lock,
  game_uid). What survives the rebase intact: the prose channel (TurnMessage `hint` is exactly their
  above-the-fence prose), hold-don't-advance, dedup-by-commit, byte-identical resend, and the
  `prev`/`prev_recv` DAG — with one placement fix: since TurnMessage rejects unknown top-level keys, the
  chain fields must ride **inside the sealed commit payload** (extra keys inside audit-record payloads
  are interop-safe — the auditor recomputes from the record's own payload + nonce; INTEROP §2.3/D9),
  giving the DAG for free at audit time without breaking a stock peer.

---

## 3. Verdict on their §11 open questions — now answerable

1. **Exact scent mechanic?** Book Ch4 + Appendix F Table 16 (all fixed): each agent's move/stay emits a
   **5×5 field** around it — 0.9 at center, radial falloff (reference: Chebyshev rings 0.9/0.6/0.3,
   3-dp) — and after every full turn the whole board decays by
   `τ(t+1) = max(0, (1−ρ)·τ(t) + Δτ)`, ρ = 0.10 (**A2:** the multiplicative book law is the reference
   standard; the repo's subtractive/max-merge is adoptable ONLY as a mutually-agreed, Step-0-locked
   upgrade — rule 23 requires exchanging formula + numeric example and hashing it). The **emitter
   computes its own grid and broadcasts it** in every turn message; the receiver Bayes-fuses it with the
   (possibly lying) hint. So the answer to "Mode B vs a different observability model" is: **a different
   model — scent-grid broadcast, not delayed position reveal** (see conflict (a); Mode B as drafted
   should be retired or renumbered as a non-league mode).
2. **Board / rounds / scoring / barriers?** Board 7×7 **minimum**; survival threshold and move ceiling
   **35 minimum**, adjudicated on the **thief's own valid-step counter** (A5: STAY/HOLD count; cop
   barrier turns don't add). Scoring **fixed**: capture 20/5, survival 5/10, tie 2/2, technical loss 0/0
   (Table 17). Barriers: cop-only, quota **14 minimum**, irreversible, **5 placement options** (own cell
   + 4 orthogonal — A3), mandatory truthful declaration, and **rules 46/47 (barrier-on-thief capture,
   jailed-thief capture) are mandatory** (A3). `max_barriers: 0` is not a legal card.
3. **Report schema + destination?** Fixed by Ch9/Table 20: the four artifacts of conflict (d);
   the emailed object is `result_<game_id>.json` **as a JSON attachment**, sent **by both groups
   separately** to `rmisegal+uoh26finalgame@gmail.com` (general/repo mail: `rmisegal@gmail.com`).
   **A6:** on timeout/crash the surviving peer must **still audit and email**, result string
   `"technical_loss"`, scores 0/0. **A9(a):** caught forgery → sub-game adjudicated 0/0, both groups
   still report; not reporting a caught forgery risks total disqualification. Their two-phase
   `report_sha` confirm slots in cleanly as the pre-email mutual-agreement gate.
4. **Does the assignment constrain shared league services?** No — and the book affirmatively blesses the
   space: p.34, the contract is a floor, not a ceiling; undefined-space conventions are "permitted and
   even desirable" when legal and mutually agreed. Appendix B (lobby, demo league, sink, sparring,
   fixture rounds) is fair game, with two guardrails: services stay passive (Zero-Trust, A4), and nothing
   in them substitutes for the signed declaration / dual separate reports (rules 32–37).
5. **Tournament structure?** No pre-dictated schedule in the book (Ch9: the league runs live). The actual
   scoring structure (Table 18, all relevant to fixtures): **one counted game per opponent** (warm-ups
   free and encouraged), **diversity reward 10 fixed** per win vs a NEW opponent, **≥2 counted games vs
   different groups to pass**, **≤10 counted games**, 6 sub-games per series fixed. There is no published
   diminishing-returns formula; the order-dependence is via diversity + caps + the truthful
   counted-games declaration, which **rule 37 / A9(b) requires INSIDE the Ed25519-signed pre-game
   declaration**. Their synchronized fixture rounds are therefore genuinely useful and legal — and the
   sparring server should be explicitly *non-counted* (a warm-up peer) so it never eats anyone's 10-game
   budget.
6. **Commit-reveal per-ply, per-game, or both?** Both, precisely: **A8** — stages 1–3 (Commit,
   Acknowledge, Reveal move/hint — nonce withheld) run **sequentially every turn**; stage 4 (Final
   Audit) is a **single end-of-game reveal of all nonces**. The commitment covers
   `{state, move, intent, nonce}` with the nonce inside the canonical JSON (**A1**), not position-only.
   Mode A's immediate nonce reveal violates rule 18; the §6.2 construction needs the (b) upgrade.

---

## 4. Proposed GitHub issues (ready to paste)

Tone: we are co-authors of the league standard, not critics; every issue offers artifacts, not just asks.

---

### Issue 1 — Mode C: scent-grid broadcast — the official observability model (Modes A/B can't be the counted-game wire)

The official rules are out, and they answer §11 Q1 in a way that affects §7 directly: the environment is
a Dec-POMDP whose only observations are the opponent's **decaying scent grid + free-language hints**
(book Ch3/Ch4; Appendix F Table 16 fixes emission 0.9, ρ=0.10, 5×5 field). Positions are revealed only
at the **final audit** nonce reveal, and rule 27 forbids numeric-location protocols. "Adaptation
(scent-based belief)" is one of the four graded axes — so cleartext `move` (Mode A) or lag-k exact
positions (Mode B) on a counted game's wire would remove the graded mechanic for both teams.

Proposal for v1.0:

- Add **Mode C (default for counted games):** each move message carries the sender's own decayed 5×5
  `smell_grid` (`{"r,c": intensity}`, cells > 0 only), the ≤15-word hint, and the commit; `move: null`;
  nonces withheld until one end-of-game audit (book 4-stage flow: Commit → Ack → Reveal move/hint →
  Final Audit).
- Keep Mode A as a **sparring/debug** disclosure level (it's excellent for integration tests — lockstep
  replicas catch desyncs instantly); match cards with `disclosure:"A"` and `stage:"official"` should be
  rejected.
- Retire Mode B or mark it non-league (its open capture-detection question is now moot — capture is a
  cop `capture_claim` that the thief is crypto-obligated to answer truthfully, verified at audit).

The scent law itself must be locked pre-series under rule 23 (formula + worked numeric example, hashed).
The professor's chatbot confirms the book's multiplicative law `τ(t+1)=max(0,(1−ρ)τ+Δτ)` is the
reference standard, and that a mutually-agreed alternative is legal if exchanged and locked at Step 0.
We have a config-selectable implementation of both laws and a worked numeric example ready to
contribute as a fixture.

---

### Issue 2 — Commit construction: seal `{state, move, intent, nonce}` with the nonce inside the canonical JSON; withhold nonces until the final audit

Two rule-book requirements affect §6.2/§7:

1. **What is sealed.** The book's per-step commitment is
   `H_commit = SHA256(canonical_json({"state":…, "move":…, "intent":…, "nonce":…}))` — the **intent
   (truth/lie) flag is inside the seal**. That's the lie-detection mechanic: the audit later proves what
   the sender *committed to* about its own hint's honesty. A `{nonce, pos}` commit audits the trajectory
   but not the deception layer. (The full sealed record in the professor's simulator also carries step,
   hint, verdict-duplicate, prompt_discussion, and token counters.)
2. **When nonces reveal.** Rule 18: nonces stay secret until the single end-of-game audit. Mode A's
   immediate `nonce` field would need to become `null` until audit (see Issue 1's Mode C).

Also worth pinning while we're in this file: the professor's simulator canonicalizes with
`ensure_ascii=False` (Hebrew hints hash as raw UTF-8), §2 currently says `ensure_ascii=True` — same
object, different digests for any non-ASCII hint. And the simulator's own commit is pipe-appended
(`sha256(canonical_json(payload) + "|" + nonce)`), which the professor's chatbot calls a "simplified
sketch" — the book's nonce-inside form is authoritative for cross-audits. Since both constructions
exist in the wild, we suggest v1.0 name them explicitly and default to the book form. We have worked
byte-level vectors for both dialects from the same payload (they share nothing — an unnegotiated
mismatch reads as 100% tampering) and are happy to PR them into `vectors/`.

---

### Issue 3 — No-floats rule vs Appendix F: ρ=0.10 and intensity 0.9 are league-mandated floats inside signed objects

§2's float rejection is built on a real scar (the hand-typed `7.5`) and we endorse the diagnosis. But
Appendix F Table 16 **fixes** `emit_intensity: 0.9` and `decay: 0.10`, the scent grids on the wire carry
3-dp float intensities every turn, and hardware specs (`ram_gb: 63.5`) sit in the signed declaration —
so the league's own mandatory data cannot pass a conformant-to-§2 canonicalizer. `vectors/negative.json`
currently rejects `0.1`, which is literally the league's decay constant.

Two resolutions, either works — we'd like the league to pick one:

- **(A) Pinned-float exemption (our preference — zero drift from the professor's simulator):** floats
  are permitted in hashed objects **iff** they round-trip through JSON (`loads` → `dumps`), pinning
  shortest-repr semantics identically in Python and ECMAScript (`0.10` → `0.1`); scent intensities are
  additionally pinned by 3-dp rounding at emission. We've byte-verified this against the professor's
  sample-run artifacts (config hash, 19/19 sealed records with float token/latency fields).
- **(B) Scaled integers:** per-mille encoding (`decay_permille: 100`, `intensity_millis: 900`). Cleaner
  cross-language, but byte-incompatible with an unmodified reference peer, so it only works as a
  league-wide locked upgrade under rule 23.

Either way, the float *rejection* stays exactly right for trailer-native values (positions, counters).

---

### Issue 4 — Match card v1.0: compile into the four mandatory artifacts, Ed25519-sign the declaration, and carry the rule-37 counted-games declaration

The assignment fixes a four-artifact record per game (Ch9, Appendix F Table 20) — the match card maps
onto it beautifully but needs three additions:

1. **Declaration** (`declaration_<game_id>.json`): pre-game, signed, holding both teams' members, repo
   URLs (cop+thief ×2), MCP URLs, hardware specs, LLM model, token cap. Signing is **Ed25519** — each
   team its own keypair, public keys exchanged and locked into the declaration before play
   (`ed25519:<base64-signed-blob>`); no staff-distributed key. **Rule 37**: each team's
   *counted-games-played-so-far* number must appear **inside** this signed JSON (it feeds the
   diversity-reward and 10-game-cap accounting; a false or absent declaration is a disqualification
   risk). The card's `agreement`/`transport` split survives intact: agreement → the signed per-game
   `config_<game_id>_g<NN>.json`, transport + identity + counted-count → the declaration.
2. **Result email** (`result_<game_id>.json`): the destination is fixed by the assignment
   (`rmisegal+uoh26finalgame@gmail.com`), the result goes as a **JSON attachment** (free text scores 0),
   and **both teams email separately**. So: when `stage:"official"`, implementations should verify
   `report_email` equals the official address rather than just obeying the card — the `stage` interlock
   itself is exactly right and we'd like to keep it verbatim. §9's "exact canonical bytes" rule becomes
   "the attachment MUST be the exact canonical bytes that were hashed."
3. **Failure semantics**: once a sub-game has started, timeout/crash is `"technical_loss"` 0/0 and the
   surviving peer must **still audit and email** (professor's chatbot ruling). §8.3's void/re-run should
   apply only to failures before ply 0 (nothing began — same logic §4.3 already uses for handshake
   mismatch). Audit-caught tampering: adjudicated 0/0, and both teams must still report it.

We can contribute our field-verified schemas for all four artifacts (validated byte-for-byte against
the professor's sample run), including the symmetric-outcome-subset trick that lets both teams'
independently-emitted result files agree byte-identically.

---

### Issue 5 — Pin the Appendix-F values and the role-swap pattern in the v1.0 card

Now that the parameter table is out, the placeholder values need updating — several current examples
are below mandated minimums (Appendix F: *fixed* = never change, *minimum* = negotiable upward only):

| Field | v0.3 example | Appendix F |
|---|---|---|
| `rounds` | 25 | move ceiling / survival **35 minimum** — and counted on the **thief's own step counter** (its STAY/HOLDs count toward 35; the cop's barrier turns do not add to it), not in thief+cop round pairs |
| `max_barriers` | 0 | **14 minimum**, cop-only; placement = own cell + 4 orthogonal (5 options); **barrier-on-thief = capture and jailed-thief = capture are mandatory league rules (46/47)** |
| scoring | absent | **fixed** 20/5 capture, 5/10 survival, 2/2 tie, 0/0 technical — belongs in the hashed agreement so both engines assert it |
| `timeouts` | 120 s / 1800 s | book defaults 30 s per-request / 60 s watchdog, negotiable — fine to raise by agreement, but must be pinned: a stock book-peer watchdogs at 60 s while a card-peer waits 120 s → false timeout losses |
| gatekeeper block | absent | Table-19 minimums (30 rpm / 2 parallel / 5 s retry / 3 retries / queue 100) ride in the shared config |
| `num_games: 6`, `grid: [10,10]` | — | already legal (6 fixed; 7×7 is the minimum) — no change |

One addition: the reference simulator alternates roles **every sub-game** (odd = natural, even =
swapped), while the card's `swap_at` swaps once at the midpoint. Both are legal — the book doesn't pin
it — but an unpinned mismatch means both peers boot as cop in sub-game 2. Propose
`role_pattern: "alternate" | "halves"` in the hashed agreement, default `"alternate"` (stock-peer
behavior).

---

### Issue 6 — Offer: byte-verified golden vectors from the professor's sample run, as the v1.0 interop baseline (and a proposal to rebase v1.0 transport onto the reference 4-tool wire)

We've spent the past weeks byte-verifying the professor's reference simulator — the wire that his own
code (and any team that builds on it) already speaks. Offer: we contribute our golden vector set to
`vectors/` (or a `vectors/reference-wire/` folder), machine-recomputed on 2026-07-13 against the
sample-run artifacts shipped in his repo:

- **Per-step commits:** 19/19 sealed records (incl. the step-0 hardware-spec record) recompute exactly
  under `sha256(canonical_json(payload) + "|" + nonce)`, `ensure_ascii=False` — plus a paired
  same-payload vector for the book's nonce-inside dialect, so both constructions are pinned side by side.
- **The two coexisting canonical hashers:** compact separators for commits/config/`game_uid` vs Python
  *default spaced* separators for `consensus_signature` fields (declaration signatures, log + result
  mutual-agreement hashes) — mixing them fails silently; all verified against the sample files.
- **`game_uid` derivation:** non-RFC UUID from `sha256(canonical(terms)|gid1|gid2)[:16]`, worked example
  included.
- **Envelope fixtures:** the 4 tools (`negotiate` / `receive_turn` / `submit_audit` — note its argument
  key is `payload`, not `message` — / `receive_control`), the signed-terms exact-equality handshake, and
  the strict TurnMessage/AuditPayload field contracts.

On that basis, a proposal for the §3 transport in v1.0: **rebase onto the reference 4-tool wire as the
de-facto league baseline.** It's the only wire every team can integration-test against today (the
professor's simulator speaks it out of the box), and teams extending his repo become conformant for
free — which serves this repo's own goal of killing pairwise negotiation. Everything that makes v0.3
strong survives the rebase: the prose channel (the TurnMessage `hint` field is exactly the
above-the-fence prose), hold-don't-advance, dedup-by-commit, byte-identical resend — and the
`prev`/`prev_recv` transcript DAG, which we'd love to keep: it can ride **inside the sealed commit
payload** (extra keys there are audit-safe — the auditor recomputes each commit from the record's own
payload + nonce), giving the interlocked-DAG guarantee at audit time without breaking a stock peer,
whose TurnMessage parser rejects unknown top-level keys. `deliver_message` could remain specified as an
optional side-channel for prose-only traffic if the league wants it.

Happy to pair on the PR — vectors, `verify_vectors.py` checks, and a worked reference-wire exchange for
`examples/`.

---

## 5. Recommended posture for our team (adopt / extend / rebase matrix)

| Component (their spec) | Posture | Action |
|---|---|---|
| Lobby repo, demo league, `stage` interlock, report sink, synchronized fixture rounds, sparring server (App. B) | **Adopt** | Say yes loudly; register in their lobby; request `stage`-verification of the official address (Issue 4) and non-counted status for sparring |
| Hold-don't-advance, dedup-by-commit, byte-identical resend (§5.2/§8.2) | **Adopt** | Implement the same invariants on the reference wire (fixes the reference's own no-dedup landmine, INTEROP §1/landmine 8) |
| `prev`/`prev_recv` transcript DAG (§5.2) | **Extend** | Carry the two chain fields inside our sealed step payload (audit-safe extra keys, INTEROP §2.3); propose as a league-wide locked upgrade |
| Email-exact-bytes + two-phase report confirm (§9) | **Adopt (amended)** | Attachment, not body; both teams separately; keep never-reserialize as a hard invariant next to the symmetric-subset mutual signature we already verified |
| `agreement`/`transport` split (§4.1) | **Adopt (recompiled)** | Use as negotiation front-end that compiles into the 4 book artifacts + Ed25519 declaration (Issue 4) |
| Joint-seed coin flip + seed-derived starts (§4.2/§6.4) | **Extend (optional)** | Book makes starts negotiable config values in signed terms; seed-derived starts are a legal locked upgrade — support it behind a term (`start_mode: "fixed"|"seed"`), default `fixed` (stock-peer compatible) |
| Canonical JSON, `ensure_ascii=True`, no-floats (§2) | **Amend** | Align `ensure_ascii` with the reference (`False`) or pin per-field; pinned-float exemption for config/scent/spec values (Issue 3); keep float-rejection for int-native fields |
| Position commit `{nonce,pos}` (§6.2) + Mode A nonce-now | **Rebase** | Book H_commit over `{state,move,intent,nonce}`, nonce inside canonical JSON (A1); nonces withheld until final audit (rule 18, A8). We ship both dialects config-selectable; default book |
| Mode A / Mode B disclosure (§7) | **Rebase** | Mode C scent-grid broadcast for counted games (Issue 1); Mode A relegated to sparring/debug |
| `deliver_message` transport (§3) | **Rebase** | v1.0 on the reference 4-tool wire (Issue 6); our engine speaks the reference wire natively either way — their adoption decision does not block us |
| Match-card values (§4.1) | **Rebase** | Appendix-F-compliant defaults (Issue 5); assert fixed values in code, never trust config alone |
| Void/re-run (§8.3) | **Amend** | Pre-ply-0 failures: re-run. Started sub-games: `technical_loss` 0/0, audit still runs, both teams email (A6, A9a) |
| State-hash per-ply desync check (§6.3) | **Extend (optional)** | Not in the book (which detects divergence only at audit) — a legitimate early-warning upgrade IF the state frame excludes hidden info under Mode C (barriers + counters are public via mandatory declarations; positions are not). Worth co-designing a Mode-C-safe frame with them |
| Their conformance-kit model (vectors + stdlib verifier + CI regen) | **Adopt the pattern** | Mirror it for the reference wire: our golden vectors + G1–G8 tests (INTEROP §6.1) become the league's second fixture set (Issue 6) |

**Bottom line.** Their draft solves the part of the league the book leaves open — coordination,
conformance, settlement discipline — and solves it well (all 53 vectors pass; the kit regenerates
cleanly). It predates the official rules, so its game-facing layer (observability, commit contents,
float ban, artifact set, parameter values) now needs a rebase onto Appendix F / the 4-stage
commit-reveal / the four signed artifacts, and its transport should converge on the professor's 4-tool
wire that we have byte-verified end-to-end. We should engage as co-authors: endorse Appendix B and the
wire-discipline rules publicly, file Issues 1–6, and contribute our golden vectors so v1.0 has two
independently-verified fixture sets — theirs for canonicalization and settlement, ours for the
reference wire the league will actually speak.
