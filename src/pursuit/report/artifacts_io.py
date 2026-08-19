"""JSON sink for the four game artifacts, split from :mod:`pursuit.report.artifacts`
so the pure builder module stays under the 150-line ceiling (same split rationale as
:mod:`pursuit.report.schema`). Only I/O lives here; nothing is hardcoded.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pursuit.report.schema import (
    config_filename,
    declaration_filename,
    log_filename,
    result_filename,
)


def _dump(path: Path, data: Mapping[str, Any]) -> str:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def write_artifacts(out_dir: str | Path, declaration: Mapping[str, Any],
                    configs: Sequence[Mapping[str, Any]], result: Mapping[str, Any],
                    logs: Sequence[Mapping[str, Any]]) -> list[str]:
    """Write all four artifact kinds under ``out_dir``; return the written paths.

    ``declaration`` and ``result`` are match-level; ``configs`` and ``logs`` are one file
    per sub-game, named with the zero-padded ``_g<NN>`` their ``sub_game_number`` gives.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    game_id = str(result.get("game_id") or "")
    paths = [
        _dump(out / declaration_filename(game_id), declaration),
        _dump(out / result_filename(game_id), result),
    ]
    for cfg in configs:
        number = int(cfg.get("sub_game_number", 0) or 0)
        paths.append(_dump(out / config_filename(game_id, number), cfg))
    for log in logs:
        number = int(log.get("summary", {}).get("sub_game_number", 0) or 0)
        paths.append(_dump(out / log_filename(game_id, number), log))
    return paths
