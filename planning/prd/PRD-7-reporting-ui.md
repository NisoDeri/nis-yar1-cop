# PRD-7 — Reporting + Visualization Shell (Book Ch9+Ch7+App. A; roadmap stage 7)

## Purpose
The outermost shell, built last because it consumes every layer beneath it (brief §14.7):
autonomous **Gmail reporting** behind a 3-gate Gatekeeper, the four **JSON artifacts**, the
**live GUI** (belief heatmap, local truth only) and the **replay verifier** whose "Verified OK"
screenshot is a mandatory submission item.

## In scope
- Gmail OAuth 2.0 send-only sender (ported from our working HW6 sender, D9).
- 3-gate Gatekeeper (quota → token-bucket → DOS circuit-breaker) in front of Gmail and the LLM.
- Four JSON artifacts, reference schema 1.1, with the reference's emission gaps fixed (D9).
- Tkinter live window + replay app; web replay dashboard as creativity extension (D10).
- League bookkeeping surface (counted-game declaration, diversity tracking — D13).

## Out of scope
Strategy changes (frozen for counted games), wire changes (frozen since PRD-2), the optional
Hebrew report (nice-to-have parity item, not gating).

## Functional requirements

### Reporting (rules 30–35; Table 20)
- **FR-7.1 Gmail sender.** OAuth 2.0 **send-only scope** (rule 30); result JSON as an
  **attachment, never free text** (rule 33), to `rmisegal+uoh26finalgame@gmail.com`; sent
  autonomously by the agent at each legal game end (rule 32); each group sends separately —
  mutual agreement precondition verified first (rules 34, 49, 52). Credentials/token outside the
  repo, `.gitignore`d (rules 39–40).
- **FR-7.2 3-gate Gatekeeper (rules 28–29; Table 19; D5).** Cumulative, fail-fast, in front of
  Gmail AND the LLM: (1) daily Quota Manager; (2) token-bucket
  `tokens ← min(C, tokens + r·Δt)`, allow ⟺ tokens ≥ 1 — the book's bucket, not the reference's
  sliding window; (3) DOS detector locking the API path on abnormal send patterns
  (circuit-breaker). HTTP 429 ⇒ back off to the next window, never blind-retry;
  `retry_after_seconds` actually slept; `concurrent_max` enforced (reference gap #19).
- **FR-7.3 Four artifacts (Table 20; schema 1.1).** `declaration_<game_id>.json`,
  `config_<game_id>_g<NN>.json`, `log_<game_id>_g<NN>.json`, `result_<game_id>.json` — shared
  `game_uid`, written to `logs/<own_group_id>/`. Fixes over the reference (D9; gaps #14–15):
  real `github_commit` per sub-game, all **4 repo links in the result**, real token totals both
  sides, mutual-agreement SHA over the **symmetric-only subset** (reference_map §2.6 trick —
  keep byte-exact), both canonical hashers replicated exactly per field (compact vs spaced
  separators, landmine #7).
- **FR-7.4 League bookkeeping.** Truthful count of already-played counted games declared at game
  start (Table 18; disqualification for false declaration); counted/warm-up flag, per-opponent
  history, diversity-reward tracker.

### Visualization (Ch7; rules 8–9, 20)
- **FR-7.5 Live window.** Tkinter: own position, own barriers, opponent's smell overlay, and the
  **belief heatmap** (mandatory screenshot); **local truth only, never the objective board**
  (rules 8–9) — enforced structurally: render path receives no opponent position.
- **FR-7.6 Replay verifier.** Steps through a saved `log_*.json`, rebuilds belief from RECORDED
  smell grids, re-verifies every commit via the PRD-6 dialect-aware core, auto-discovers the
  opponent's sibling log, and shows a **prominent "Verified OK" banner** (the reference has only
  a per-step label — gap; rule 20 screenshot needs the banner). Accepts both log dialects; a
  missing audit is reported as UNVERIFIED, never defaulted to passed (reference_map §2.6
  warning).
- **FR-7.7 Web replay dashboard (creativity extension, D10).** HW6 web replay UI ported to
  render finished games from `log_*.json` — post-game only, so no info-leak rule risk.
- **FR-7.8 Docs closure.** `docs/RESEARCH-REPORT-Performance-Analysis.md` (LLM-call volume vs
  provider limits; fallback guarantees every sub-game finishes — brief §15) and `docs/STRATEGY.md`
  (lab-backed, D7); README academic-report components in both deliverable repos (brief §13).

## Acceptance criteria (testable)
1. **Runs end-to-end (the full product):** a complete remote series plays under crypto, then —
   with zero human action — both peers write all four artifacts and our agent emails the signed
   result JSON attachment through the Gatekeeper; message lands with valid JSON attached.
2. Artifact schema tests: golden fixtures validate all four against reference schema 1.1 incl.
   `_schema` prose, filenames, `links` placeholders, both hashers; two independently-emitted
   result files from a real game agree byte-identically on the mutual-agreement SHA.
3. Gatekeeper tests (fake clock, fake Gmail): daily quota blocks; bucket smooths a burst; DOS
   gate locks on a send loop; 429 path sleeps and recovers; nothing reaches the fake API after
   lock.
4. UI leak test: object graph reachable from the live-render path contains no opponent-position
   field; screenshot artifacts (belief heatmap + "Verified OK") captured and stored for the
   READMEs.
5. Replay verifier: tampered log from the PRD-6 tamper test shows FAILED on the exact step; clean
   log shows the banner.
6. CI: no network, no Gmail, no Ollama — injected fakes throughout; gates: ≤150 lines/file, ruff,
   coverage ≥85%.
7. Submission dry-run: master-PRD §6 checklist walked once on a warm-up game before any counted
   game (D13).

## Dependencies
PRD-6 (verification core, sealed logs), PRD-5 (remote play), PRD-4 (belief for the heatmap,
token totals), HW6 Gmail OAuth sender + web replay UI (team assets, reference_map §11).

## Risks
- Gmail quota/429 during the league window → Gatekeeper gates + send-once-per-game design keep
  volume trivial; drafts-then-send fallback documented in the runbook.
- Hasher mix-ups (compact vs spaced) silently breaking mutual signatures → per-field golden
  tests pinned to reference fixtures (landmine #7).
- Screenshot forgotten until deadline week → captured automatically at the end of every lab/warm-up
  run from PRD-7 completion onward.
