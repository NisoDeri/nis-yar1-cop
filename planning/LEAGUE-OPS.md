# LEAGUE-OPS — Operational Playbook for League Play

Group **nis-yar1** (Nissim Deri, Yarden Tziar) · Orchestration of AI Agents (Dr. Yoram Segal)
Conforms to `FINAL_PROJECT_BRIEF.md` (book v3.0.0, Appendix E rules 1–55, Appendix F parameters),
`planning/reference_map.md` (wire protocol + interop landmines §10), and `planning/DECISIONS.md`
(D1–D14, incl. the NotebookLM rulings log of 2026-07-13, cited below as A1–A9). Where this doc
cites a "rule N" it means Appendix E; "landmine N" means reference_map §10.

Grading reminder: the league needs **≥2 counted games vs different groups** to pass, **≤10 counted
games** total, **diversity reward 10 per win vs a new opponent**, **one counted game per opponent**
(warm-ups free and encouraged) — brief §10 Table 18 + §12. Mutual agreement is the anti-fraud
backbone: both groups email identical result JSONs separately or **both score 0** (rules 34–35).

**Pod draft league protocol:** the pod has published a draft league protocol
(github.com/Imreec/copthief-league-protocol). Full analysis in `LEAGUE-PROTOCOL-REVIEW.md`;
reconcile its terms with this checklist before onboarding any pod opponent.

---

## 1. Opponent onboarding checklist (run per opponent group, BEFORE any game)

Work through this top-to-bottom with the partner group (WhatsApp template B below is this section
in fill-in form). Nothing is played until every box is checked by BOTH sides.

### 1.1 Identity exchange (feeds `declaration_<game_id>.json`)

- [ ] Group IDs (8-char, no spaces) + group names + full member lists.
- [ ] Both repo URLs per side (cop + thief = 4 links total; needed later in the result JSON, rule 49).
- [ ] MCP URLs per role (public tunnel URLs, path `/mcp`). Ours: per D5 — provider decided at
      Stage 5 (fresh ngrok account or Cloudflare named tunnel; see §2 step 4).
- [ ] LLM model each side runs (goes in step-0 + declaration; ours: local Ollama qwen2.5:7b, D8).
- [ ] Current GitHub commit hash each side will play (rule 24/53; re-exchanged before every game).
- [ ] **Ed25519 public keys exchanged both ways + declaration signatures verified** (A7, D14):
      no staff-distributed key exists — each team signs the pre-game declaration and step-0 record
      with its own keypair (`ed25519:base64-signed-blob`); pubkeys are locked into the signed
      declaration BEFORE play so the spec record cannot be altered mid-series.

### 1.2 Dialect matrix (D3 — lock BOTH axes before the series)

Two known book-vs-reference splits. Our engine implements both sides of each, selected by the
signed shared config. Pick one value per axis with the partner and record it:

| Axis | Option A (`reference`) | Option B (`book`) | Agreed |
|---|---|---|---|
| Commit hash construction | `sha256(canonical_json(payload) + "\|" + nonce)` — nonce pipe-appended AFTER compact canonical JSON, `ensure_ascii=False` | `sha256(canonical_json({...payload, nonce}))` — nonce a key INSIDE the JSON | ☐ A ☐ B |
| Scent law | subtractive decay `max(0, τ−0.10)` + max-merge deposit | multiplicative `τ(t+1)=max(0,(1−ρ)·τ+Δτ)` + additive deposit | ☐ A ☐ B |

Defaults per D3 as updated by the 2026-07-13 rulings: hash = **`book`** (A1 — the book's
nonce-inside-JSON construction is authoritative for league cross-audits; dialect A only for
stock-reference partners, explicitly negotiated); scent = **`book`** multiplicative (A2 — the
reference dialect is a LEGAL mutually-agreed upgrade if exchanged + crypto-locked at Step-0;
priority = both peers byte-identical).

