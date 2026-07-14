# USER-TASKS — what Nissim (and Yarden) must do

Everything not on this list, Claude does. Items are ordered by when they block progress.

## Now (this week — unblocks implementation)
1. ~~**NotebookLM**: paste Q1–Q10 into the professor's chatbots.~~ **DONE (2026-07-13)** — all
   ten questions answered and integrated (DECISIONS.md rulings log A1–A9, D3 flip, new D14).
   Only the grade-formula question remains open — ask the professor directly (WhatsApp/forum).
2. **ngrok — the paid account was DELETED. That's fine; nothing to do now.** Tunneling is needed
   only at Stage 5 (~Jul 27): either open a fresh ngrok account when league play nears, or use a
   free **named Cloudflare tunnel** (stable hostname, path-route `/cop/mcp` + `/thief/mcp` —
   field-proven by another team). Both paths are documented in `LEAGUE-OPS.md` §2 step 4;
   decision deferred to Stage 5.
3. **WhatsApp pod (4 pairs)**: send the intro message (template in `LEAGUE-OPS.md` §5a) —
   introduce group nis-yar1, propose a warm-up window in week Aug 3–9, and ask each pair which
   codebase they're building on (reference-derived or own) + which commit-hash construction they
   use. Their answers feed our dialect defaults.
4. **WhatsApp — league-protocol draft**: respond in the group re the pod's draft league protocol
   (github.com/Imreec/copthief-league-protocol). We prepare the reply text (our analysis:
   `LEAGUE-PROTOCOL-REVIEW.md`); you just paste it.
5. **Downloads — nothing further needed.** The course grading-baseline files are already on disk:
   `software_submission_guidelines-V3.pdf` and `installation-guide.pdf` (course folder root).

## Soon (when code stabilizes, ~week of Jul 27)
6. **GitHub**: create the two deliverable repos (proposed: `nis-yar1-cop`, `nis-yar1-thief`) —
   or just authorize me and I'll create + populate them. Share both with `rmisegal@gmail.com`
   (or make public).
7. **Gmail OAuth**: our HW6 send-only token (`nissimderi123@gmail.com`) should still work —
   I'll verify; if it expired you'll re-consent in the browser once (2 minutes).
8. **Ollama**: nothing to do — qwen2.5:7b and aya-expanse:8b are already pulled.

## League week (Aug 3–9)
9. **Schedule games**: coordinate exact times with each pair on WhatsApp (game-day template in
   `LEAGUE-OPS.md`). Be present during games (start the peer, watch the UI; I prep everything
   scripted). Target: warm-up + 1 counted game vs each of the 3 pairs.
10. **Confirm mutual results**: after each counted game, confirm on WhatsApp that both sides
    email the SAME result JSON (a mismatch = 0 for both, rule 34–35).

## Submission (Aug 10–12, deadline Aug 12 23:59 — no lateness)
11. **Moodle Word template**: download the NEW final-project template (different from earlier
    HWs), fill fields only (never move/rename them), save as `nis-yar1-exNN.pdf` — **each member
    submits separately**. Group code: `nis-yar1` (exactly 8 chars, no spaces ✓).
12. **Screenshots** (mandatory in both READMEs): live GUI belief heatmap + replay "Verified OK".
    I'll generate them scripted; if Tkinter capture misbehaves on your machine you take 2 manual
    screenshots (30 seconds).
13. **Self-score** (code quality ONLY per rule 55): we decide together at the end — evidence-backed,
    following the HW1 lesson (high score ⇒ harsher review).

## Standing offers (optional, helpful)
- ~~The course-intro grading-baseline file — please download.~~ **FOUND (2026-07-13)**: the
  grading-baseline files are `software_submission_guidelines-V3.pdf` and
  `installation-guide.pdf` in the course folder root — I'll audit our repos against them clause
  by clause. Nothing further to download.
- Any Moodle announcement about the league schedule / grade formula — paste it to me as text.
  (The Q7 signing-key question is RESOLVED: no staff key, we use our own Ed25519 keypair, D14.)
