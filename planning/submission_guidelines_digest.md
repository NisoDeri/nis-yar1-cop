# Submission Guidelines Digest — software_submission_guidelines-V3.pdf

Source: **"Guidelines for Writing Professional Software at the Highest Level of Excellence"**
(הנחיות לכתיבת תוכנה מקצועית ברמת הצטיינות יתרה), Dr. Yoram Segal, **version 3.00, 2026-03-26**, 39 pp., Hebrew.
Per the final-project book, the ENTIRE submission (code, structure, docs, process) is graded against
this document — it is the **5th grading criterion** (DECISIONS.md D11).

## The document's own meta-rules (read first — this calibrates every severity below)

- **§19 Important Note (verbatim-faithful):** *"This document presents an especially high level of
  excellence. Not every clause is fully mandatory (לא כל סעיף הוא מחויב במלואו), but the more
  criteria are met, the higher the quality assessment will be. Focus on depth, professionalism, and
  demonstrating high-level development capability. It is recommended to use LLM tools and AI agents
  to help complete the project. It is clarified that, as part of the grading, AI agents may be used
  to perform the review (יתכן וייעשה שימוש בסוכני AI לביצוע הבדיקה)."*
- **§2 opening:** *"Without these documents the project will NOT be considered as meeting minimum
  requirements"* (ללא מסמכים אלו הפרויקט לא ייחשב כעומד בדרישות המינימום) — i.e., README + docs/
  are a hard floor despite §19's softening.
- **There is NO numeric grading formula and NO self-score mechanism anywhere in this PDF.** The only
  quantified gates are in Table 5 (§19.1, reproduced below). Grade-formula details must come from the
  final-project book / professor (already queued in NOTEBOOKLM-QUESTIONS.md line 66).
- **AI-agent-usage content:** (a) §1.4 — Vibe Coding: one programmer orchestrates AI agents like a
  Senior Software Architect, "16x more quality code lines"; *"the first and most important rule: to
  exploit AI agents' full potential, you MUST define clear and detailed requirements... define and
  demand full documentation before any line of code"*; (b) §8.3 — the Prompt Book (see item 24);
  (c) §19 — AI agents may grade the submission (so structure/naming conventions must be machine-findable).

### Table 5 — §19.1 Quick reference card (סיכום דרישות איכות קוד), verbatim-faithful

| Rule (כלל) | Threshold (סף) | Enforcement (אכיפה) |
|---|---|---|
| SDK architecture | ALL logic through SDK | code review |
| OOP / no duplication | extract at 2+ copies | code review |
| API Gatekeeper (שומר סף) | ALL external calls through it | code review + test |
| Rate limits | from config, not code | config check |
| Overflow handling | queue, not crash | integration test |
| Version control (בקרת גרסאות) | starts at 1.00 | version module |
| TDD | RED–GREEN–REFACTOR | work process |
| File size | ≤150 lines | automated check |
| Linter | 0 Ruff violations | `ruff check` |
| Test coverage | ≥85% | `pytest --cov` |
| Hardcoded values (ערכים מוטבעים) | 0 in source code | code review |
| Secrets | 0 + `.env-example` | automated scan |
| Package manager | everything through `uv` | automated check |

Severity legend: **HARD** = explicit חובה / Table-5 gate / "not minimum-compliant without it";
**REC** = recommendation ("מומלץ", quality-ladder item per §19).

---

## Checklist

### Ch. 2 — Mandatory project structure & documentation (מבנה פרויקט חובה)

1. **README.md in repo root at full user-manual level** (§2.1): must contain (i) Installation
   Instructions — system requirements, step-by-step install, env-var setup, troubleshooting;
   (ii) Usage Instructions — run modes, CLI/GUI flags, typical workflow; (iii) examples & demos —
   code samples, screenshots, common scenarios (appendix §20.2 adds "links to videos");
   (iv) Configuration Guide — config files, parameters and their effect; (v) Contribution
   Guidelines — code/style standards; (vi) License & Credits — license + third-party attribution.
   - *Ours:* D11/prd.md plan an "academic report" README (Dec-POMDP, MCP dilemmas, strategies,
     screenshots, cross-link) in both deliverable repos; INTEROP.md documents run commands.
     **Add:** the six user-manual sections above as an explicit README template for BOTH repos —
     especially troubleshooting, configuration guide, contribution guidelines, and License & Credits
     (attribution to the reference simulator is also an EULA obligation, reference_map "License").
   - **HARD** (project "not minimum-compliant" without it).