**Rule-23 lock procedure (mandatory, per series):**
1. Exchange the full scent formula TEXT: emission profile (5×5 field, center 0.9, falloff rings —
   reference uses Chebyshev rings 0.9/0.6/0.3, 3-dp rounding), `min_center_intensity` (reference
   invention, 0.5 — negotiate it), decay law + timing (message-driven: deposit then decay on own
   send; absorb then decay on receive), merge semantics.
2. Exchange a **numeric worked example**: agent at (3,3) deposits, one decay tick — full 5×5 grid
   of expected values, both sides compute independently.
3. Verify byte-identical output (same 3-dp values, same `"r,c"` string keys, cells > 0 only).
4. **SHA-256-lock**: hash formula-text + worked example; both sides record the digest in chat and
   in the game notes. Any later deviation is detectable and voids the game (rule 23).

Also confirm the hash-adjacent landmines (landmines 2, 3, 7, 8):
- [ ] `submit_audit` MCP tool takes param key `payload`; the other three tools take `message`.
- [ ] `game_uid` = UUID from `sha256(canonical_json(terms) + "|" + gid1 + "|" + gid2)[:16]`,
      gids sorted; `game_id = "<a>-vs-<b>"` sorted.
- [ ] Two canonical hashers coexist: compact separators for `config_sha256`, default (spaced)
      separators for `consensus_signature` — confirm the partner replicates both per field.
- [ ] Fixed literals: `"You got me."` / `"(silence)"` / fallback hint; **thief moves first**;
      turn token = possession of the TurnMessage.

### 1.3 Shared game parameters (Appendix F; typed identically into both configs)

Negotiation is out-of-band; `verify_peer` requires EXACT dict equality of terms, types included
(landmine 9) — a mismatch is a hard refuse-to-play, not a bargaining round.

- [ ] Coordinate system: origin corner (default top-left `(0,0)`), index base (default 0), row
      grows DOWN. Must be identical or `(3,3)` means two different cells and the game breaks.
- [ ] Board size: 7 (minimum; raise only by mutual agreement, never lower — rule 12).
- [ ] Starts: thief `(3,3)`, cop `(0,0)` (negotiable, must match).
- [ ] Arena: `"New York"` (or "" = generic; London/Paris also book-legal).
- [ ] `hint_max_words`: 15.
- [ ] `num_games`: **6 — fixed by Appendix F Table 18, not negotiable.**
- [ ] Token budget per series: ~200,000 (negotiable; reported in the result email).
- [ ] Timeouts: per-request 30 s, watchdog freeze 60 s (both negotiable), turn timeout — agree the
      number explicitly; the reference's private 180 s silently overrides the shared 30/60
      (reference_map §6 trap), so state the effective turn deadline out loud.
- [ ] Survival counting semantics (landmine 5) — **book default RESOLVED per A5**: adjudicated
      on the thief's OWN valid-step counter; STAY/HOLD count toward the 35; the cop's barrier
      turns do NOT add to the thief's count. Confirm the partner follows this; lock it.
- [ ] Barrier semantics (landmine 10): 5 placement options (own cell + 4 orthogonal, per book/D4;
      **confirmed by A3**); **barrier-on-thief = capture** (rule 46); **jailed thief = capture**
      (rule 47). **A3: rules 46/47 are MANDATORY in league play** (marked mandatory in the master
      parameter table) — our engine implements them even when the partner's reference-based peer
      lacks them. The stock reference implements NONE of the three (gaps 1–3): **surface this
      EARLY — it is the likeliest dispute of the whole onboarding.**
- [ ] Timeout/crash semantics (landmine 6): **technical loss 0/0 to the crashed/frozen side's game
      — never waiting-peer-wins — with the audit still run and reported** (D4; **confirmed by A6**:
      the surviving peer MUST still run the audit and email the result JSON, result string
      `technical_loss`; stock reference awards the waiter a win and skips the audit; must be
      agreed away).

### 1.4 Policy declarations

- [ ] **LLM-move exception: we DECLINE** (D13). The book allows an LLM-chosen move only as an
      explicit, mutual, documented pre-game exception (PDF p.66); we do not grant it. Moves are
      Python on both sides; local legality enforcement stays mandatory regardless.
