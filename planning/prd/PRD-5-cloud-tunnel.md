# PRD-5 — Cloud + Tunnel (Book Ch2; roadmap stage 5)

## Purpose
Move from localhost to **public addresses via ngrok** and connect agents on remote machines
(brief §14.5). Tunneling is mandatory for league play (rule 10; Appendix E group 1 #10). From
here on this is a real distributed system: latency, disconnects, and duplicate deliveries are
normal, not exceptional.

## In scope
- Tunnel integration with **stable hostnames, one per role** — provider decided at this stage per
  D5: a fresh ngrok account with reserved domains, or a free named Cloudflare tunnel (the old
  paid ngrok account was deleted; both paths in LEAGUE-OPS §2 step 4)
  (reference gap #18: the reference has no tunneling at all).
- Preflight checks, remote-play runbook, resilience hardening of the PRD-2 transport under real
  WAN conditions.
- Public URLs wired into config (`[network] opponent_url`, `mcp_servers` block of the
  declaration artifact).

## Out of scope
Crypto (PRD-6), reporting (PRD-7), any change to the wire protocol (frozen since PRD-2, D1).

## Functional requirements
- **FR-5.1 Tunnel bring-up.** One command (or Orchestrator startup hook) starts the peer's ngrok
  tunnel on its reserved domain and verifies end-to-end reachability by calling a no-op on its
  own public URL before declaring readiness (rule 10; D5 preflight).
- **FR-5.2 Stable public identity.** Reserved domains (not ephemeral URLs) are the values placed
  in the negotiation `identity.mcp_servers` and the declaration JSON, so partners can reconnect
  across restarts without renegotiating addresses (reference_map §3.1; Table 20).
- **FR-5.3 Config-only addressing.** Host/port/public-URL exclusively from private config; no CLI
  flags, no hardcoding (course gate; reference CLI parity).
- **FR-5.4 WAN resilience.** PRD-2 retry semantics proven over the tunnel: connect retry ≤60s,
  duplicate-delivery idempotence (step-number dedup), out-of-order control messages tolerated;
  per-request timeout 30s and watchdog 60s from Table 19 enforced end-to-end (rules 6–7).
- **FR-5.5 Disconnect handling.** Mid-game tunnel drop is detected by the deadline/watchdog path
  and resolved per D4: technical loss 0/0 semantics with the audit still attempted (best-effort
  both ways, `None` tolerated — reference_map §2.5); logs always extracted locally.
- **FR-5.6 Security posture.** Server binds `0.0.0.0` only when tunneling; no secrets in the
  tunnel config committed (ngrok authtoken via env/.gitignored file; rules 39–40). `.env-example`
  documents required variables (D11).
- **FR-5.7 Latency telemetry.** Round-trip and turn-latency measurements logged per step —
  evidence for the README's FastMCP orchestration-dilemmas section (brief §13 README #2) and for
  `docs/RESEARCH-REPORT-Performance-Analysis.md`.

## Acceptance criteria (testable)
1. **Runs end-to-end:** a full series between two physically separate machines (or two networks;
   minimum: laptop + second host/phone hotspot) over the public ngrok domains, completing with
   legal results and complete logs on both sides.
2. Preflight test: peer refuses to enter the league loop if its own public URL is unreachable;
   clear operator error message.
3. Chaos test (local, injected): dropped/duplicated/delayed turn messages neither desync the
   implicit turn token nor corrupt the FSM; forced mid-game disconnect yields 0/0 + extracted log.
4. CI never opens a tunnel or socket: all resilience tests run against the injected fake
   transport with simulated faults (course gate).
5. Config swap between localhost and ngrok URLs requires zero code changes.
6. Gates: ≤150 lines/file, ruff, coverage ≥85%.

## Dependencies
PRD-2 (transport + FSM + watchdog), PRD-4 (real payloads worth carrying; can start in parallel
once PRD-2 is stable — D12 schedules this in W3).

## Risks
- ngrok free-tier behavior differs from paid (interstitial pages break MCP) → the old paid
  account was deleted: if we pick ngrok at Stage 5 we open a fresh account with reserved domains,
  otherwise use the free named Cloudflare tunnel path (D5); verified in FR-5.1 preflight either way.
- Partner behind restrictive NAT/firewall with a different tunnel tool (Localtonet) → only OUR
  side's exposure is our duty; client side just needs outbound HTTPS.
- Public endpoint abuse (strangers calling our tools) → tools are enqueue-only with local
  enforcement (PRD-2), plus negotiation signature gate; game only starts with a verified partner.
