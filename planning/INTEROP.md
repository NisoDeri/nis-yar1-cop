# INTEROP.md — Wire-Protocol Specification for League Interoperability

Group **nis-yar1** (Nissim Deri, Yarden Tziar) · Final project, Orchestration of AI Agents (Dr. Yoram Segal) · Book v3.0.0.
Status: BINDING. This document stands alone: it is the complete contract our implementation must satisfy to
interoperate with an **unmodified reference peer** (`rmisegal/Game-P2P-Cop-Chase`, config schema 1.10 / shared
schema 1.3 / artifact schema 1.1) — the de-facto league standard per DECISIONS D1. Every hash and byte sequence
below was **recomputed and verified against the professor's sample-run artifacts**
(`reference/Game-P2P-Cop-Chase/docs/sample-run/`) on 2026-07-13. Where the book and the reference diverge, the
divergence is a negotiable dialect (D3) and both sides are specified.

---

## 1. Transport

- **Protocol:** MCP over **FastMCP streamable-HTTP**. Each peer runs its **own** FastMCP server (there is no
  central server) named `police-thief-{role}` and acts as a `fastmcp.Client` toward the opponent's server.
- **URL shape:** `http://<host>:<port>/mcp` — the `/mcp` path is FastMCP's default and is part of the contract
  (e.g. `http://127.0.0.1:8802/mcp`). League play substitutes the public tunnel URL — ngrok reserved domain
  or Cloudflare named-tunnel path route, both ending in `/mcp` (LEAGUE-OPS §2); the URL goes in the
  declaration's `mcp_servers` block.
- **Ports (reference defaults):** thief **8801**, police **8802**. These are private per-peer config
  (`[network] my_port` / `opponent_url`), NOT signed terms — ours are negotiable per game, but publish them
  correctly in `opponent_url` on the other side or nothing connects. The reference preflight-probes its own
  port and aborts with a "port already in use" error if a stale peer is still bound.
- **Call convention:** per call, `async with Client(url)` then
  `await client.call_tool(tool_name, {"message": <dict>})` — except `submit_audit`, which uses
  `{"payload": <dict>}` (§2.3). Every tool returns `{"ok": true}` unconditionally.
- **Zero server-side validation:** the reference server tools only enqueue into thread-safe inboxes
  (agreements / turns / audits / controls) and return. ALL enforcement (physics, crypto, schema) is done
  locally by the consuming runtime. Never rely on the opponent's server rejecting anything.
- **Retry-until-up semantics (a partner MUST tolerate):** peers start seconds apart, so every outbound call
  retries the same invocation every **1.0 s** until a deadline:
  | Call | Retry deadline | On expiry |
  |---|---|---|
  | `negotiate` / `receive_turn` | **60 s** (connect timeout) | hard error ("Opponent MCP server unreachable") |
  | `submit_audit` | **10 s** | error **suppressed** (best-effort; opponent may have exited) |
  | `receive_control` | **2 s** | error suppressed (advisory channel) |
  Retries mean **duplicate deliveries are possible**; receiver queues have **no dedup**. Our runtime must be
  idempotent to a replayed message (the reference is not — see §7 landmine 8).
- **Polling:** incoming turns are polled from the local inbox every 0.5 s (private config); the turn deadline
  resets on every received message.

## 2. The four tools

Exactly four tools; names, argument keys and body shapes are frozen (D1). Adding tools is safe (unknown tools
are simply never called); renaming or re-keying these four breaks the league.

| # | Tool | Argument key | Body | Direction |
|---|---|---|---|---|
| 1 | `negotiate` | `message` | signed agreement (§2.1) | both, pre-game (and before every sub-game) |
| 2 | `receive_turn` | `message` | TurnMessage (§2.2) — carries the implicit turn token | mover → waiter |
| 3 | `submit_audit` | **`payload`** | AuditPayload (§2.3) | both, end of sub-game |
| 4 | `receive_control` | `message` | ControlMessage (§2.4) | optional, bidirectional |

### 2.1 `negotiate` — signed agreement

Request (the `message` value):