- [ ] Counted vs warm-up status of the upcoming session, stated explicitly.
- [ ] **Truthful counted-game counts** (rule 36): each side declares how many counted games it has
      already played and against whom. False declaration = disqualification. **Per rule 37 / A9b
      the counted-games-so-far count is written INSIDE the cryptographically signed pre-game
      declaration JSON** — not just stated in chat (prevents diversity-reward resets / limit
      bypass).
- [ ] Both sides confirm they will **email the result JSON separately and independently** to
      `rmisegal+uoh26finalgame@gmail.com` — JSON attachment, never free text (rules 32–35; missing
      or contradictory report = 0 to BOTH groups).
- [ ] Trash-talk providers exchanged for the declaration (private, not negotiated — Table 21).

Onboarding is DONE when: dialect matrix locked + rule-23 SHA recorded + full terms dict agreed
field-by-field + policy declarations confirmed + a scheduled warm-up slot.

---

## 2. Pre-game runbook (our side, step by step)

Run this in order for every game (warm-up or counted). Target: T-30 minutes before the slot.

1. **Generate the shared config** from the negotiation record:
   `config_<game_id>_g<NN>.json` (per-game filename per Appendix F; `game_id = "<a>-vs-<b>"`
   sorted). Every negotiated value from §1.3 goes in; nothing hardcoded.
2. **Byte-verify vs partner**: compute `sha256` of the file bytes AND the `config_sha256`
   (compact-separator canonical hash of the shared terms); exchange both digests on WhatsApp;
   proceed only on exact match. A terms mismatch will hard-fail the handshake mid-slot otherwise.
3. **Commit the config** to the repo on the game branch; note the commit hash — it must appear in
   step-0 and in the result JSON (rule 24/53).
4. **Start tunnels** — the paid ngrok account was DELETED; two documented paths, decision
   deferred to Stage 5 (~Jul 27), keep both runnable:
   - **Path A — fresh ngrok account** (open when league week nears), one command per role on
     reserved domains: `ngrok http --url=<cop-domain> 8802` (police) and
     `ngrok http --url=<thief-domain> 8801` (thief).
   - **Path B — free named Cloudflare tunnel** (stable hostname, no paid plan — field-proven by
     another team): one tunnel, path-routed `https://<host>/cop/mcp` → localhost:8802 and
     `https://<host>/thief/mcp` → localhost:8801 (URLs still end in `/mcp`, so the FastMCP
     contract holds).