2. **`docs/` folder with `docs/PRD.md`** (§2.2): project overview & context, user problem, market/
   audience, measurable goals + KPIs + acceptance criteria, functional & non-functional
   requirements, user stories, assumptions/dependencies/constraints/out-of-scope, timeline &
   milestones.
   - *Ours:* planning/prd.md already has this shape (stakeholders, FR-*, acceptance checklist).
     **Add:** ship it as `docs/PRD.md` (exact path/name — an AI grader will look for it) in each
     deliverable repo, role-trimmed.
   - **HARD**.

3. **`docs/PLAN.md`** (§2.2): architecture & technical design containing **C4 Model diagrams
   (Context, Container, Component, Code)**, **UML diagrams** for complex flows, **deployment
   diagrams**, **ADRs** (architectural decision records) with rationale/trade-offs/alternatives,
   API & interface documentation, data schemas and contracts.
   - *Ours:* architecture.md (ASCII layer diagram, file budgets), DECISIONS.md (D1–D13 = real ADRs
     with rationale), INTEROP.md (wire contracts/schemas), plan.md. **Add:** render explicit
     C4-labelled diagrams (Mermaid renders on GitHub) + one UML sequence diagram (turn loop /
     commit-reveal) + a deployment diagram (two peers, ngrok, Gmail), assembled into `docs/PLAN.md`.
   - **HARD** (docs/ trio is the minimum floor); diagram formats themselves REC-leaning but cheap.

4. **`docs/TODO.md`** (§2.2): detailed task list with priorities and status (not-started /
   in-progress / done), phase breakdown with milestones, responsibility assignment per task,
   definition-of-done per task.
   - *Ours:* planning/todo.md (500–1000 granular tasks, phased). **Add:** status + owner (Nissim/
     Yarden) columns and per-phase DoD; ship as `docs/TODO.md`, kept updated during development
     (§2.5 step 6 requires updating it with progress).
   - **HARD**.

5. **Dedicated PRD per algorithm/mechanism** (§2.3): every specific algorithm, central mechanism, or
   complex technical component gets its own `docs/PRD_<mechanism>.md` with theoretical background,
   specific requirements, expected I/O, performance metrics, constraints, alternatives considered +
   why chosen, success criteria and specific test scenarios.
   - *Ours:* 7 stage PRDs (planning/prd/PRD-1..7) + STRATEGY.md (belief/brains deep design) — the
     content exists. **Add:** re-cut into the mandated naming convention in `docs/`, e.g.
     `PRD_belief_engine.md`, `PRD_commit_reveal.md`, `PRD_gatekeeper.md`, `PRD_scent_model.md`,
     `PRD_hint_reliability.md` — each with the "alternatives considered" and "expected I/O" sections.
   - **HARD** ("דרישה חשובה", part of the docs/ floor).

6. **Recommended project tree** (§2.4): `src/<package>/` (with `sdk/`, `services/`, `shared/`
   containing `gatekeeper.py`, `config.py`, `version.py`, plus `constants.py`), `tests/unit/` +
   `tests/integration/`, `docs/`, `config/` (`setup.json`, `rate_limits.json`), `data/`,
   `results/`, `assets/`, `notebooks/`, `README.md`, `pyproject.toml`, `uv.lock`, `.env-example`,
   `.gitignore`.
   - *Ours:* architecture.md matches src/tests/config largely (gatekeeper, config.py, version,
     rate_limits.json, game.toml). **Add:** `notebooks/`, `assets/` (screenshots/diagrams),
     `results/` (lab outputs — currently `lab/results/`, fine but mirror or symlink naming), and
     a `constants.py`. `game.toml` instead of `setup.json` is fine (appendix §20.3 allows
     .json/.yaml/.env formats).
   - **REC** (tree is "מומלץ"), but the marked-MANDATORY leaves (docs/, README, pyproject, uv.lock,
     .env-example, .gitignore) are **HARD**.