```json
{
  "terms": {
    "board_size": 7, "smell_grid_size": 5, "decay_per_step": 0.10,
    "emit_intensity": 0.9, "min_center_intensity": 0.5,
    "max_steps": 35, "barriers_max": 14,
    "setting": "New York", "hint_max_words": 15,
    "axis_origin_corner": "top-left", "axis_start_index": 0,
    "thief_start": [3, 3], "cop_start": [0, 0], "num_games": 6
  },
  "nonce": "0f0e0d0c0b0a09080706050403020100",
  "signature": "167fef4e1881492a35297832f78a550e3ffd909e69a21f259cf09c58b887472d",
  "identity": {
    "group_id": "nis-yar1", "group_name": "Nis-Yar-1",
    "members": ["Nissim Deri", "Yarden Tziar"],
    "repos": {"cop": "https://github.com/...", "thief": "https://github.com/..."},
    "mcp_servers": {"cop": "https://<domain-a>/mcp", "thief": "https://<domain-b>/mcp"},
    "llm_model": "qwen2.5:7b",
    "spec": {"os": "...", "cpu_type": "...", "cpu_cores": 22, "cpu_freq_mhz": 0,
             "ram_gb": 63.5, "gpu_type": "NVIDIA RTX 3500 Ada", "gpu_cores_or_cuda": "CUDA",
             "vram_gb": 12.0}
  }
}
```

Response: `{"ok": true}`.

- `terms` is the **complete signed contract**: exactly these 14 keys (extra keys would fail the opponent's
  exact-equality check). Required-no-default keys (missing = the reference refuses to start):
  `board_size, smell_grid_size, decay_per_step, emit_intensity, min_center_intensity, max_steps,
  barriers_max, thief_start, cop_start`. Defaults exist for `setting` (may be `""`), `hint_max_words` (15),
  `axis_origin_corner` ("top-left"), `axis_start_index` (0), `num_games` (1).
- `signature = sha256(canonical_json(terms) + "|" + nonce)` (§3.1, reference dialect always — the agreement
  signature is computed by the reference's `CommitReveal.commit_of` regardless of the per-step dialect we
  negotiate). Nonce = 32 lowercase hex chars (16 random bytes).
- `identity` is **deliberately unsigned** — it feeds the declaration artifact, not the crypto. Its `spec`
  subkeys feed `hardware_spec` (note: `gpu_type` in identity is renamed `gpu_model` in the declaration).
- The worked `signature` above is real: canonical form of the terms shown (with `num_games: 1`,
  `decay_per_step: 0.1`) plus that nonce hashes to that digest — usable as a unit-test vector.

### 2.2 `receive_turn` — TurnMessage

Request (the `message` value):

```json
{
  "step": 4,
  "sender": "police",
  "hint": "I'm sweeping the blocks near Central Park.",
  "smell_grid": {"2,3": 0.9, "2,4": 0.6, "1,3": 0.6, "3,3": 0.6, "2,2": 0.6, "1,2": 0.3},
  "commit": "eb9e7590c3abae35ea775f7787aadbfeaa430ddc5e47cf890eb7cb62ee204add",
  "timestamp": "2026-07-11T10:52:41.101957+00:00",
  "barrier_placed": [2, 5],
  "capture_claim": [2, 3],
  "claim_response": null,
  "win_claim": null
}
```

Field contract:

| Field | Required | Semantics |
|---|---|---|
| `step` | YES | sender's own step counter (1-based; MOVE/BARRIER/HOLD all increment it) |
| `sender` | YES | `"thief"` \| `"police"` |
| `hint` | YES | free natural language, ≤ `hint_max_words`, MAY lie; no coordinates allowed (book rule 27) |
| `smell_grid` | YES | sender's decaying scent trail: `{"r,c": intensity}` string keys, **no spaces**, only cells > 0. Does NOT reveal position directly (5×5 fingerprint) |
| `commit` | YES | sha256 hex of the sealed step payload (§3); **nonce withheld until audit** |
| `timestamp` | YES | ISO-8601 UTC |
| `barrier_placed` | no (`null`) | cop's mandatory truthful declaration `[r, c]` on the turn it builds |
| `capture_claim` | no (`null`) | **cop only, on EVERY MOVE turn**: its own landing cell `[r, c]` |
| `claim_response` | no (`null`) | thief's crypto-obligated honest answer: `{"claim": [r, c], "caught": true|false}` |
| `win_claim` | no (`null`) | thief's `{"type": "survival"}` when its own counter reaches `max_steps` |

