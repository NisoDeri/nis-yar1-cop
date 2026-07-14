"""resolve_brain — the ``[strategy]`` extension-point loader (ref-map §4.1, arch §strategy).

The private game.toml selects brain classes by ``'module:Class'``; unset -> our
shipped brains. A malformed or unloadable selector, or a class that is not a
``BrainBase`` subclass, raises :class:`~pursuit.exceptions.ConfigError` (fail-fast —
never a silent fallback).

Tuning kwargs for OUR brains are read from the private ``[police]`` / ``[thief]``
tables and passed through only when present, so every numeric default lives in
exactly one place: the brain constructors themselves.
"""

from __future__ import annotations

import importlib
from typing import Any

from pursuit.constants import Role
from pursuit.exceptions import ConfigError
from pursuit.strategy.base import BrainBase, TalkLike
from pursuit.strategy.police import InterceptorPoliceBrain
from pursuit.strategy.talk import TemplateTalk
from pursuit.strategy.thief import SurvivorThiefBrain

#: INTEROP §2.1: `setting` and `hint_max_words` carry protocol-pinned defaults
#: ("" and 15) when the negotiated terms omit them — the only sanctioned fallbacks.
_FALLBACK_SETTING = ""
_FALLBACK_HINT_MAX_WORDS = 15

_DEFAULT_BRAINS: dict[Role, type[BrainBase]] = {
    Role.POLICE: InterceptorPoliceBrain,
    Role.THIEF: SurvivorThiefBrain,
}
_SELECTOR_KEYS = {Role.POLICE: "strategy.police_class", Role.THIEF: "strategy.thief_class"}
_TUNING_TABLES: dict[Role, tuple[str, frozenset[str]]] = {
    Role.POLICE: ("police", frozenset({"barrier_finisher_p", "cage_radius"})),
    Role.THIEF: ("thief", frozenset({"w_dist", "w_mob", "mobility_k", "jail_min_mobility",
                                      "decoy_enabled", "decoy_margin"})),
}


def load_brain_cls(selector: Any) -> type[BrainBase]:
    """Import ``'module:Class'`` and require a BrainBase subclass (ref-map §4.1)."""
    if not isinstance(selector, str) or ":" not in selector:
        raise ConfigError(f"brain selector must look like 'module:Class', got {selector!r}")
    module_name, _, class_name = selector.partition(":")
    if not module_name or not class_name:
        raise ConfigError(f"brain selector must look like 'module:Class', got {selector!r}")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigError(f"cannot import brain module {module_name!r}: {exc}") from exc
    cls = getattr(module, class_name, None)
    if cls is None:
        raise ConfigError(f"module {module_name!r} has no attribute {class_name!r}")
    if not (isinstance(cls, type) and issubclass(cls, BrainBase)):
        raise ConfigError(f"{selector!r} does not name a BrainBase subclass")
    return cls


def _optional(reader: Any, key: str) -> Any:
    """A config read that treats a missing key as None (everything else propagates)."""
    try:
        return reader(key)
    except ConfigError:
        return None


def resolve_brain(config: Any, role: Role | str, rng: Any,
                  talk: TalkLike | None = None) -> BrainBase:
    """Instantiate the configured brain for ``role`` with injected talk + rng."""
    role = Role(role)
    selector = _optional(config.private, _SELECTOR_KEYS[role])
    cls = load_brain_cls(selector) if selector is not None else _DEFAULT_BRAINS[role]
    if talk is None:
        talk = _default_talk(config, rng)
    kwargs = _tuning_kwargs(config, role) if cls is _DEFAULT_BRAINS[role] else {}
    return cls(talk, rng, **kwargs)


def _tuning_kwargs(config: Any, role: Role) -> dict[str, Any]:
    """Private [police]/[thief] knobs, filtered to what the v1 constructors accept."""
    table_name, allowed = _TUNING_TABLES[role]
    table = _optional(config.private, table_name)
    if table is None:
        return {}
    if not isinstance(table, dict):
        raise ConfigError(f"[{table_name}] in game.toml must be a table, got {table!r}")
    return {key: value for key, value in table.items() if key in allowed}


def _default_talk(config: Any, rng: Any) -> TalkLike:
    """Talk seam from the shared world terms: Ollama banter when opted in, else TemplateTalk.

    ``[trash_talk] provider == "ollama"`` builds :class:`OllamaTalk` (local, $0) over an
    :class:`OllamaClient`; ANY construction error falls back to zero-token TemplateTalk, so
    LLM selection can never raise into the game. ``"template"`` (default) stays TemplateTalk.
    """
    setting = _optional(config.game, "world.setting")
    if setting is None:
        setting = _optional(config.game, "world.arena")  # arch §7.2 names the key 'arena'
    setting = _FALLBACK_SETTING if setting is None else str(setting)
    cap = _optional(config.game, "world.hint_max_words")
    cap = _FALLBACK_HINT_MAX_WORDS if cap is None else int(cap)
    if _optional(config.private, "trash_talk.provider") == "ollama":
        ollama = _ollama_talk(config, rng, setting, cap)
        if ollama is not None:
            return ollama
    return TemplateTalk(rng, setting, cap)


def _ollama_talk(config: Any, rng: Any, setting: str, cap: int) -> TalkLike | None:
    """Build OllamaTalk from the private ``[trash_talk]`` block; None on any failure."""
    try:
        from pursuit.infra.ollama import OllamaClient
        from pursuit.strategy.ollama_talk import OllamaTalk

        url = str(_optional(config.private, "trash_talk.ollama_url") or "http://localhost:11434")
        model = str(_optional(config.private, "trash_talk.model") or "qwen2.5:7b")
        deadline = float(_optional(config.private, "trash_talk.deadline_seconds") or 8.0)
        client = OllamaClient(url, model, deadline)
        return OllamaTalk(rng, setting, cap, client=client, deadline_seconds=deadline)
    except Exception:  # noqa: BLE001 — never let LLM talk construction crash the game
        return None