7. **Mandatory workflow order** (§2.5, verbatim-faithful): 1) create docs/PRD.md — and approve it
   before continuing; 2) docs/PLAN.md; 3) docs/TODO.md; 4) dedicated PRDs per algorithm/mechanism;
   5) approve ALL documents before development starts; 6) start development — update TODO.md with
   progress; 7) save results, create visualizations, update README.md.
   - *Ours:* D11's Vibe-Coding lifecycle (initial → PRD → plan → TODO → verify → execute → push) is
     exactly this. **Add:** make the "approval" step visible in git history (docs committed and
     tagged/PR-approved BEFORE first src commit — order of commits is auditable by an AI grader).
   - **HARD** (titled "תהליך עבודה חובה").

### Ch. 3 — Code documentation & structure

8. **Modular structure** (§3.1): logical folder split by role (source/tests/docs/data/results/
   config/assets); feature-based or layered architecture; clear code/data/results/docs separation.
   - *Ours:* layered (domain/peer/infra/shared/strategy) — covered. **HARD-ish** (review axis).

9. **150-line file rule** (§3.2): no code file exceeds **150 lines of code — blank lines and
   comment lines DO NOT count**. When over: split, "never compress code to fit". Named splitting
   strategies: extract helpers, extract mixin, 50/50 split, extract constants to `constants.py`,
   extract models. Applies to test files too (§6.1 rule 6).
   - *Ours:* covered aggressively (≤140 budget with headroom, CI line-budget gate, plan.md R7).
     Note the counting rule (code lines only) — make the CI checker skip blanks/comments so we don't
     over-split. **HARD** (Table 5, automated).

10. **Comment & docstring standards** (§3.3): comments explain the **"why" not just the "what"**;
    detailed docstrings on EVERY function, class, and module; comments document design decisions,
    assumptions, preconditions; kept up to date. Descriptive naming, short single-responsibility
    functions, DRY, consistent style.
    - *Ours:* implied by ruff+review but not written down. **Add:** a docstring convention line in
      CONTRIBUTING.md (T0.35) + ruff `D` rules or a review checklist item. **HARD** (review axis).

### Ch. 4 — SDK architecture & OOP

11. **SDK layer = single entry point** (§4.1): every business-logic function is reachable through an
    SDK class; GUI/CLI/controllers contain NO business logic — they delegate to the SDK; external
    consumers can import the SDK and drive everything without touching internal modules.
    - *Ours:* D5 "Single Orchestrator entry (SDK)". **Add:** an actual `sdk/` module exposing the
      façade (start_peer, run_series, replay, lab) and a README note that CLI/GUI call only the SDK —
      graders check for the layer by name. **HARD** (Table 5).

12. **OOP, zero duplication** (§4.2): duplicate function body in 2+ files → extract shared module;
    same try/except pattern in 3+ files → wrapper function; identical method in 3+ classes → base
    class or mixin; near-duplicates → Template Method. Mixin rules: one concern per mixin, no
    override collisions, independently testable.
    - *Ours:* single shared engine in both repos (D2) is the biggest DRY win; BrainBase/ScentModel
      protocol design conforms. **HARD** (Table 5: extract at 2+ copies).

### Ch. 5 — API Gatekeeper & rate control

13. **Central API Gatekeeper** (§5.1): ALL external API calls pass through one gatekeeper handling
    rate limiting, queues, retries, monitoring. No direct API calls bypassing it; limits enforced
    BEFORE each call; overflow **queued, not rejected**; every call logged. Reference interface:
    `ApiGatekeeper(config).execute(api_call, ...)` + `get_queue_status()`.
    - *Ours:* D5 3-gate Gatekeeper (daily quota → token-bucket → DOS/circuit-breaker) in front of
      Gmail AND LLM — exceeds spec. Check: T7.10 currently says overflow "rejected" at max queue
      depth — the guideline's letter is "queue, not reject"; document that rejection only happens at
      the configured max-depth backpressure bound (which §5.3 itself allows). **HARD** (Table 5).

