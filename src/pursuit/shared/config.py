"""ConfigManager — the single doorway for every game parameter (brief §10).

Loads the three per-role config files (reference_map §6 split):

* ``game.json``   — SHARED agreed terms (Appendix F), byte-identical on both
  peers, signed in the handshake;
* ``game.toml``   — PRIVATE local settings (stdlib :mod:`tomllib`), never shared;
* ``rate_limits.json`` — private per-service Gatekeeper limits (table 19).

``validate_agreement`` fail-fasts on any missing agreed term BEFORE the
handshake: the reference translates only a subset of game.json into runtime,
so private defaults silently beat agreed values (reference_map §6 traps) —
we refuse to start instead, naming the term and the file (ConfigError).
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from pursuit.exceptions import ConfigError

GAME_JSON = "game.json"
GAME_TOML = "game.toml"
RATE_LIMITS_JSON = "rate_limits.json"

#: Agreed terms that MUST exist in game.json — no code defaults anywhere.
REQUIRED_AGREED_TERMS: tuple[str, ...] = (
    "board_and_agents.grid_size",
    "board_and_agents.thief_start",
    "board_and_agents.cop_start",
    "movement_and_barriers.move_set",
    "movement_and_barriers.max_barriers",
    "movement_and_barriers.max_moves",
    "movement_and_barriers.survival_threshold",
    "scoring.capture_cop",
    "scoring.capture_thief",
    "scoring.survival_cop",
    "scoring.survival_thief",
    "scoring.tie_score",
    "scoring.technical_loss",
    "pheromones.dialect",
    "pheromones.pheromone_center_intensity",
    "pheromones.pheromone_decay",
    "pheromones.pheromone_grid_size",
    "pheromones.pheromone_min_center_intensity",
    "crypto.dialect",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"missing config file {path.name} in {path.parent}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path.name}: {exc}") from exc


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"missing config file {path.name} in {path.parent}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path.name}: {exc}") from exc


def _lookup(tree: dict[str, Any], key_path: str, file_name: str, label: str = "term") -> Any:
    node: Any = tree
    for part in key_path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ConfigError(f"missing {label} '{key_path}' in {file_name}")
        node = node[part]
    return node


class ConfigManager:
    """Immutable view over the three loaded config trees; dotted-path access."""

    def __init__(
        self,
        game_terms: dict[str, Any],
        private_terms: dict[str, Any],
        rate_limits: dict[str, Any],
    ) -> None:
        self._game = game_terms
        self._private = private_terms
        self._rate_limits = rate_limits

    @classmethod
    def load(cls, config_dir: str | Path) -> ConfigManager:
        """Read game.json + game.toml + rate_limits.json from ``config_dir``."""
        base = Path(config_dir)
        return cls(
            game_terms=_read_json(base / GAME_JSON),
            private_terms=_read_toml(base / GAME_TOML),
            rate_limits=_read_json(base / RATE_LIMITS_JSON),
        )

    def validate_agreement(self) -> None:
        """Fail-fast: every REQUIRED agreed term present, else ConfigError."""
        for term in REQUIRED_AGREED_TERMS:
            _lookup(self._game, term, GAME_JSON, label="agreed term")

    def game(self, key_path: str) -> Any:
        """Dotted-path read from the shared game.json (agreed terms)."""
        return _lookup(self._game, key_path, GAME_JSON)

    def private(self, key_path: str) -> Any:
        """Dotted-path read from the private game.toml."""
        return _lookup(self._private, key_path, GAME_TOML)

    def service_limits(self, service: str) -> dict[str, Any]:
        """Gatekeeper limits block for one service (gmail / ollama / ...)."""
        return _lookup(self._rate_limits, service, RATE_LIMITS_JSON, label="service")

    @staticmethod
    def per_game_config_name(game_id: str, sub_game: int) -> str:
        """Book-mandated per-game filename: ``config_<game_id>_g<NN>.json``."""
        return f"config_{game_id}_g{sub_game:02d}.json"

    def config_sha256(self) -> str:
        """SHA-256 of the canonical AGREED WIRE TERMS — the byte-identical config lock.

        Hashes ONLY the negotiated terms (``build_terms`` = the reference's
        ``terms_from_config`` 14-key set), NOT our local-only blocks (setting, num_games,
        crypto ``_note``, network) — so the mutual-agreement SHA reproduces byte-for-byte
        on a reference partner (review fix; a full-tree hash could never cross-match).
        The import is lazy: ``negotiation`` imports us, so a module-level import would cycle.
        """
        from pursuit.domain.crypto.canonical import canonical_bytes, sha256_hex
        from pursuit.domain.negotiation import build_terms

        return sha256_hex(canonical_bytes(build_terms(self)))
