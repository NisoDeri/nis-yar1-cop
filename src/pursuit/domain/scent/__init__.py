"""Scent dialect seam (DECISIONS.md D3) — one factory, two locked laws.

The signed shared config's ``pheromones`` block selects the dialect; because
the dialect id lives inside the signed terms and its worked example is hashed
(rule 23, ``pheromones.formula_sha256``), a cross-dialect pairing is refused at
negotiation instead of silently corrupting a game (architecture.md §3).
"""

from pursuit.domain.scent.base import ScentModel
from pursuit.domain.scent.book import BookScent
from pursuit.domain.scent.book_v1 import MultiplicativeBookV1Scent
from pursuit.domain.scent.params import STAMP_LAW, ScentParams
from pursuit.domain.scent.reference import ReferenceScent
from pursuit.exceptions import ConfigError

_DIALECTS: dict[str, type[ScentModel]] = {
    BookScent.dialect: BookScent,
    ReferenceScent.dialect: ReferenceScent,
    MultiplicativeBookV1Scent.dialect: MultiplicativeBookV1Scent,
}
_PARAM_KEYS = tuple(ScentParams.__dataclass_fields__)


def make_scent_model(pheromones_cfg: dict) -> ScentModel:
    """Build the negotiated scent model from the signed ``pheromones`` terms.

    ``dialect`` defaults to ``"book"`` — NotebookLM ruling A2: the book
    equation is the standard, ``"reference"`` is a legal negotiated alternative
    (D3). Every numeric term is REQUIRED — no code defaults, per the sealing
    ``REQUIRED_TERMS`` fail-fast discipline (reference_map.md §2.3).
    """
    dialect = pheromones_cfg.get("dialect", BookScent.dialect)
    model_cls = _DIALECTS.get(dialect)
    if model_cls is None:
        raise ConfigError(f"unknown pheromones dialect {dialect!r} (allowed: {sorted(_DIALECTS)})")
    missing = sorted(key for key in _PARAM_KEYS if key not in pheromones_cfg)
    if missing:
        raise ConfigError(f"pheromones config missing required terms: {missing}")
    return model_cls(ScentParams(**{key: pheromones_cfg[key] for key in _PARAM_KEYS}))


__all__ = [
    "STAMP_LAW",
    "BookScent",
    "MultiplicativeBookV1Scent",
    "ReferenceScent",
    "ScentModel",
    "ScentParams",
    "make_scent_model",
]