14. **Rate limits from config, never hardcoded** (§5.2): JSON with `"version"`, per-service
    `requests_per_minute` / `requests_per_hour` / `concurrent_max` / `retry_after_seconds` /
    `max_retries`.
    - *Ours:* `config/<role>/rate_limits.json` with services map (gmail/llm) — covered. **HARD**.

15. **Queue management for overflow** (§5.3): FIFO queue for waiting requests; max queue depth from
    config; backpressure alert when full; drain mechanism when rate windows reset.
    - *Ours:* queue depth 100 in config, drain semantics — covered; add the backpressure log/alert.
    - **HARD** (Table 5 integration test).

### Ch. 6 — TDD & quality assurance

16. **TDD RED–GREEN–REFACTOR** (§6.1): tests written before/with the code, never after; every module
    has a matching test file (tests/ mirrors src/); every public function/method has ≥1 test; happy
    path AND error cases; fixtures in `conftest.py`; **mock all external dependencies** (DB, files,
    API); **no tests depending on external services**; test files also ≤150 lines.
    - *Ours:* todo.md interleaves test tasks with impl tasks; "tests use injected fakes (no
      network/model in CI)" is stated policy. **Add:** tests/unit mirror-structure convention +
      conftest.py fixtures named in todo. **HARD** (process + Table 5).

17. **Coverage ≥85%, suite fails below** (§6.2): global coverage ≥85%; enforced via
    `[tool.coverage.report] fail_under = 85`; `[tool.coverage.run] source=["src"]`, omit pattern
    shown includes `src/main.py`, `*/tests/*`, `src/**/gui/*` (GUI may be excluded!). Statement +
    branch coverage, path coverage for critical paths.
    - *Ours:* D11 pytest ≥85%, CI gate T0.14/T0.55. **Add:** put `fail_under = 85` literally in
      pyproject.toml and use the sanctioned GUI omit for the Tkinter window. **HARD** (Table 5).

18. **Edge cases & failures** (§6.3): systematically identify boundary conditions; document every
    edge case with detailed description; **include screenshots of faults where relevant**; defensive
    programming, clear error messages, detailed logging, graceful degradation.
    - *Ours:* fail-fast physics, timeout=technical-loss, template fallback — strong. **Add:** a
      documented edge-case catalog (e.g., `docs/EDGE_CASES.md` or PRD sections) with expected
      input→response pairs, plus fault screenshots. **REC→HARD** (appendix restates it as required).

19. **Expected test results** (§6.4): document expected outcome per test; produce automated test
    reports with pass/fail rates; keep logs of successful AND failed runs.
    - *Ours:* not planned. **Add:** CI artifact (pytest junit/HTML report) + a `results/test_reports/`
      snapshot in the submission. **REC**.

### Ch. 7 — Linting, configuration & security

20. **Zero Ruff violations** (§7.1): all code passes `ruff check` with 0 errors; config in
    pyproject.toml: `line-length = 100`, `target-version = "py310"`,
    `select = ["E","F","W","I","N","UP","B","C4","SIM"]`, `ignore = ["E501"]`.
    - *Ours:* exact same select-list in D11/plan.md/todo T0.8 — covered. **HARD** (Table 5).

21. **No hardcoded values** (§7.2): every configurable value from config files. Verbatim table:
    API URLs → `cfg.get("api_url")` not literals; rate limits → `cfg.get("rate_limit", 10)`;
    timeouts → `cfg.get("timeout", 60)`; secrets → `os.environ.get("API_KEY")`. Allowed in code:
    physical/mathematical constants, parameter defaults, constants in `constants.py`, Enum values.
    - *Ours:* D4 "all from config, nothing hardcoded" + CI no-hardcoded gate (T0.14). **HARD**.