- **Seal semantics:** true position/move/intent are NEVER in the clear on the wire — they live only inside
  `commit`. The sealed payload (revealed at audit, §2.3) has exactly these keys:
  `step, state, position, move, intent, verdict, hint, prompt_discussion {llm_prompt, llm_reasoning,
  bluff_classification}, model, tokens_step, tokens_total, response_seconds, random_move`.
  `verdict` duplicates `intent` (`"truth"` | `"lie"`) — **both keys must be present or hashes break**.
  `state` is a compact string `"grid=7x7;self=[4, 3];barriers=[[2, 5]]"` (Python list repr **with spaces**,
  barriers sorted); `move` is `"<MoveType>:<Direction>"` → `"MOVE:S"`, `"BARRIER:E"`, `"HOLD:-"`.
- **Turn token is implicit:** receiving a TurnMessage IS permission to move. The thief moves first,
  unconditionally, after the handshake.
- **Strict parse:** the reference `from_dict` raises `TypeError` listing any missing required field
  (`step/sender/hint/smell_grid/commit/timestamp`); the four `null`-able fields are optional. Do not add
  unknown top-level keys — `TurnMessage(**data)` would reject them.
- **Fixed literals a partner will send/expect:** final capture concession hint `"You got me."`;
  empty-hint placeholder `"(silence)"`; fallback hint `"I keep moving through the streets."`.

### 2.3 `submit_audit` — AuditPayload

**Argument key is `payload`, not `message`** — the one asymmetry in the API; sending `message` here fails
FastMCP schema validation. Request (the `payload` value):

```json
{
  "sender": "thief",
  "result_claim": "capture",
  "records": [
    {
      "payload": {"step": 0, "type": "system_spec",
                  "spec": {"os": "Windows 11 (10.0.26200)", "cpu_type": "...", "cpu_cores": 8,
                           "cpu_freq_mhz": 2400, "ram_gb": 31.8, "gpu_type": "...",
                           "gpu_cores_or_cuda": "...", "vram_gb": 6.0},
                  "model": "qwen2.5:7b", "code_version": "1.12",
                  "group_name": "Nis-Yar-1", "sub_game_number": 1},
      "nonce": "5f72978b482c02eeb3d8a20b01e619b9",
      "commit": "78a31c516536350bfdb8a3ee4ba3e131ae0676d7b4b95d02ff94b1aa84b85e65"
    },
    {
      "payload": {"step": 1, "state": "grid=7x7;self=[4, 3];barriers=[]", "position": [4, 3],
                  "move": "MOVE:S", "intent": "truth", "verdict": "truth",
                  "hint": "I keep moving through the streets.",
                  "prompt_discussion": {"llm_prompt": "...", "llm_reasoning": "...",
                                        "bluff_classification": "truth"},
                  "model": "stub", "tokens_step": 0, "tokens_total": 0,
                  "response_seconds": 0.0, "random_move": false},
      "nonce": "22fdde9fd1571e88dfe922d6190dffcc",
      "commit": "eb9e7590c3abae35ea775f7787aadbfeaa430ddc5e47cf890eb7cb62ee204add"
    }
  ]
}
```

- `result_claim` ∈ `"capture" | "survival" | "timeout"`.
- `records[0]` is the sealed **step-0 system_spec** (hardware declaration); records 1..N are the per-step
  sealed payloads **with nonces now revealed**. The auditor recomputes each record's commit from the record's
  own `payload` + `nonce` (§3.1) — so **extra keys inside `payload` are interop-safe** (self-describing);
  this is how we add `github_commit` to step-0 (D9) without breaking a reference auditor.
- **Envelope is strict:** the reference parses via `AuditPayload(**data)` — unknown TOP-LEVEL keys raise
  `TypeError`. Only `sender`, `records`, `result_claim` at the top level, ever.
- Exchange is best-effort both ways: the winner's process may exit mid-response, so a `None` reply after the
  60 s inbox wait is legal; our own payload usually landed anyway.

### 2.4 `receive_control` — ControlMessage (optional bidirectional channel)

```json
{
  "kind": "enable",
  "sender": "police",
  "sub_game_number": 1,
  "status": "PLAYING",
  "step_budget": 30.0,
  "payload": null
}
```

- `kind` ∈ `enable | status | restart | quit`; `status` label ∈
  `WAITING | THINKING | PLAYING | PAUSED | STOPPED | GAME_OVER | QUIT`.
- Only `kind` and `sender` are required; **unknown keys are silently dropped** (forward-compatible — the one
  envelope we may extend freely).
- Channel is dormant until BOTH peers have sent `enable`; a `restart` is then auto-approved and both sides
  restart the whole series (max 10 restarts in the reference). Advisory only: 2 s send timeout, errors
  suppressed, never part of the sealed record. Not required for interop — a peer that never sends control
  messages plays fine.