5. **Preflight checks** (all must pass before telling the partner we're ready):
   - [ ] Local ports 8801/8802 free (the MCP server does a port-free probe, but check first).
   - [ ] Tunnel reachable **from outside** (phone on cellular, or partner pings `/mcp`).
   - [ ] Ollama up: `ollama ps` / one-token generate against qwen2.5:7b (D8; template fallback
         means a dead Ollama is not fatal, but know before, not during).
   - [ ] Gmail OAuth token valid: dry-run the HW6 sender's auth refresh (send-only scope, rule 30);
         re-auth now if expired — never mid-game.
   - [ ] Correct git commit checked out; `git rev-parse HEAD` matches the hash we exchanged.
   - [ ] Watchdog + FSM + gatekeeper enabled in config (D5); UI in local-truth mode (rules 8–9).
6. **Step-0 signed hardware declaration** (rule 24): collect_spec (OS/CPU/RAM/GPU/LLM model) +
   code version + group name + sub-game number + `github_commit`, sealed as records[0] of the
   commit chain. Verify it is emitted before move 1. Skipping it forfeits the computational-
   fairness bonus — which our laptop-plus-efficient-algorithm story is built to win (D9).
7. Exchange final "READY" with MCP URLs restated; agree who starts servers first (§3).

---

## 3. Game-day runbook

**Launch order.** Both sides start their peer servers (server up = listening); then each starts its
client loop toward the opponent's URL. Connect retries run every 1 s up to 60 s, so exact ordering
is forgiving — but agree a "servers up by T-5" convention. Negotiation (signed-terms exchange)
runs first; **the game clock starts at handshake** (reference_map §2.3) — don't dawdle after
launch. **Thief moves first, unconditionally.**

**What to watch in the live UI** (local truth only — rules 8–9):
- Status line: WAITING/THINKING/PLAYING transitions; a stuck WAITING past the poll interval means
  the pipe is down.
- Belief heatmap evolving (also the mandatory screenshot source — capture at least one good frame
  per counted game).
- Step counter vs the 35-move ceiling; barrier count vs quota 14; own scent deposits.
- Watchdog panel: last-message age vs the 60 s freeze threshold.

**Timeout / pause discipline.** The pause control is for genuine emergencies only: **a pause that
outlives the agreed turn timeout is indistinguishable from a freeze and hands a technical loss
(0/0 per D4)**. If a human pause is needed, announce it on WhatsApp FIRST, get an explicit "ok"
from the partner, and resume well inside the window. Never pause during the opponent's think time
expecting the clock to stop — the deadline resets only on received messages.

**Network flaps (retry policy).** The transport already retries: 1 s interval up to 60 s for
connect/negotiate, 10 s for audit, 2 s for control; duplicates are possible and receiver queues
have no dedup (reference_map §3). Our deadline resets on every received message, so a
slow-but-alive opponent never times us out. On a tunnel flap: do NOT restart the peer process —
restart only the tunnel (named/reserved hostname = same URL, sessions resume). If the flap exceeds
the watchdog threshold, treat it as a crash (below). Never blind-retry past the agreed timeout;
message the partner in parallel.

**Crash procedure** (our side crashes or freezes past watchdog):
1. The watchdog performs **controlled data extraction** — the step log with all sealed records up
   to the failure is flushed to `logs/<group_id>/` (rule 7; a lost official log is a lost game).
2. Declare the technical loss honestly: result `technical loss 0/0` per D4 and the scoring table —
   nobody wins on a timeout.
3. **Run the audit anyway** (D4 — stock reference skips it on timeout/stopped; we do not):
   exchange whatever AuditPayloads both sides can, verify, and record the outcome in the log.
4. Both sides email the 0/0 result JSON separately, same as any other result (rules 32–35).
5. If it was a warm-up: fix, re-verify preflight, replay. If counted: it counts as played — this
   is exactly why warm-ups come first (§6).

If the OPPONENT freezes past the agreed threshold: capture the watchdog evidence (timestamps,
last received message), message them, and propose the honest 0/0 + audit. Do not claim a win.

---

## 4. Post-game runbook

1. **Mutual audit** (rules 19–22, 35): AuditPayloads exchange automatically at game end. Then:
   - Run our replay verifier on OUR log → "Verified OK" (screenshot on counted games — mandatory
     README artifact).
   - Re-hash THEIR revealed records against their committed hashes; they do the same to ours.
     Any mismatch = provable forgery = sub-game adjudicated `technical_loss` 0/0 regardless of
     the board result (A9a); both groups must still report it.
   - Verify their declared `github_commit` exists in their repo and matches what was exchanged
     pre-game; they verify ours.
2. **Agree the result** explicitly (per sub-game scores + cumulative + winner + tokens). The mutual
   signature hashes only the symmetric outcome subset, so both independently-emitted files must
   agree byte-identically on it (reference_map §2.6).
3. **Both email separately**: each group's agent sends `result_<game_id>.json` as a **JSON
   attachment** to `rmisegal+uoh26finalgame@gmail.com` (free text = 0; missing/contradictory
   report = 0 to both). Confirm on WhatsApp that both mails are out (template D).
4. **Commit artifacts**: per-game `config_<game_id>_g<NN>.json` + `log_<game_id>_g<NN>.json` (+
   declaration + result) committed to the repo (Appendix F config rule: name per game, commit,
   email the hash used).
5. **Update the commit hash for the next game**: code may change between games; the new
   `git rev-parse HEAD` must go into the next game's step-0 and result JSON (rule 53) and be
   re-exchanged with the next opponent.
6. Update our counted-game ledger (opponent, date, counted?, result, diversity reward) — the
   source for the rule-36 truthful declaration at the next onboarding.

---

## 5. WhatsApp message templates (4-pair pod)

### (a) Intro + scheduling ask

**EN:**
> Hi! We're group **nis-yar1** (Nissim Deri + Yarden Tziar) from Dr. Segal's final-project league.
> We'd like to schedule a series against you: one warm-up first (free, per the book), then one
> counted game if both sides are stable. We run reference-compatible wire protocol (4 MCP tools,
> schema 1.1) over a stable named public tunnel, so connectivity on our side is solid.
> Which days between Aug 3–9 work for you? A warm-up slot takes ~1 hour, counted ~1.5 hours
> including the mutual audit. Before playing we'll send a short technical negotiation form to
> lock parameters + the rule-23 scent hash. Looking forward!

**HE:**
> היי! אנחנו קבוצת **nis-yar1** (ניסים דרעי + ירדן צייר) מהליגה של הפרויקט הסופי של ד"ר סגל.
> נשמח לתאם מולכם סדרה: קודם משחק חימום (חופשי, לפי הספר), ואז משחק נספר אם שני הצדדים יציבים.
> אנחנו רצים על פרוטוקול תואם-רפרנס (4 כלי MCP, סכמה 1.1) מעל טאנל ציבורי עם שם מארח קבוע,
> כך שהקישוריות אצלנו יציבה. אילו ימים בין 3–9 באוגוסט מתאימים לכם? חימום לוקח בערך שעה,
> משחק נספר בערך שעה וחצי כולל הביקורת ההדדית. לפני המשחק נשלח טופס תיאום טכני קצר לנעילת
> הפרמטרים וה-hash של חוק הריח (כלל 23). מחכים!

### (b) Technical negotiation form (copy-paste, fill both sides)

**EN:**
> **P2P Cops&Robbers — pre-series negotiation form** (both groups fill; play only on full match)
>
> IDENTITY
> 1. Group ID (8 chars) / name / members: ___
> 2. Repo URLs — cop: ___ thief: ___
> 3. MCP URLs — cop: ___ thief: ___
> 4. LLM model (for declaration): ___
> 5. Commit hash you will play: ___
>
> DIALECTS (pick one per line; rule 23 lock follows)
> 6. Commit hash construction: [ ] reference (nonce pipe-appended after compact canonical JSON,
>    ensure_ascii=False) [ ] book (nonce inside JSON) — book is the authoritative construction
>    for cross-audits (NotebookLM 13/7); nis-yar1 default: book
> 7. Scent law: [ ] reference (subtractive decay max(0,τ−0.10), max-merge deposit)
>    [ ] book (τ(t+1)=max(0,(1−ρ)τ+Δτ), additive deposit) — nis-yar1 default: book; reference is
>    legal by mutual locked agreement (NotebookLM 13/7)
> 8. Scent details: falloff rings ___ (default Chebyshev 0.9/0.6/0.3, 3-dp), min_center_intensity
>    ___ (default 0.5), decay timing: message-driven [ ] yes
> 9. Rule-23 lock: we exchange formula text + numeric worked example (deposit at (3,3) + one decay
>    tick, full 5×5 grid), verify identical, then both record SHA-256 of formula+example: ___
>
> SHARED PARAMETERS (typed identically into both configs; exact dict equality enforced)
> 10. Origin corner: ___ (default top-left) | index base: ___ (default 0) | row grows down: yes
> 11. Board size: ___ (min 7) | thief start: ___ (default (3,3)) | cop start: ___ (default (0,0))
> 12. Arena: ___ (default "New York") | hint_max_words: ___ (default 15)
> 13. num_games: 6 (fixed) | token budget/series: ___ (default 200,000)
> 14. Timeouts: per-request ___ s (default 30) | watchdog ___ s (default 60) | effective turn
>     timeout ___ s (state explicitly — private defaults differ)
> 15. Survival counting (book default per NotebookLM 13/7): thief's OWN step counter; thief
>     STAY/HOLD count toward the 35; cop barrier turns do NOT add. Confirmed? [ ] yes [ ] deviation: ___
> 16. Barrier semantics confirmed by BOTH engines: 5 placement options (own cell + 4 adjacent)
>     [ ] · barrier-on-thief = capture [ ] · jailed thief = capture [ ]
> 17. Timeout/crash = technical loss 0/0 (never waiting-peer-wins), audit still runs: [ ] agreed
>
> POLICY
> 18. LLM-move exception: DECLINED by nis-yar1 (moves are Python both sides). Agreed? [ ]
> 19. This session is: [ ] warm-up [ ] counted
> 20. Counted games already played (truthful, rule 36) — us: ___ (vs: ___) you: ___ (vs: ___)
> 21. Both groups will email result JSON separately (attachment) to
>     rmisegal+uoh26finalgame@gmail.com: [ ] agreed
> 22. config_<game_id>_g<NN>.json sha256 exchange before start: [ ] agreed
> 23. Ed25519 public keys exchanged both ways; declaration + step-0 signatures verified
>     (ed25519:base64-signed-blob; no staff key exists): [ ] done — our pubkey: ___ yours: ___
> 24. Counted-games-so-far count written INSIDE the signed declaration JSON (rule 37): [ ] agreed

**HE:**
> **שוטרים וגנבים P2P — טופס תיאום לפני סדרה** (שתי הקבוצות ממלאות; משחקים רק בהתאמה מלאה)
>
> זהות
> 1. מזהה קבוצה (8 תווים) / שם / חברים: ___
> 2. כתובות ריפו — שוטר: ___ גנב: ___
> 3. כתובות MCP — שוטר: ___ גנב: ___
> 4. מודל LLM (להצהרה): ___
> 5. commit hash שתשחקו איתו: ___
>
> דיאלקטים (בחרו אחד בכל שורה; נעילת כלל 23 בהמשך)
> 6. בניית hash ה-commit: [ ] רפרנס (nonce מחובר עם | אחרי JSON קנוני קומפקטי, ensure_ascii=False)
>    [ ] ספר (nonce כשדה בתוך ה-JSON) — גרסת הספר היא הסמכותית לביקורות צולבות (NotebookLM 13/7);
>    ברירת המחדל של nis-yar1: ספר
> 7. חוק הריח: [ ] רפרנס (דעיכה חיסורית max(0,τ−0.10), מיזוג-מקסימום)
>    [ ] ספר (τ(t+1)=max(0,(1−ρ)τ+Δτ), הפקדה חיבורית) — ברירת המחדל של nis-yar1: ספר; רפרנס
>    חוקי בהסכמה הדדית נעולה (NotebookLM 13/7)
> 8. פרטי ריח: טבעות דעיכה ___ (ברירת מחדל צ'בישב 0.9/0.6/0.3, עיגול 3 ספרות),
>    min_center_intensity ___ (ברירת מחדל 0.5), דעיכה מונעת-הודעות: [ ] כן
> 9. נעילת כלל 23: מחליפים נוסח נוסחה + דוגמה מספרית (הפקדה ב-(3,3) + טיק דעיכה אחד, רשת 5×5
>    מלאה), מאמתים זהות, ושני הצדדים רושמים SHA-256 של נוסחה+דוגמה: ___
>
> פרמטרים משותפים (מוקלדים זהה בשתי הקונפיגורציות; נאכף שוויון מילון מדויק)
> 10. פינת ראשית: ___ (ברירת מחדל שמאל-עליון) | בסיס אינדקס: ___ (ברירת מחדל 0) | שורה גדלה מטה: כן
> 11. גודל לוח: ___ (מינימום 7) | התחלת גנב: ___ ((3,3)) | התחלת שוטר: ___ ((0,0))
> 12. זירה: ___ ("New York") | מקסימום מילים לרמז: ___ (15)
> 13. num_games: 6 (קבוע) | תקציב טוקנים לסדרה: ___ (200,000)
> 14. טיימאאוטים: לבקשה ___ שנ' (30) | watchdog ___ שנ' (60) | טיימאאוט תור אפקטיבי ___ שנ'
>     (לציין מפורשות — ברירות המחדל הפרטיות שונות)
> 15. ספירת הישרדות (ברירת מחדל הספר לפי NotebookLM 13/7): המונה של הגנב עצמו; STAY/HOLD של הגנב
>     נספרים אל תוך ה-35; תורות מחסום של השוטר לא מוסיפים. מאושר? [ ] כן [ ] חריגה: ___
> 16. סמנטיקת מחסומים מאושרת בשני המנועים: 5 אפשרויות הנחה (התא העצמי + 4 שכנים) [ ] ·
>     מחסום-על-גנב = לכידה [ ] · גנב כלוא = לכידה [ ]
> 17. טיימאאוט/קריסה = הפסד טכני 0/0 (אף פעם לא ניצחון לממתין), הביקורת עדיין רצה: [ ] מוסכם
>
> מדיניות
> 18. חריגת LLM-בוחר-מהלך: nis-yar1 מסרבת (המהלכים בפייתון בשני הצדדים). מוסכם? [ ]
> 19. הסשן הזה הוא: [ ] חימום [ ] נספר
> 20. משחקים נספרים שכבר שוחקו (הצהרת אמת, כלל 36) — אנחנו: ___ (מול: ___) אתם: ___ (מול: ___)
> 21. שתי הקבוצות ישלחו את קובץ התוצאה בנפרד (כקובץ מצורף) אל
>     rmisegal+uoh26finalgame@gmail.com: [ ] מוסכם
> 22. החלפת sha256 של config_<game_id>_g<NN>.json לפני ההתחלה: [ ] מוסכם
> 23. הוחלפו מפתחות Ed25519 ציבוריים בשני הכיוונים; אומתו חתימות ההצהרה ורשומת step-0
>     (ed25519:base64-signed-blob; אין מפתח מהסגל): [ ] בוצע — המפתח שלנו: ___ שלכם: ___
> 24. ספירת המשחקים-הנספרים-עד-כה נכתבת בתוך ה-JSON החתום של ההצהרה (כלל 37): [ ] מוסכם

### (c) Game-day coordination

**EN:**
> Game day — <game_id>, sub-game g<NN>, [warm-up/counted].
> 1. Config sha256 (file bytes): `___` / config_sha256 (canonical terms): `___` — please confirm
>    match.
> 2. Our MCP URLs live: cop `https://<cop-domain>/mcp`, thief `https://<thief-domain>/mcp`.
>    Yours?
> 3. Our commit hash for this game: `___`. Yours?
> 4. Servers up by HH:MM, handshake at HH:MM+5 (clock starts at handshake). Thief moves first.
> 5. Emergency channel = this chat. Any human pause gets announced HERE before pressing anything;
>    a pause past the turn timeout is a 0/0 technical loss for the pauser.
> READY? reply "READY <commit-hash>".

**HE:**
> יום משחק — <game_id>, תת-משחק g<NN>, [חימום/נספר].
> 1. sha256 של קובץ הקונפיג: `___` / config_sha256 (מונחים קנוניים): `___` — נא לאשר התאמה.
> 2. כתובות ה-MCP שלנו באוויר: שוטר `https://<cop-domain>/mcp`, גנב `https://<thief-domain>/mcp`.
>    שלכם?
> 3. ה-commit hash שלנו למשחק: `___`. שלכם?
> 4. שרתים למעלה עד HH:MM, לחיצת-יד ב-HH:MM+5 (השעון מתחיל בלחיצת-היד). הגנב זז ראשון.
> 5. ערוץ חירום = הצ'אט הזה. כל השהיה אנושית מוכרזת כאן לפני שלוחצים על משהו; השהיה מעבר
>    לטיימאאוט התור = הפסד טכני 0/0 למשהה.
> מוכנים? השיבו "READY <commit-hash>".

### (d) Post-game result confirmation

**EN:**
> Post-game <game_id>: our audit of your log = PASSED / FAILED (details: ___). Replay verifier on
> our side: "Verified OK". Proposed result: sub-games ___ , cumulative us ___ / you ___ , winner
> ___ , tokens us ___ / you ___ , commit hashes: us `___` you `___`.
> Please confirm the identical result. On confirmation BOTH groups email result_<game_id>.json
> (attachment) separately to rmisegal+uoh26finalgame@gmail.com — mismatch or missing mail = 0 to
> both. Reply "CONFIRMED + SENT" once your mail is out; we'll do the same.

**HE:**
> אחרי המשחק <game_id>: הביקורת שלנו על הלוג שלכם = עברה / נכשלה (פרטים: ___). מאמת ה-Replay
> אצלנו: "Verified OK". תוצאה מוצעת: תתי-משחקים ___ , מצטבר אנחנו ___ / אתם ___ , מנצח ___ ,
> טוקנים אנחנו ___ / אתם ___ , commit hashes: אנחנו `___` אתם `___`.
> נא לאשר את התוצאה הזהה. עם האישור שתי הקבוצות שולחות את result_<game_id>.json (כקובץ מצורף)
> בנפרד אל rmisegal+uoh26finalgame@gmail.com — אי-התאמה או מייל חסר = 0 לשתיהן. השיבו
> "CONFIRMED + SENT" כשהמייל שלכם יצא; נעשה אותו דבר.

---

## 6. Counted-game policy

Per D13 and brief §12 (Table 18):

- **Warm-up first, ALWAYS.** Every new opponent gets at least one full free warm-up series
  (handshake → 6 sub-games → audit → dry-run result exchange, no email to the lecturer). Warm-ups
  are unlimited and encouraged by the book.
- **Count only when stable**: a game is declared counted only after (a) a clean warm-up vs that
  opponent — handshake, full series, audit PASSED both ways, no watchdog events — and (b) our own
  preflight (§2) green. One counted game per opponent (rule 52); a counted crash still counts, so
  never gamble a counted slot on an unproven pairing.
- **Targets**: **3 counted games** across the pod (3 available opponents), each vs a NEW opponent
  → up to 3 × diversity reward 10. Hard floor **≥2 counted vs different groups** (pass gate);
  hard ceiling **≤10 counted** (we will not approach it).
- **Truthful ledger** (rule 36): maintain the counted-game ledger (§4.6); declare it verbatim at
  every onboarding. False declaration = disqualification — never worth it.

---

## 7. Schedule

Maps to DECISIONS D12; league window = **W4 (Aug 3–9)** after stage 7 (Gmail + artifacts + GUI
polish) lands.

| When | What |
|---|---|
| **W3, Aug 1–2** (early bird) | Send template (a) to all 3 pod opponents; open negotiation forms (b). If stages 5–6 finished early, offer opportunistic warm-ups. |
| **Aug 3–4** | Complete onboarding (§1) with all 3 opponents: dialect matrix + rule-23 locks + forms signed off. Warm-up #1 (first opponent). |
| **Aug 5–6** | Warm-ups #2–#3 (remaining opponents). Fix anything the warm-ups expose; re-warm-up if changes touched wire/crypto/scent. |
| **Aug 6–8** | **Counted games #1–#3**, one per opponent, each within 24–48 h of that opponent's clean warm-up. After each: full §4 post-game (both emails out same day). |
| **Aug 9** | Slack for reschedules; confirm all result emails landed (2 per counted game); ledger reconciled. |
| **Fallback week, Aug 10–12 (the D12 buffer)** | If any opponent slipped: warm-up + counted game compressed into one day per remaining opponent. Hard cutoffs: last counted game **Aug 11 12:00**, both result emails out **Aug 11 EOD** — Aug 12 stays reserved for repo finalization, `v1.0-submission` tags, screenshots, and Moodle PDFs (deadline Aug 12 23:59, no late submission). If only one opponent remains reachable, prioritize hitting the ≥2-counted floor over the 3-win diversity target. |

Risk rule: never schedule a counted game on the same calendar day as a code change touching the
wire protocol, crypto, or scent model — warm-up again first.
