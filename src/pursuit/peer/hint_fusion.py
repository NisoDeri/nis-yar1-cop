"""Live hint fusion — wire the book p.63 pipeline into the turn loop (E1, STRATEGY §2.5).

The belief already inverts the (unfakeable) scent; a verbal hint is *extra* evidence that
MAY lie. ``HintFuser`` parses the opponent's words into a direction claim, fuses it into
belief weighted by a Beta-ledger reliability r_t (seeded from the cross-sub-game profiler),
and folds the scent-vs-hint consistency back into the ledger — so a caught liar is trusted
less every turn. Deterministic, zero-token: the claim parser is pure text (no LLM on the
move path). DEFAULT OFF (runtime builds a fuser only when ``strategy.fuse_hints`` is set),
and a no-op on the stand-in belief that lacks ``fuse_hint`` — so it never perturbs a game
that did not opt in. Whether it *helps* is a lab question (under reference scent belief is
already near-perfect); it ships gated so the evidence decides.
"""

from __future__ import annotations

import re
from typing import Any

_DIR_WORDS = {"N": "north", "S": "south", "E": "east", "W": "west"}


def parse_claim(hint: str, move_set: Any) -> dict[str, Any] | None:
    """Best-effort direction claim from free text; None when nothing checkable is said."""
    low = (hint or "").lower()
    allowed = {d: w for d, w in _DIR_WORDS.items() if d in set(move_set)}
    for direction, word in allowed.items():
        if re.search(rf"\b{word}\b", low) or re.search(rf"\b{direction}\b", hint or ""):
            return {"claimed_direction": direction, "confidence": 1.0}
    return None


class HintFuser:
    """Per-sub-game hint→belief fusion with a reliability ledger (seeded by the profiler)."""

    def __init__(self, ledger: Any, move_set: Any) -> None:
        self.ledger = ledger  # ReliabilityLedger; its prior may come from a lie-profile
        self._move_set = list(move_set)

    def fuse(self, belief: Any, hint: str) -> None:
        """Fuse one opponent hint into belief, then fold the consistency into the ledger."""
        if not hasattr(belief, "fuse_hint"):
            return  # stand-in belief (lab/stage-2): fusion is a structural no-op
        claim = parse_claim(hint, self._move_set)
        if claim is None:
            return
        consistency = belief.fuse_hint(claim, self.ledger.value())
        if consistency is not None:
            self.ledger.update(consistency)


def build_hint_fuser(config: Any) -> HintFuser | None:
    """Gated (private ``strategy.fuse_hints``) HintFuser; None on off/any error (non-fatal)."""
    try:
        if not bool(config.private("strategy.fuse_hints")):
            return None
        from pursuit.domain.belief.reliability import ReliabilityLedger

        belief = config.private("belief")
        r0 = float(belief.get("hint_trust_prior", 0.5))
        strength = float(belief.get("hint_prior_strength", 2.0))
        ledger = ReliabilityLedger({
            "hint_alpha0": max(1e-6, r0 * strength), "hint_beta0": max(1e-6, (1 - r0) * strength),
            "reliability_forget": float(belief.get("reliability_forget", 0.95)),
            "injection_penalty": float(config.private("llm_defense.injection_penalty"))})
        return HintFuser(ledger, config.game("movement_and_barriers.move_set"))
    except Exception:  # noqa: BLE001 — a best-effort edge is never fatal
        return None