## 3. Hash & canonicalization contract (byte-exact or interop dies)

**Canonical JSON** (used everywhere unless stated):

```python
json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
```

- `sort_keys=True` — key order never matters.
- `separators=(",", ":")` — compact, no spaces. (One exception: `consensus_signature`, §3.4.)
- `ensure_ascii=False` — **non-ASCII (Hebrew hints) hashes as raw UTF-8 bytes**, not `\uXXXX` escapes. A
  peer hashing with the Python default (`ensure_ascii=True`) produces different digests for any non-ASCII
  hint. Encode as UTF-8 before hashing.

### 3.1 Per-step commit — the two dialects (DECISIONS D3)

> **AUTHORITATIVE RULING (NotebookLM 2026-07-13, A1):** the BOOK construction — nonce a key INSIDE the
> canonical JSON, per the chapter-5 schema — is **authoritative for league cross-audits**; the reference
> repo's pipe-appended form is a "simplified sketch". Our default is therefore **`book` (dialect B)**.
> Dialect A remains implemented ONLY for compatibility with stock-reference peers and must be
> **explicitly negotiated** into the rule-23 lock — never assumed.

Both dialects are implemented in our engine and selected by the pre-series locked agreement. Default:
`book` (dialect B, per the A1 ruling above).

**Dialect A — `reference`** (verified: recomputing both sample-run records below reproduces their stored
commits exactly): the nonce is **pipe-appended AFTER the canonical JSON, outside it**:

```
commit = sha256( canonical_json(payload) + "|" + nonce )     # UTF-8 encoded
```

**Dialect B — `book`** (the rule-book §7 reference snippet): the nonce is a **key inside the JSON**:

```
commit = sha256( canonical_json({**payload, "nonce": nonce}) )
```

**Worked byte-level example — same payload, both digests.**
Payload and nonce:

```json
payload = {"step": 1, "move": "MOVE:S", "intent": "truth",
           "state": "grid=7x7;self=[4, 3];barriers=[]"}
nonce   = "22fdde9fd1571e88dfe922d6190dffcc"
```

Dialect A — exact byte string hashed (one line):

```
{"intent":"truth","move":"MOVE:S","state":"grid=7x7;self=[4, 3];barriers=[]","step":1}|22fdde9fd1571e88dfe922d6190dffcc
```

```
sha256 = b578bc307517f62029449e9fa845e6e981b8c802779713072324af02a722624b
```

Dialect B — exact byte string hashed (one line; note `nonce` sorts between `move` and `state`):

```
{"intent":"truth","move":"MOVE:S","nonce":"22fdde9fd1571e88dfe922d6190dffcc","state":"grid=7x7;self=[4, 3];barriers=[]","step":1}
```

```
sha256 = 93a63dddf6d1ac3a02d5f641aa123dfd8aa9f0519bad55dd77ea916b92efeeea
```

The two digests share nothing. An unnegotiated dialect mismatch = every step "fails" the cross-audit =
false tamper_forfeit. **Lock ONE dialect in the pre-series agreement (rule 23), alongside the scent formula.**

Verified golden vectors from the professor's sample run (dialect A): log record step 1
(payload as in §2.3, nonce `22fdde9f...`) → commit `eb9e7590c3ab...204add`; step-0 spec record
(nonce `5f72978b...`) → commit `78a31c5165...b85e65`. Both recomputed byte-identically on 2026-07-13.

### 3.2 game_uid derivation

Both peers derive `game_id` and `game_uid` independently after the handshake — no extra round-trip:

```python
pair     = sorted([group_id_a, group_id_b])                  # lexicographic
game_id  = f"{pair[0]}-vs-{pair[1]}"
seed     = canonical_json(terms) + "|" + pair[0] + "|" + pair[1]
game_uid = str(uuid.UUID(bytes=sha256(seed.encode())[:16])) # first 16 digest bytes
```

- `terms` = the full 14-key signed terms dict of §2.1 — any single differing term value yields a different
  uid (that is the point: the uid commits to the contract).
- The result is **NOT RFC-4122-valid** (version/variant bits are whatever sha256 produced). Do not
  "normalize" it; copy byte-for-byte.
