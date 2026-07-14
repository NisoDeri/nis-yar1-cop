# NotebookLM Questions — ALL ANSWERED (2026-07-13)

Two chatbots exist: **[BOOK]** = the rule-book notebook, **[CODE]** = the simulator-code notebook.
**Status: Q1–Q10 ANSWERED on 2026-07-13** — rulings integrated into DECISIONS.md (D3 update, new
D14, rulings log A1–A9), INTEROP.md, LEAGUE-OPS.md, STRATEGY.md and PRD-6. The only OPEN item is
the grade-formula question at the bottom (for the professor directly, not NotebookLM).

---

**Q1 [BOOK] — hash construction (gates our crypto module):**
"The book's reference commit function puts the nonce INSIDE the canonical JSON
(`SHA256(canonical_json({state, move, intent, nonce}))`), but the reference repo computes
`sha256(canonical_json(payload) + '|' + nonce)`. Which construction is authoritative for league
cross-audits — or is the hash construction itself a term both groups must negotiate and lock
before the series?"
> **ANSWERED (2026-07-13, A1):** the BOOK construction (nonce inside the canonical JSON, chapter-5
> schema) is authoritative for league cross-audits; the reference's pipe-appended form is a
> "simplified sketch" → our default flipped to `book` (D3), dialect A kept for stock-reference peers.

**Q2 [BOOK] — scent formula lock (gates our scent module):**
"Rule 23 requires locking the scent model before each series. If both groups mutually agree to
use the reference repo's subtractive decay and max-merge deposit instead of the book's
multiplicative equation τ(t+1)=max(0,(1−ρ)·τ+Δτ), is that a legal 'upgrade' — or are the book's
emission/decay equations fixed like the Table 16 parameters?"
> **ANSWERED (2026-07-13, A2):** the book multiplicative equation is the reference standard; the
> reference subtractive/max-merge is a LEGAL mutually-agreed upgrade if exchanged + crypto-locked
> at Step-0 (rule 23). Priority = both peers byte-identical → our default flipped to `book` (D3).

**Q3 [BOOK] — the two missing captures + 5th barrier option (gates our rules module):**
"Must the cop be able to place a barrier on its own current cell (5 placement options total)?
And are barrier-on-thief capture (rule 46) and jailed-thief capture (rule 47) mandatory in every
league game, even when playing against a peer built on the reference simulator, which implements
neither?"
> **ANSWERED (2026-07-13, A3):** yes — 5 placement options (own cell + 4 orthogonal); rules 46/47
> are MANDATORY in league play (marked mandatory in the master parameter table) — implement even
> vs stock-reference peers. Confirms D4; surfaced early in the LEAGUE-OPS onboarding checklist.

**Q4 [BOOK] — identical shared engine across the two repos (gates our release plan):**
"May the cop and thief GitHub repos share an identical engine codebase (same package, different
config dirs, different strategy modules and entry roles), or does Zero-Trust require the two
repos to contain independently developed code?"
> **ANSWERED (2026-07-13, A4):** identical engine/SDK package is allowed; Zero-Trust requires
> separate OS processes, separate config dirs (config/police vs config/thief) and no shared
> memory/live state — not independently-developed code. Confirms D2.

**Q5 [BOOK] — survival counting:**
"For the thief's survival threshold of 35 valid moves: do STAY/HOLD actions and the cop's barrier
turns count toward the 35, and is survival adjudicated on the thief's own step counter or on a
shared turn count?"
> **ANSWERED (2026-07-13, A5):** STAY/HOLD are valid moves and COUNT toward the thief's 35; the
> cop's barrier turns do NOT add; survival is adjudicated on the thief's OWN valid-step counter.
> STRATEGY §4/§4.5 hedges removed; still confirmed per-series at onboarding.

**Q6 [BOOK] — timeout endings:**
"If a peer times out or crashes mid-game, the book mandates technical loss 0/0 — must the
surviving peer still run and email the cryptographic log audit for that sub-game, and what
result string goes in the result JSON?"
> **ANSWERED (2026-07-13, A6):** yes — the surviving peer MUST still run the audit and email the
> result JSON; result string `"technical_loss"`, scores 0/0. Confirms D4; INTEROP §5.5 fix #4.

**Q7 [BOOK] — step-0 signing key:**
"Rule 24 says the hardware declaration is 'signed cryptographically with a pre-supplied key' —
will a key be distributed by the course staff, or does the reference repo's nonce-based SHA-256
commit-reveal of the spec record satisfy this rule?"
> **ANSWERED (2026-07-13, A7):** no staff-distributed key. Teams use their own Ed25519 keypair
> (`ed25519:base64-signed-blob` in the declaration schema); pubkeys exchanged + locked into the
> signed pre-game declaration. SHA-256 commit-reveal of the hardware record still satisfies
> computational fairness; declaration signing = Ed25519 → new decision D14.

**Q8 [BOOK] — 4-stage protocol strictness:**
"Is the literal 4-stage per-step protocol (Commit → Acknowledge → Reveal → Final Audit) required,
or is the reference repo's compressed flow — per-turn commit with a single end-of-game reveal of
all nonces — compliant?"
> **ANSWERED (2026-07-13, A8):** the compressed flow is COMPLIANT — stages 1–3 (Commit,
> Acknowledge, Reveal move/hint) happen sequentially every turn; stage 4 (Final Audit) = single
> end-of-game reveal of all nonces. Validates PRD-6 FR-6.4 staging as-is.

**Q9 [BOOK] — forgery scoring + counted-game bookkeeping:**
"(a) When a post-game audit catches tampering, what exact scores go in the result JSON for a
forgery ending, and must both groups still email matching results? (b) Who records which series
against a given opponent is the counted one — must the counted-games-so-far declaration appear
inside the signed declaration JSON or only in the negotiation?"
> **ANSWERED (2026-07-13, A9):** (a) audit-caught tampering ⇒ the sub-game is adjudicated
> technical loss 0/0 (`technical_loss`); both groups must still report — failing to report a
> caught forgery risks total disqualification. (b) rule 37: the counted-games-so-far declaration
> MUST appear INSIDE the cryptographically signed pre-game declaration JSON → D14.

**Q10 [CODE] — turn-loop internals (implementation aid):**
"Walk through one full turn on the wire: which peer initiates, the exact order of
negotiate/receive_turn calls, what the TurnMessage seal covers, when belief/smell updates are
applied, and where a timeout is detected. Then explain how the series loop swaps roles between
sub-games and how game_uid is derived."
> **ANSWERED (2026-07-13):** the walkthrough matched what INTEROP.md already documents from the
> source survey — symmetric handshake, thief moves first, seal covers the chapter-5 payload,
> game_uid per INTEROP §3.2 — no contradictions; the compressed staging is compliant per A8.

---

## Grade-formula question for the professor directly (WhatsApp/forum, not NotebookLM) — **OPEN, the only remaining item:**
"How do league placement (75–100), the code-quality review, and the computational-fairness bonus
combine into the final project grade? And is the HW6-bonus (+ up to 10) added on top of 100?"
