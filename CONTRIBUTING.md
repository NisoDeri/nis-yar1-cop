# Contributing — the Vibe-Coding lifecycle & course gates

This repo is built with the **Vibe-Coding** lifecycle (the 5th grading axis: process). Every
capability walks the same path before it merges; every merge clears the same hard gates. Group
`nis-yar1` (Nissim Deri, Yarden Tziar), Orchestration of AI Agents, Dr. Yoram Segal.

## 1. The lifecycle

```
initial ──► PRD ──► plan ──► TODO ──► verify ──► execute ──► push
```

1. **initial** — capture the raw intent and constraints in `planning/initial.md`.
2. **PRD** — a master PRD plus per-stage PRDs (`planning/prd/`) turn intent into a signed-off spec:
   what, why, acceptance criteria, book-rule citations.
3. **plan** — `planning/plan.md` sequences the PRDs into stages with explicit file ownership so
   parallel work never collides.
4. **TODO** — `planning/todo.md` explodes the plan into small, checkable tasks (hundreds of them);
   nothing is coded that isn't a TODO first.
5. **verify** — before writing code, state how the change will be proven (a test, a golden vector, a
   lab experiment). *Nothing ships on vibes* — a brain change ships only if the lab shows an
   improvement at p < 0.05 (`planning/STRATEGY.md` §6.3).
6. **execute** — write the code and its tests against the exclusive files you own.
7. **push** — clear every gate below, then open a PR.

**Docs win over code.** When code and a planning doc disagree, the doc is the contract: fix the code
(or amend the doc deliberately, in its own commit). This is what lets AI agents self-correct against
the plan instead of hallucinating an interface.

## 2. Branching

- **One feature branch per capability** (book Appendix C): `feat/belief-reliability`,
  `feat/cop-cage-planner`, `fix/handshake-dedup`, … Never commit a feature straight to the default
  branch.
- Keep a branch scoped to a single capability and its tests; if it grows a second concern, split it.
- The two deliverable repos (`nis-yar1-cop`, `nis-yar1-thief`) are populated *from* this workshop repo
  with role-trimmed strategy — the shared engine is identical, the brains are split (Zero-Trust is a
  *runtime* property: separate processes/config, not separate code).

## 3. Course gates (CI-enforced; a PR is not mergeable until all pass)

| Gate | Command | Threshold |
|---|---|---|
| Lint | `uv run ruff check src tests` | clean on `E,F,W,I,N,UP,B,C4,SIM` |
| File size | `uv run python scripts/check_line_budget.py` | **every source file ≤ 150 lines** |
| Tests + coverage | `uv run pytest -q` | all pass, **coverage ≥ 85%** |
| No hardcoding | `uv run python tools/check_no_hardcoded.py` | advisory — review every flagged line |

Run everything with `PYTHONUTF8=1 PYTHONPATH=src` (the package runs from source; a Hebrew dev path
breaks editable installs on Windows). `.github/workflows/ci.yml` runs the lint + test gates on push.

## 4. Config-driven discipline (zero hardcoding)

Every Appendix-F game value — board size, barrier budget, move clock, scent constants, scoring —
enters the program through config and nothing downstream bakes it in:

- **Shared/signed terms** live in `config/<role>/game.json` (byte-identical both peers, hashed in the
  handshake). **Private tuning** lives in `config/<role>/game.toml` (the sanctioned unsigned knobs).
- Strategy weights are private, never signed terms — they are our weapon, not part of the contract.
- Pure logic (`src/pursuit/domain/**`) does **no** network, LLM, or file I/O and takes its randomness
  from an **injected `random.Random`**, so every game is reproducible and every domain unit is testable
  with fakes. Keep the LLM out of move selection entirely (rule 25 posture).

## 5. Commits

**Conventional Commits**, granular and imperative:

```
feat(belief): fuse hints with a Beta reliability ledger
fix(handshake): tolerate duplicate negotiate deliveries
test(crypto): pin both commit dialects to the golden vectors
docs(readme): add the Dec-POMDP framing section
```

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `perf`. One logical change per commit;
commit the config diff alongside a brain change so a promotion is reproducible. Do not amend pushed
history. The submission is cut as an annotated tag `v1.0-submission`.