- Worked example: terms exactly as in §2.1 but `num_games: 1`, `decay_per_step: 0.1`, groups
  `segal-police-team` / `segal-thief-team` → canonical terms string
  `{"axis_origin_corner":"top-left","axis_start_index":0,"barriers_max":14,"board_size":7,"cop_start":[0,0],"decay_per_step":0.1,"emit_intensity":0.9,"hint_max_words":15,"max_steps":35,"min_center_intensity":0.5,"num_games":1,"setting":"New York","smell_grid_size":5,"thief_start":[3,3]}`
  → `game_uid = 7132f6ae-5e09-92a9-3e85-625e138e52cb`. (This does not equal the sample-run uid
  `57ea5514-...` because the sample was generated under an older terms schema; the uid is reproducible only
  from the terms actually exchanged in that handshake.)
- JSON float formatting matters inside `seed`: Python renders `0.10` as `0.1`. Both sides must load terms
  through JSON (not construct strings by hand) so float repr is identical.

### 3.3 Agreement signature & config_sha256 (compact hasher)

- **Agreement signature** (§2.1): `sha256(canonical_json(terms) + "|" + nonce)` — always the pipe-append
  construction, even under dialect B for steps (it is what an unmodified reference peer verifies).
- **`config_sha256`** (config artifact): `sha256(canonical_json(shared_terms))` where `shared_terms` is the
  **entire loaded shared `game.json` dict** — including its own `schema_version`, `agreed_between`, and all
  prose `_note` keys. Verified: the sample-run `config_sha256`
  (`bd23d9eef59d...94c040`) reproduces only when `schema_version: "1.1"` (the game.json's version at
  generation time) is restored into the hashed dict — the artifact builder later overwrites that key with the
  artifact schema version, so **recompute from the source game.json, never from the emitted artifact**.

### 3.4 consensus_signature (spaced hasher) — the second canonicalization

Used for: declaration group-block signatures, the log's `mutual_agreement.sha256`, and the result's
`mutual_agreement.sha256`:

```python
sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode())   # DEFAULT separators (", ", ": ")
```

Identical to §3 canonical JSON **except the separators are Python's spaced defaults**. Mixing the two hashers
silently fails verification. Field-by-field map:

| Field | Hasher | Input |
|---|---|---|
| per-step `commit` / agreement `signature` | compact + `"|" + nonce` | sealed payload / terms |
| `game_uid` | compact (inside seed) | terms |
| config `config_sha256` | compact | full shared game.json dict |
| declaration `groups.*.signature` | **spaced** | group block sans `signature` |
| log `mutual_agreement.sha256` | **spaced** | the full `records` array (with nonces) |
| result `mutual_agreement.sha256` | **spaced** | symmetric outcome subset (§5.4) |

All three spaced-hasher vectors verified against the sample-run files on 2026-07-13.

## 4. Negotiation state machine (as the reference implements it)

There is **no initiator role** — the handshake is symmetric and concurrent:

1. **SEND:** each peer builds `terms` from its shared config, signs (fresh 16-byte nonce), and pushes
   `negotiate` to the opponent — retrying every 1 s for up to 60 s while the opponent's server comes up.
   Failure to deliver within 60 s = hard error, peer aborts.
2. **RECEIVE:** each peer then blocks on its own agreements inbox (timeout 60 s). Empty inbox = hard error
   ("Opponent never sent its agreement").
3. **VERIFY:** on the received message: (a) `message["terms"] != my_terms` → **CryptoError, refusal to
   play** — exact dict equality including types (`0.1` float vs `"0.1"` string mismatches; `[3,3]` list is
   what JSON delivers) — there is **no in-protocol bargaining**; terms are agreed out-of-band (WhatsApp/email)
   and typed identically into both configs. (b) signature re-check via §3.3; mismatch → CryptoError.
   (c) opponent's `identity` captured (unsigned) for the declaration artifact.
4. **DERIVE:** both peers independently compute `game_id` / `game_uid` (§3.2). **The game clock starts at
   agreement** — negotiation latency eats the game timer.
5. **PLAY:** the **thief moves first, unconditionally.** Thereafter possession of the last received
   TurnMessage is the turn token.
6. **Per sub-game:** the whole handshake re-runs before EVERY sub-game (fresh PeerRuntime, fresh nonces,
   same terms). Duplicated `negotiate` deliveries from retries sit in the queue; the reference never drains
   the agreements inbox, so a duplicate can be consumed as the next sub-game's agreement — benign iff terms
   are constant (they are), but do not rely on ordering.

Refusal matrix: terms mismatch → CryptoError (refuse); bad signature → CryptoError (refuse); missing required
term in own config → ConfigError before the server even starts (fail-fast, no port opened).

