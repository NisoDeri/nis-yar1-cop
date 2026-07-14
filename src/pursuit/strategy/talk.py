"""TemplateTalk — the zero-token hint provider (D8 template mode; STRATEGY §5, §8.3).

A 48-line landmark-aware bank. Mechanical guarantees (rule 26-27, STRATEGY §8.3):
the word cap is enforced by truncation AFTER formatting, digit-bearing words are
dropped (free NL only, never numeric coordinates), and the whole bank plus every
landmark name is linted digit-free at import. ``verdict`` truthfully labels intent
(STRATEGY §8.9): lines claiming a concrete (invented) location are tagged "lie";
atmosphere lines that assert nothing checkable are tagged "truth".
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pursuit.constants import Role
from pursuit.exceptions import ConfigError

TRUTH, LIE = "truth", "lie"  # the INTEROP §2.3 verdict literals

_LANDMARKS: dict[str, tuple[str, ...]] = {
    "New York": ("Times Square", "Central Park", "the Brooklyn Bridge",
                 "Grand Central", "the Village", "Wall Street"),
    "London": ("Big Ben", "Camden Market", "the Tube", "Tower Bridge",
               "Soho", "Piccadilly Circus"),
    "Paris": ("the Eiffel Tower", "the Louvre", "Montmartre", "the Seine",
              "the Marais", "the Latin Quarter"),
}
_GENERIC_LANDMARKS = ("the old market", "the clock tower", "the river bend", "the north gate")

_THIEF_TRUTH = (
    "Still breathing, still moving; catch me if you can.",
    "The streets remember me; your boots they only tolerate.",
    "Every alley whispers my name and none of them repeat it.",
    "I trade in shadows and the market is generous tonight.",
    "Your footsteps echo; mine never do.",
    "Keep chasing rumors, officer; I collect them for fun.",
    "The city hides those who listen to it.",
    "I am wherever the lamplight fails you.",
    "Patience is your enemy and my oldest friend.",
    "You look tired; I could run this dance forever.",
    "The wind changes faster than your plans.",
    "No cage fits someone made of fog.",
)
_THIEF_LIE = (
    "I am resting right beside {landmark}, come say hello.",
    "You just missed me at {landmark}; the crowd was lovely.",
    "Heading straight for {landmark}, no detours this time.",
    "I left my coat near {landmark}; fetching it now.",
    "Meet me by {landmark} if you dare.",
    "The view from {landmark} is wasted on you.",
    "I am circling {landmark} until sunrise.",
    "Ask the pigeons at {landmark}; they saw me pass.",
    "I am camped in the shadow of {landmark} tonight.",
    "Strolling past {landmark} as we speak, officer.",
    "My trail ends at {landmark}; the rest you imagine.",
    "Waiting out the night at {landmark}, cozy as ever.",
)
_POLICE_TRUTH = (
    "The net is tightening and you already feel it.",
    "Every step you take costs you a street.",
    "I do not chase; I herd.",
    "Your options are thinner than yesterday's alibi.",
    "The walls you fear are the ones I have not built yet.",
    "Run all you like; the map is on my side.",
    "I have patience, a budget, and your pattern.",
    "The city closes like a hand, finger by finger.",
    "You repeat yourself; thieves always do.",
    "My patrol never sleeps and never guesses twice.",
    "Each barrier is a promise I intend to keep.",
    "The clock is my partner and it never takes bribes.",
)
_POLICE_LIE = (
    "My patrol is stuck out by {landmark} tonight.",
    "I am wasting my shift watching {landmark}.",
    "Half my attention is on {landmark}; lucky you.",
    "Orders keep me anchored near {landmark} for now.",
    "I lost your scent somewhere around {landmark}.",
    "The trail went cold by {landmark}; enjoy it.",
    "I am doubling back toward {landmark} as we speak.",
    "Paperwork chains me to {landmark} this evening.",
    "My best guess puts you nowhere near {landmark}.",
    "I am searching {landmark} block by block.",
    "Backup is meeting me at {landmark}; slow night.",
    "I could swear you were hiding behind {landmark}.",
)

_BANK: dict[Role, dict[str, tuple[str, ...]]] = {
    Role.THIEF: {TRUTH: _THIEF_TRUTH, LIE: _THIEF_LIE},
    Role.POLICE: {TRUTH: _POLICE_TRUTH, LIE: _POLICE_LIE},
}
BANK_LINES: tuple[str, ...] = _THIEF_TRUTH + _THIEF_LIE + _POLICE_TRUTH + _POLICE_LIE


def _lint_digit_free(lines: Iterable[str]) -> None:
    """Rule-27 lint: numeric coordinates can never originate from this module."""
    for line in lines:
        if any(ch.isdigit() for ch in line):
            raise ConfigError(f"digit found in hint bank/landmark line: {line!r}")


_lint_digit_free(BANK_LINES)
_lint_digit_free(name for names in _LANDMARKS.values() for name in names)
_lint_digit_free(_GENERIC_LANDMARKS)


class TemplateTalk:
    """rng-injected, setting-aware, cap-enforcing hint generator; prompt is always ''."""

    def __init__(self, rng: Any, setting: str, hint_max_words: int, *,
                 lie_rate: float = 0.2) -> None:
        if int(hint_max_words) < 1:
            raise ConfigError(f"hint_max_words must be >= 1, got {hint_max_words!r}")
        if not 0.0 <= float(lie_rate) <= 1.0:
            raise ConfigError(f"lie_rate must be in [0, 1], got {lie_rate!r}")
        self.rng = rng
        self.setting = setting
        self.hint_max_words = int(hint_max_words)
        self.lie_rate = float(lie_rate)  # default mirrors STRATEGY §7 deception.lie_rate_cap

    def say(self, role: Role, state: Any, belief: Any, setting: str,
            opponent_hint: str, deadline: float | None) -> tuple[str, str, str, str]:
        """Return (hint, verdict, reasoning, prompt) — template mode ignores state/belief."""
        arena = setting or self.setting
        landmark = self.rng.choice(_LANDMARKS.get(arena, _GENERIC_LANDMARKS))
        verdict = LIE if self.rng.random() < self.lie_rate else TRUTH
        line = self.rng.choice(_BANK[Role(role)][verdict])
        hint = self._enforce(line.format(landmark=landmark))
        reasoning = f"template bank ({verdict}) for the {arena or 'generic'} setting; zero tokens"
        return hint, verdict, reasoning, ""

    def _enforce(self, text: str) -> str:
        """Mechanical rule 26-27 gate: drop digit-bearing words, truncate to the cap."""
        words = [w for w in text.split() if not any(ch.isdigit() for ch in w)]
        return " ".join(words[: self.hint_max_words])
