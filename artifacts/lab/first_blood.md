# First Blood — Agent-vs-Agent Lab Results (D7, BeliefV2)

**Date:** 2026-07-14
**Group:** nis-yar1
**Seed:** 42 | **Games per matchup:** 100 (played twice with roles swapped → 200 sub-games)

## What this lab measures

The earlier "self-play" table (one brain-set playing itself, thief-always-wins) was
**misleading**: on the signed board the thief starts at the centre (3,3) while the cop
starts at the corner (0,0) — a 6-cell BFS handicap with only a 35-move survival quota, so
*any* thief survives *any* cop. That says nothing about brain quality.

This honest lab runs a real **agent-vs-agent** series (`run_lab_versus`): each seed is
played twice with the two agents' roles swapped, so `win_rate_A` measures agent **A**'s
brains against agent **B**'s on byte-identical boards. The positional handicap is present
in every game but **cancels by symmetry**, isolating strategy quality. Belief is the real
recursive-Bayes **BeliefV2** filter.

## Results

| Matchup | Agent A | Agent B | Games | win_rate_A | p_value_A | Points A | Points B |
|---------|---------|---------|------:|-----------:|----------:|---------:|---------:|
| Interceptor vs Greedy | ours (BeliefV2) | reference greedy | 200 | **0.98** | 4.1e-53 | **2980** | 1060 |
| Ours vs Ours (mirror) | ours | ours (identical) | 200 | 0.50 | 0.53 | 1500 | 1500 |

## Findings

**1 — Our BeliefV2 agent beats the greedy baseline decisively.**
With the positional handicap cancelled by role-swapping, our
`InterceptorPoliceBrain + SurvivorThiefBrain` set wins **98%** of decided games against
the reference `Greedy` baseline (2980 vs 1060 points) at p ≈ 4×10⁻⁵³ — overwhelmingly
significant. BFS routing, the value-tested barrier doctrine, and mobility-aware flight
translate into a real, measurable edge that the blind self-play table completely hid.

**2 — The mirror matchup is balanced, exactly as it must be.**
Our brain-set against an identical copy of itself gives `win_rate_A = 0.50`, points
1500 = 1500, p ≈ 0.53 — a textbook null result. This confirms the lab has no role or
seed bias: the 98% above is a property of the *brains*, not of the harness.

**3 — The cop-start handicap is real but not the story.**
The thief's 6-cell head start still makes survival the common outcome for both agents;
what the honest lab shows is that, given the same handicap, **our agent converts far more
of those symmetric games into points than greedy does.**