## 5. Artifact schemas (schema_version "1.1", timezone "Asia/Jerusalem")

Four JSONs per game, all sharing `game_id` + `game_uid`; filenames derive from them so games never mix:
`declaration_<game_id>.json`, `config_<game_id>_g<NN>.json`, `log_<game_id>_g<NN>.json`,
`result_<game_id>.json` (`<NN>` = zero-padded sub-game number, `g01`…). Every file embeds: `_schema` (verbatim
self-documenting prose — keep it, the grader's tooling expects it), `schema_version: "1.1"`, `game_id`,
`game_uid`, and a `links` block mapping logical role → filename with literal `g<NN>` placeholders for the
per-sub-game files. Each peer writes ALL FOUR into `logs/<own_group_id>/` (group id, not role, keys the
folder because roles alternate across sub-games).

### 5.1 Declaration — `declaration_<game_id>.json` (pre-game, whole series)

Required fields (sample-run verified): `declaration_type: "pre_game_declaration"`, `timezone`,
`game_started_at` / `game_ended_at` (ISO-8601), `num_sub_games`, `max_tokens_per_game` (default 200000),
`groups.group_1` / `groups.group_2`, each:
`{group_id, group_name, members[], repos {cop, thief}, mcp_servers {cop, thief}, llm_model,
hardware_spec {cpu_type, cpu_freq_mhz, cpu_cores, ram_gb, gpu_model, vram_gb},
signature = consensus_signature(block sans signature)}` (§3.4 — verified against the sample).

### 5.2 Config — `config_<game_id>_g<NN>.json` (per sub-game)

The shared terms spread at top level: `agreed_between[]`, `board_and_agents`, `world`,
`movement_and_barriers`, `scoring`, `pheromones`, `network_and_league`, `rate_limiter_gatekeeper` — plus
`sub_game_number`, `config_name` (its own filename) and `config_sha256` (§3.3). Book requires this per-game
file committed to the repo; the reference ships one static game.json — we generate and commit one per game
(D3/D4).

### 5.3 Log — `log_<game_id>_g<NN>.json` (per sub-game, per peer)

`summary {sub_game_number, group_id, role, opponent_group_id, result, winner_role, steps, timezone,
started_at, ended_at, duration_seconds, tokens_total, audit {passed, verified_steps, failed_steps[]}}` +
`records[]` — the sealed commit-reveal chain **with nonces revealed** (records[0] = step-0 system_spec) —
+ `mutual_agreement {opponent_group_id, sha256 = consensus_signature(records), confirmed}`. This file is what
the Replay verifier re-audits.

### 5.4 Result — `result_<game_id>.json` (THE mandatory email attachment)

`report_type: "final_game_result"`, `groups[]` (sorted gids), `num_sub_games`, `sub_games[]` each:
`{sub_game_number, roles {gid: role}, started_at, ended_at, result, winner_group, tie,
github_commit {gid: hash}, tokens {gid: n}, score {gid: pts}, log_files {gid: path},
audit {log_verified, tampered}}` + `final_result {total_score, sub_games_won, ties, winner_group, series_tie,
tokens_total_series}` + `mutual_agreement {sha256, confirmed}`.

**The mutual result signature hashes ONLY the symmetric outcome subset** (so both independently-emitted
result files agree byte-identically — verified against the sample):

```python
symmetric = {"game_id": game_id, "aggregate": {total_score, sub_games_won, ties, winner_group, series_tie},
             "sub_games": [{sub_game_number, roles, result, winner_group, score} per sub-game]}
mutual_agreement.sha256 = consensus_signature(symmetric)   # spaced hasher, §3.4
```

Per-peer tokens, timestamps, log paths and github_commit are deliberately EXCLUDED — they legitimately differ
between peers. Keep this trick exactly.

### 5.5 OUR fixes (DECISIONS D9) — schema-compatible extensions

All additive or value-level; an unmodified reference peer/verifier still parses everything:

1. **Real `github_commit`** — the reference emits literal `"unknown"`. We wire `git rev-parse HEAD` into the
   result's `github_commit` map AND into the sealed step-0 payload (extra payload key — audit-safe per §2.3;
   book rules 24/53 require the commit hash in both places).
2. **Both-sides tokens** — the reference hard-codes the opponent's `tokens` to 0. We carry `tokens_total`
   from the opponent's audited log records into the result rows and `tokens_total_series`. Value-level fix;
   stays OUT of the symmetric mutual subset, so signatures still match a reference peer.
