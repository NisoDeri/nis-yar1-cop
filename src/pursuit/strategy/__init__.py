"""pursuit.strategy — the graded core: deterministic heuristic brains v1 (STRATEGY §3-§4).

Public surface per architecture.md §strategy: the reference-compatible contract
(``BrainBase``/``Decision``), the shipped brains, the zero-token talk provider,
and the ``[strategy]``-driven loader (``resolve_brain``/``load_brain_cls``).
"""

from pursuit.strategy.base import BeliefLike, BrainBase, Decision, TalkLike, mode_probability
from pursuit.strategy.greedy import GreedyPoliceBrain, GreedyThiefBrain
from pursuit.strategy.police import InterceptorPoliceBrain
from pursuit.strategy.resolve import load_brain_cls, resolve_brain
from pursuit.strategy.talk import TemplateTalk
from pursuit.strategy.thief import SurvivorThiefBrain

__all__ = [
    "BeliefLike",
    "BrainBase",
    "Decision",
    "GreedyPoliceBrain",
    "GreedyThiefBrain",
    "InterceptorPoliceBrain",
    "SurvivorThiefBrain",
    "TalkLike",
    "TemplateTalk",
    "load_brain_cls",
    "mode_probability",
    "resolve_brain",
]
