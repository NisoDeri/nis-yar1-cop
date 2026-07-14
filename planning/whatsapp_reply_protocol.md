# WhatsApp reply — league-protocol thread (paste as-is or trim)

Hey Imree, nis-yar1 here (Nissim + Yarden) 👋

First — huge respect for the protocol repo. We cloned it, ran `verify_vectors.py` — **53/53 pass**,
and the engineering lessons in it are real: the `prev`/`prev_recv` transcript DAG, hold-don't-advance,
byte-identical resends, the "email the exact hashed bytes" rule, the `stage` interlock. We're in. 🤝

We also spent this week deep in the official material, and we think v1.0 needs one big rebase now
that the book is binding. We verified everything below against the 160-page book (v3.0.0,
Appendix F), the professor's reference simulator, and his NotebookLM chatbots — happy to share
receipts:

1. **The game wire already has a de-facto standard: the professor's own simulator.** It speaks a
   4-tool FastMCP protocol (`negotiate` / `receive_turn` / `submit_audit` / `receive_control`),
   and every team that starts from his repo speaks it out of the box. We suggest v1.0 adopts that
   wire as the baseline transport and keeps your league layer (lobby, demo season, fixture rounds,
   transcript chaining) on top — best of both.
2. **Mode A can't be a counted game.** Cleartext `move:[r,c]` kills the partial observability the
   project is graded on (belief maps from scent are the core "Adaptation" axis). The book's
   observability model IS the wire answer to your §11-Q1: broadcast a **5×5 decaying scent grid**
   each turn + free-language hints; true positions come out only at the final-audit nonce reveal.
3. **Commit construction is ruled.** Per the professor's NotebookLM: the commit seals
   `{state, move, intent, nonce}` with the **nonce INSIDE the canonical JSON** (chapter-5 schema),
   nonces withheld until the final audit. `intent` (truth/lie) can't be omitted — it's the
   lie-detection mechanic. Also note `ensure_ascii`: the reference wire uses `False`; any Hebrew
   hint gives different digests than your `True` — worth a vector.
4. **The no-floats rule collides with the league's own config** — ρ=0.10 and intensity 0.9 are
   *mandated* floats inside signed objects, and scent grids carry floats every turn. Needs a
   pinned-float rule (JSON round-trip repr — matches the professor's sample run) or a scaled-int
   convention.
5. **Settlement = the book's 4 artifacts**, not a match card + body email: Ed25519-signed
   declaration (which must carry each team's counted-games count — rule 37), per-game
   `config_<game_id>_g<NN>.json`, sealed log, and the result JSON emailed **as an attachment by
   both teams separately** to the fixed lecturer address. Your two-phase `report_sha` confirm
   slots perfectly *before* that send.
6. Small but scoring-critical: `rounds: 25` → 35 minimum (counted on the *thief's own* moves —
   STAY counts, cop barrier turns don't); `max_barriers: 0` → 14 minimum; barrier-on-thief and
   jailed-thief captures are mandatory; scoring is fixed 20/5, 5/10, tie 2, technical 0/0.

We wrote all of this up with citations + we have **byte-verified golden vectors generated from the
professor's own sample-run artifacts** (19/19 commit records reproduced, both hash dialects, the
`game_uid` derivation, envelope fixtures). We'll open issues on the repo with the details and
we're offering the vectors as the v1.0 interop baseline.

And +1 on both proposals: **demo league first** (with the automated report-sink checker) and
**synchronized fixture rounds**. We'd add one thing to the roster file: each team's chosen
hash/scent dialect + Ed25519 public key, so match cards can be generated with zero surprises.

Who else is starting from the reference simulator vs own code? That decides how much of the
4-tool wire we all get "for free".