3. **All 4 repo links in the result** — book requires them in the result JSON (reference has them only in the
   declaration). We add a top-level `repos {gid: {cop, thief}}` block to our result file — additive; excluded
   from the mutual signature.
4. **`technical_loss` endings (NotebookLM A6/A9a, 2026-07-13)** — timeout, crash and audit-caught forgery
   sub-games carry the result string **`"technical_loss"`** with scores **0/0** in the result JSON —
   overriding the reference's waiting-peer-wins timeout AND its tamper_forfeit-winner behavior. The audit is
   still run (best-effort) and the result JSON is still emailed by the surviving peer; both groups must
   report a caught forgery or risk total disqualification.
5. **Ed25519-signed declaration + counted-games count (NotebookLM A7/A9b; DECISIONS D14)** — the declaration
   additionally carries each group's Ed25519 public key and an `"ed25519:base64-signed-blob"` signature over
   the declaration and step-0 record (no staff key exists; pubkeys are exchanged and locked pre-game), plus
   the **counted-games-so-far count INSIDE the signed declaration JSON** (rule 37). Additive keys, excluded
   from the reference `consensus_signature` inputs, so an unmodified reference peer still verifies.

## 6. Compatibility test plan

### 6.1 Golden-file tests (pinned to `reference/Game-P2P-Cop-Chase/docs/sample-run/`)

Pytest suite `tests/interop/test_golden.py`, no network, no LLM — each asserts our re-implementation
reproduces the professor's stored bytes/digests (all five verified by hand on 2026-07-13):

| # | Test | Asserts |
|---|---|---|
| G1 | commit dialect A | recompute every record in `log_..._g01.json`: `commit_of(payload, nonce) == commit` (19/19 records incl. step-0) |
| G2 | log mutual sha | `consensus_signature(records) == log.mutual_agreement.sha256` |
| G3 | declaration signatures | `consensus_signature(group_block sans signature) == signature`, both groups |
| G4 | result mutual sha | symmetric-subset (§5.4) `consensus_signature == result.mutual_agreement.sha256` |
| G5 | config lock | `canonical_sha256(shared game.json dict) == config_sha256` (using the source game.json, §3.3) |
| G6 | dialect vectors | the §3.1 worked payload produces `b578bc30...` (A) and `93a63ddd...` (B) |
| G7 | game_uid | §3.2 worked terms + gids → `7132f6ae-5e09-92a9-3e85-625e138e52cb`; property: permuting gids or any term changes the uid; sorted gids are order-stable |
| G8 | envelope parse | our TurnMessage/AuditPayload/ControlMessage parsers accept the sample-run message shapes; TurnMessage missing `commit` raises; ControlMessage with unknown keys parses |

### 6.2 Localhost smoke test — our peer vs UNMODIFIED reference peer