22. **Config architecture** (§7.3): clear hierarchy, versioned config files: `config/setup.json`,
    `rate_limits.json`, `logging_config.json`, `.env` (git-ignored), `.env-example` (committed),
    pyproject.toml, `src/<pkg>/constants.py`.
    - *Ours:* game.toml + rate_limits.json versioned & validated (architecture.md config.py
      "version-gated"). **Add:** `logging_config.json` (we do heavy structured logging anyway) and
      `constants.py`. **HARD** for versioning+separation; the specific extra files **REC**.

23. **Secrets** (§7.4): NO secret data in the project; on GitHub push a `.env-example` with dummy
    values is mandatory; no API keys/passwords/tokens in source; env vars only; `.gitignore` must
    include `.env`, `*.pem`, `*.key`, `credentials.json`; periodic key rotation, usage monitoring,
    least privilege.
    - *Ours:* D9 Gmail credentials outside repo + .gitignored; D11 `.env-example`. **Add:** the
      exact four .gitignore patterns (we use `credentials.json`/`token.json` for Gmail OAuth — must
      be listed) and a secret-scan step in CI (Table 5 says "automated scan"). **HARD**.

### Ch. 8 — Versioning, Git, prompts, uv

24. **Global version tracking** (§8.1): code AND config carry explicit versions, **starting at
    1.00**, bumped on significant change. Required locations (Table 2): `src/<pkg>/shared/version.py`
    = 1.00; `"version"` key in every JSON config = 1.00; `rate_limits.version` = 1.00. App must
    **validate config-version compatibility at startup**.
    - *Ours:* shared/version.py + version-gated config loader in architecture.md — covered; note
      the private game.toml is version "1.10" for reference parity (document why it isn't 1.00).
    - **HARD** (Table 5).

25. **Git best practices** (§8.2): clear commit history with meaningful messages; separate feature
    branches; **code reviews via Pull Requests**; tagging for major versions.
    - *Ours:* D11 feature branches + conventional commits + annotated tag `v1.0-submission`;
      CONTRIBUTING.md (T0.35). **Add:** actually open PRs between the two of us (reviewer =
      partner) so the PR-review trail exists in both deliverable repos. **REC** wording, but Git
      history is on the final checklist — treat as **HARD-lite**.

26. **The Prompt Book (ספר הפרומפטים)** (§8.3): document the AI-assisted development process — a
    Prompt Engineering Log listing all significant prompts used to build the project, context and
    goal of each, examples of received outputs, iterative refinements, and best practices learned.
    - *Ours:* **NOT PLANNED anywhere.** Add `docs/PROMPTS.md` per repo; start capturing now (this
      session's planning prompts qualify). Appears again in final checklist §17.1 — **HARD**.

27. **uv package manager — mandatory** (§8.4): uv is THE package manager and task runner. Forbidden:
    `pip`, `pip install`, `python -m`, `venv`, `virtualenv` directly. Verbatim command table:
    install deps `uv sync` (not pip install); add dep `uv add <pkg>`; run script
    `uv run python script.py`; run tests `uv run pytest tests/`; lock `uv lock` (not pip freeze).
    Requirements: pyproject.toml is the single source of truth (NO requirements.txt); `uv.lock`
    committed; no pip/python -m calls in code, scripts, CI/CD **or documentation**; all tools via
    `uv run`.
    - *Ours:* fully adopted (todo T0.4-6, all commands `uv run python -m pursuit ...` — the `-m` is
      fine because it goes through `uv run`). Double-check no bare `python`/`pip` sneaks into README
      or CI. **HARD** (Table 5, automated).

### Ch. 9 — Research & results analysis

28. **Parameter study / sensitivity analysis** (§9.1): systematic experiments with controlled
    parameter variation; precise documentation of each parameter's effect; methods such as partial
    derivatives, variance-based analysis, or **one-at-a-time (OAT)**; appendix adds experiment
    table + illustrative graphs + statistical analysis.
    - *Ours:* D7 simulation lab (hundreds of games, ablations, parameter sweeps, win-rate tables,
      heatmaps) — strong fit. **Add:** frame one sweep explicitly as OAT sensitivity analysis
      (e.g., reliability-coefficient λ, scent-trust weight, cage-trigger threshold) with a stats
      table. **REC** (but this is the "excellence differentiator" chapter — §9 opening says research
      is what separates ordinary projects from excellence-level work).

29. **Results Analysis Notebook** (§9.2): Jupyter Notebook (or similar) with methodical analysis of
    experiment results, comparison between algorithms/configurations, mathematical proofs or
    theoretical analyses, **LaTeX for equations**, **citations to academic literature**.
    - *Ours:* **NOT PLANNED** (lab outputs tables/heatmaps but no notebook). Add
      `notebooks/analysis.ipynb`: belief-update math in LaTeX (STRATEGY.md §2 already has the
      equations), brains-vs-reference win-rate comparison, ablation plots, Dec-POMDP citations.
      **REC**, high grade leverage.

30. **Visualization quality** (§9.3): bar charts (comparisons), line charts (trends), scatter
    (correlations), heatmaps (parameter sensitivity), box plots (distributions), waterfall
    (change analysis); clear labels, consistent accessible colors, detailed captions + legend, high
    resolution. Tools named: Matplotlib, Seaborn, Plotly, Tableau, D3.js.
    - *Ours:* heatmaps + win-rate tables planned (D7). **Add:** at least one of each core type in
      the notebook/README; caption+legend discipline. **REC**.

### Ch. 10 — UI/UX

31. **Usability criteria** (§10.1): learnability, efficiency, memorability, error prevention,
    satisfaction; **Nielsen's 10 heuristics** listed in full (system-status visibility, real-world
    match, user control & freedom, consistency & standards, error prevention, recognition over
    recall, flexibility & efficiency, aesthetic & minimalist design, error recovery, help & docs).
    - *Ours:* Tkinter live window + web replay UI (D10). **Add:** a short UI section mapping our two
      UIs to the relevant Nielsen heuristics (cheap, reviewer-visible). **REC**.

32. **Interface documentation** (§10.2): screenshots of EVERY screen and state; typical user
    workflow description; interaction & feedback explanations; accessibility considerations.
    - *Ours:* the two mandatory screenshots (belief heatmap, "Verified OK") planned. **Add:**
      full screen/state gallery (live window states, replay app, web dashboard) + workflow
      narrative in README/`docs/UI.md`. **REC**.

### Ch. 11 — Costs & pricing

33. **Token cost analysis** (§11.1): exact input/output token counts, cost per million tokens,
    total cost per model/service — presented as a table (the doc's Table 4 shows a per-model
    Input/Output/Total-cost breakdown). Optimization strategies: token reduction, batch processing,
    cost-effective model choice.
    - *Ours:* token totals already flow through the game artifacts (D9), and D8's zero-token default
      IS the optimization strategy — but **no cost-analysis table is planned**. Add a README/notebook
      section: tokens consumed per series (both sides, from artifacts), $0.00 actual cost (local
      Ollama + Claude login), hypothetical API-price comparison, and the every_n_steps/template-
      fallback throttles as the optimization narrative. **REC** (final checklist §17.5 lists it).

34. **Budget management** (§11.2): cost forecast at scale, real-time usage monitoring, budget-overrun
    alerts.
    - *Ours:* daily-quota gate in the Gatekeeper ≈ budget alert; document it as such. **REC**.

### Ch. 12–16 — Extensibility, standards, packaging, parallelism, building blocks

35. **Extension points / plugin architecture** (§12.1): new functionality without touching core —
    clear extension interfaces, lifecycle hooks, middleware, API-first design; documented extension
    points (final checklist §17.6).
    - *Ours:* the `[strategy]` brain-loader seam (`load_brain_cls("module:Class")`), ScentModel
      protocol/factory, TrashTalk provider contract, dialect switches — genuinely plugin-shaped.
      **Add:** document them as named Extension Points in PLAN/README. **REC**.

36. **Maintainability** (§12.2): modularity & separation of concerns, component reuse,
    analyzability, testability. — Covered by architecture; **REC**.

37. **ISO/IEC 25010 compliance** (§13): eight quality characteristics — functional suitability,
    performance efficiency, compatibility, usability, reliability, security, maintainability,
    portability.
    - *Ours:* not referenced. **Add:** a one-page mapping table (README or PLAN) of project features
      to the eight characteristics (e.g., dialect engine → compatibility; watchdog+technical-loss →
      reliability; commit-reveal → security). **REC** (final checklist item).

38. **Package organization** (§14): `pyproject.toml` (preferred) with name/version/description/
    author/license/deps; `__init__.py` in every package folder, exporting public interfaces via
    `__all__` and defining `__version__`; **relative imports / package names only — never absolute
    paths**, file I/O relative to package path; §14.4 self-check list.
    - *Ours:* pyproject planned; `__init__.py` files exist as re-export stubs. **Add:** `__all__` +
      `__version__` in the top package; audit that config/log paths are resolved relative to package
      or CWD-config, not absolute. **HARD-lite** (checklist-verifiable).

39. **Parallel processing & thread safety** (§15): choose multiprocessing for CPU-bound,
    multithreading for I/O-bound; protect shared variables with locks, use `queue.Queue`, avoid
    deadlock, use context managers; §15.3 checklist (dynamic worker counts, safe sharing, clean
    shutdown, no leaks, no races).
    - *Ours:* FastMCP daemon-thread server + thread-safe `queue.Queue` inboxes + watchdog; lab could
      use multiprocessing for hundreds of games (CPU-bound — say so). **Add:** a thread-safety
      paragraph in PLAN.md naming the shared structures and their protection. **REC**.

40. **Building-blocks design** (§16): every component defined by Input Data (types, valid domain,
    external deps, validation), Output Data (types, format, edge-case behavior), Setup Data
    (parameters with defaults, config, init); single responsibility, separation of concerns,
    reusability, testability via dependency injection; docstring style shown documents
    Input/Output/Setup explicitly and validates config+input in `__init__`/entry.
    - *Ours:* dependency-injected brains (`__init__(llm, rng, trash)`), validated config — conforms.
      **Add:** adopt the Input/Output/Setup docstring convention for the ~10 core classes. **REC**.

### Ch. 17 — Final pre-submission checklist (§17, condensed — every bullet above appears here)

41. §17.1 structure/docs: README user-manual level; docs/ with PRD+PLAN+TODO; per-algorithm PRDs;
    architecture docs with clear diagrams; **documented prompt book**. §17.2 architecture/code: SDK
    layer; OOP no-duplication; Gatekeeper; config-driven rate limits + queue; ≤150-line files;
    docstrings; style consistency. §17.3 tests: TDD; ≥85%; 0 ruff; edge-case docs; automated
    reports. §17.4 config/security: versioned config; .env-example; no secrets; .gitignore; uv only;
    pyproject+uv.lock. §17.5 research: systematic experiments; documented sensitivity analysis;
    analysis notebook with graphs; quality graphs/screenshots/architecture diagrams; **token cost
    analysis + optimization**. §17.6 extension/standards: documented extension points;
    professional Python packaging; parallelism with thread safety; building-blocks; ISO 25010;
    tidy Git history, license, attribution, **deployment instructions**.
    - Use this section verbatim as the submission-day gate runbook (map onto D12 buffer days).
    - **HARD** as a process step.

### Ch. 18 — External standards (REC): MIT SQA plan, ISO/IEC 25010, Google Engineering Practices,
Microsoft REST API Guidelines, Nielsen heuristics — cite 1–2 of these in PLAN.md for the
"excellence" signal.

---

## installation-guide.pdf — grading-relevant notes only

A 4-page pre-course tool-setup letter (March 2026), no grading formula or submission mechanics.
Grading-relevant implications only:
- Expected toolchain the professor assumes: **Claude CLI + Claude account (login, not API key)**,
  Gmail account + **Gmail API via Google Console**, GitHub + Git, **Python 3.13** (matches todo
  T0.3 pin), NotebookLM, MikTeX/LaTeX, Notepad++, Manus, Perplexity, Gemini.
- Nothing else actionable; it confirms our zero-API-key posture (D8) and the Gmail-API reporting
  path (D9) are the sanctioned mechanisms.

---

## DELTA LIST — requirements the planning suite does not yet cover

Ordered by severity, then leverage:

1. **Prompt Book (`docs/PROMPTS.md`, §8.3 + final checklist)** — a documented Prompt Engineering
   Log is mandatory-listed and appears NOWHERE in our planning. Start logging immediately (HARD).
2. **docs/ folder repackaging in BOTH deliverable repos** — exact names `docs/PRD.md`,
   `docs/PLAN.md`, `docs/TODO.md`, `docs/PRD_<mechanism>.md`; our content exists under planning/
   with non-conforming names/paths; an AI grader will match on the mandated names (HARD).
3. **Docs-approved-before-code auditability (§2.5)** — commit/tag the doc suite in the deliverable
   repos BEFORE the first src commit so the mandatory workflow order is visible in history (HARD).
4. **TODO.md live status + per-task ownership + definition-of-done** — todo.md has neither status
   columns, owner assignment, nor DoD; §2.2 requires all three, updated during development (HARD).
5. **README user-manual sections** — troubleshooting, configuration guide, contribution guidelines,
   License & Credits (incl. reference-simulator attribution) are not yet in the README plan; and a
   **LICENSE file + deployment instructions** (final checklist §17.6) are unplanned (HARD).
6. **Results Analysis Notebook (`notebooks/analysis.ipynb`, §9.2)** — Jupyter + LaTeX equations +
   academic citations + algorithm comparisons; lab (D7) produces the data but no notebook exists in
   any plan; `notebooks/` dir absent from architecture (REC, high leverage).
7. **Token cost analysis table + budget narrative (§11, checklist §17.5)** — artifacts carry token
   totals but no cost table / per-model pricing / optimization write-up is planned (REC).
8. **Explicit C4 + UML + deployment diagrams in PLAN.md (§2.2)** — we have ASCII layer diagrams and
   ADRs, but no C4-labelled set, no UML sequence diagram, no deployment diagram (HARD-floor doc,
   diagram form REC).
9. **Edge-case catalog with expected input→response and fault screenshots (§6.3–6.4)** — plus
   automated test reports (pass/fail rates) and stored run logs; none scheduled in todo.md (REC→HARD).
10. **Secret-scan + exact .gitignore patterns (§7.4)** — `.env`, `*.pem`, `*.key`,
    `credentials.json` must be listed; add automated secret scan to CI (Table 5 "automated scan");
    current plan gitignores Gmail creds but doesn't pin these patterns or a scanner (HARD-lite).
11. **`logging_config.json` + `constants.py` (§7.3, §2.4)** — config architecture names both; neither
    appears in architecture.md's file inventory (REC).
12. **Package polish (§14)** — `__all__` + `__version__` in top `__init__.py`; verify no absolute
    paths; pyproject author/license/description fields (HARD-lite, checklist-verifiable).
13. **PR-based partner code reviews (§8.2)** — branches and commits are planned, PRs with reviews
    between Nissim/Yarden are not explicit; do them in the deliverable repos too (REC).
14. **ISO/IEC 25010 mapping table + Nielsen-heuristics UI section + full screenshot gallery
    (§10, §13, checklist §17.6)** — none planned beyond the two mandatory screenshots (REC).
15. **OAT sensitivity-analysis framing + statistical table for one lab sweep (§9.1)** — lab sweeps
    exist but are not framed/documented as formal sensitivity analysis (REC).
16. **Named SDK façade module (§4.1)** — D5 declares an SDK entry, but architecture.md's file
    inventory has no `sdk/` module; graders look for the layer by name (HARD per Table 5).
17. **Input/Output/Setup docstring convention + thread-safety documentation (§15–16)** — adopt for
    core classes and document shared-structure protection in PLAN.md (REC).
18. **Gatekeeper queue-vs-reject wording (§5.1/T7.10)** — align the overflow test/doc with
    "queue, not reject; backpressure alert at max depth" so the letter of Table 5 is met (HARD-lite).