Run before every league window and in CI-nightly (manual gate; needs no network beyond localhost).
Prereq: both `config/*/game.json` byte-identical (copy ours over the reference's, both roles).

Terminal 1 — unmodified reference, police, port 8802:

```powershell
cd reference\Game-P2P-Cop-Chase
uv sync
uv run python -m police_thief peer --role police --stub-llm --no-gui
```

Terminal 2 — our peer, thief, port 8801, opponent_url pointing at 8802:

```powershell
cd <our-workshop-repo>
uv run python -m <our_package> peer --role thief --stub-llm --no-gui
```

Pass criteria (assert on both sides' emitted artifacts):
1. Handshake completes (no CryptoError); both peers print/log the SAME `game_id` and `game_uid`.
2. Game reaches a legal terminal result (`capture` or `survival`), never `timeout`.
3. Both audits pass: each log's `summary.audit.passed == true`, `failed_steps == []`.
4. The two `result_*.json` files' `mutual_agreement.sha256` are byte-identical.
5. Reference replay verifier accepts OUR log: `uv run python -m police_thief replay --log <our log>` shows
   every step `[verified OK]`.
6. Repeat with roles swapped (our police vs reference thief) — exercises capture_claim/claim_response from
   our side.
7. Negative check: corrupt one nonce in our audit payload → reference rewrites result to `tamper_forfeit`
   (proves the audit path actually runs).

### 6.3 Dialect matrix grid

Self-play harness (D7, both peers in-process) runs the full matrix; cross-play (6.2) runs row 1 only —
the unmodified reference speaks only dialect A / reference scent:

| # | Commit dialect | Scent law | Peer pair | Expected |
|---|---|---|---|---|
| M1 | reference (A) | reference (subtractive, max-merge) | ours vs reference | full pass (stock-reference compat row — dialect A only by explicit negotiation, A1) |
| M2 | reference (A) | book (multiplicative, additive) | ours vs ours | full pass |
| M3 | book (B) | reference | ours vs ours | full pass |
| M4 | book (B) | book | ours vs ours | full pass (**our default pairing** per NotebookLM A1/A2) |
| M5 | A vs B mismatch | — | ours vs ours | audit MUST fail every step (proves detection, and why rule-23 locking matters) |
| M6 | — | reference vs book mismatch | ours vs ours | belief degrades but game legal; scent grids differ → documented evidence for the pre-series lock |

## 7. Known interop landmines — pre-series checklist

Walk this table with every partner group BEFORE the first counted game; record each agreed value in the
signed config / rule-23 lock. (Numbers from the reference-architecture survey.)

| # | Landmine | Failure if unpinned | Agree on |
|---|---|---|---|
| 1 | Commit hash construction: nonce pipe-appended after compact canonical JSON with `ensure_ascii=False` (dialect A) vs book nonce-inside-JSON (dialect B — **authoritative per NotebookLM A1, 2026-07-13**) | every audit step fails → false tamper_forfeit | ONE dialect, in the rule-23 lock (we run both; default B, A only for stock-reference peers by explicit negotiation) |
| 2 | `submit_audit` argument key is `payload`; the other three tools use `message` | audit call rejected by schema validation → no audit | nothing to negotiate — both sides must implement it |
| 3 | `game_uid` = non-RFC UUID from sha256[:16] of `canonical(terms)|gid1|gid2`, gids sorted | artifacts don't join; grader can't match the two teams' files | copy the derivation byte-for-byte |
| 4 | Scent law: subtractive decay + max-merge deposit (reference) vs multiplicative + additive (book); falloff rings 0.9/0.6/0.3 Chebyshev, 3-dp rounding, min_center 0.5 | beliefs diverge; a peer may reject "impossible" scent | ONE formula + numeric worked example, SHA-256-locked pre-series (rule 23) |
| 5 | Survival counting: judged on the thief's OWN `step_number >= max_steps`; HOLD and BARRIER turns count as steps | premature/late `win_claim`, disputed result | book default RESOLVED (NotebookLM A5): thief's OWN counter, STAY/HOLD count, cop barrier turns do NOT add — confirm the partner matches |
| 6 | Timeout semantics: reference records the WAITING peer as winner and SKIPS the audit; book says technical loss 0/0 | contradictory result reports → both groups get 0 | 0/0 + audit-still-runs, result string `technical_loss` (our D4; **NotebookLM A6 ruling**); pin explicitly |
| 7 | TWO canonical hashers: compact separators for commits/config_sha256/game_uid vs DEFAULT spaced separators for consensus_signature fields | mutual_agreement / declaration signatures never match | use the right hasher per field (§3.4 table) |
| 8 | Fixed literals & conventions: `"You got me."` / `"(silence)"` / fallback hint; thief moves first; turn token = message possession; duplicate deliveries possible, no dedup | deadlock (both wait) or double-move desync | keep all reference conventions verbatim |
| 9 | Terms must be EXACTLY equal, types included; identity is unsigned; negotiation is out-of-band | CryptoError at handshake, no game | exchange a filled game.json file, not a screenshot; diff bytes before starting |
| 10 | Barrier semantics: reference allows only the 4 adjacent cells (own-cell placement impossible) vs book's 5 options; barrier-on-thief = capture and jailed-thief = capture are ABSENT from the reference | a legal move by us rejected by them, or capture disputed | which placement set + both capture rules, in the signed config (our D4 defaults: book) |

---

*Sources: FINAL_PROJECT_BRIEF.md (book v3.0.0 distillation); planning/reference_map.md §3/§5/§10; planning/DECISIONS.md D1/D3/D4/D9; reference source (`domain/crypto.py`, `domain/game_ids.py`, `domain/negotiation.py`, `domain/protocol.py`, `peer/sealing.py`, `peer/handshake.py`, `infra/mcp_server.py`, `infra/mcp_client.py`, `report/artifact_helpers.py`, `report/artifacts.py`, `report/emit.py`); sample-run artifacts under `reference/Game-P2P-Cop-Chase/docs/sample-run/`. All hash claims machine-verified 2026-07-13.*
