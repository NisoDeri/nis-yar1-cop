"""Headless replay auditor — recompute every sealed commit off a real series log.

The on-disk log (``sdk/series.py``) is a JSON object ``{"summary": {...},
"records": [...]}``; each record is ``{"payload": {...}, "nonce": "<hex>",
"commit": "<hex>"}`` and the commit is ``dialect.commit(payload, nonce)`` — NOT a bare
``sha256(payload)``. Two dialects exist in the league (``reference`` = nonce
pipe-appended, ``book`` = nonce inside the canonical JSON); a record is accepted if
EITHER verifies, so this auditor reads a partner's log without pre-negotiating which one
they used. Pure and I/O-free apart from the single file read in :func:`verify_log`; the
``parse_state`` / ``grid_size`` helpers are shared with the Tkinter viewer.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from pursuit.domain.crypto import make_hash_dialect

_SELF_RE = re.compile(r"self=(\[-?\d+,\s*-?\d+\])")
_BARRIERS_RE = re.compile(r"barriers=(\[.*\])")
_GRID_RE = re.compile(r"grid=(\d+)x(\d+)")
_DIALECTS = ("reference", "book")

Cell = tuple[int, int]


def _literal(text: str) -> Any:
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def _as_cell(raw: Any) -> Cell | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            return (int(raw[0]), int(raw[1]))
        except (TypeError, ValueError):
            return None
    return None


def parse_state(state_str: Any) -> tuple[Cell | None, list[Cell]]:
    """Parse a sealed ``grid=NxN;self=[r, c];barriers=[[r, c], ...]`` state string.

    Returns ``(self_pos, barriers)``; the barrier list is the FULL accumulated set known
    at that step (the state string already carries every barrier declared so far, so the
    viewer needs no separate running total). Total over junk input — unparseable fields
    become ``None`` / ``[]``, never a crash.
    """
    if not isinstance(state_str, str):
        return None, []
    self_match = _SELF_RE.search(state_str)
    pos = _as_cell(_literal(self_match.group(1))) if self_match else None
    barriers: list[Cell] = []
    barrier_match = _BARRIERS_RE.search(state_str)
    if barrier_match:
        raw = _literal(barrier_match.group(1))
        if isinstance(raw, list):
            barriers = [c for c in (_as_cell(x) for x in raw) if c is not None]
    return pos, barriers


def grid_size(state_str: Any) -> int | None:
    """Board edge length from a ``grid=NxN`` prefix — the log's own board parameter."""
    if isinstance(state_str, str):
        match = _GRID_RE.search(state_str)
        if match:
            return int(match.group(1))
    return None


def _step_of(record: Any, index: int) -> int:
    if isinstance(record, dict):
        payload = record.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("step"), int):
            return payload["step"]
    return index


def _verifies(record: Any, dialect: Any) -> bool:
    """True iff ``dialect`` reseals this record's payload+nonce to its stored commit."""
    if not isinstance(record, dict):
        return False
    payload, nonce, commit = record.get("payload"), record.get("nonce"), record.get("commit")
    if not (isinstance(payload, dict) and isinstance(nonce, str) and isinstance(commit, str)):
        return False
    return dialect.verify(payload, nonce, commit)


def audit_records(records: list[Any], summary: dict[str, Any]) -> dict[str, Any]:
    """Pure audit core: per-record pass/fail under both dialects + a summary verdict."""
    dialects = {name: make_hash_dialect({"dialect": name}) for name in _DIALECTS}
    ref_ok = [_verifies(r, dialects["reference"]) for r in records]
    book_ok = [_verifies(r, dialects["book"]) for r in records]
    failed_steps = [
        _step_of(records[i], i) for i in range(len(records)) if not (ref_ok[i] or book_ok[i])
    ]
    needs_ref = any(r and not b for r, b in zip(ref_ok, book_ok, strict=True))
    needs_book = any(b and not r for r, b in zip(ref_ok, book_ok, strict=True))
    if needs_ref and needs_book:
        dialect = "mixed"
    elif needs_book:
        dialect = "book"
    elif needs_ref:
        dialect = "reference"
    else:
        dialect = "reference" if sum(ref_ok) >= sum(book_ok) else "book"
    return {
        "passed": bool(records) and not failed_steps,
        "n_records": len(records),
        "failed_steps": failed_steps,
        "dialect": dialect,
        "game_id": str(summary.get("game_id", "")),
        "result": str(summary.get("result", "")),
    }


def verify_log(path: str | Path) -> dict[str, Any]:
    """Read a ``{summary, records}`` series log and audit every sealed commit.

    Picks whichever dialect verifies each record (``reference`` or ``book``); ``dialect``
    is ``"mixed"`` when both were genuinely needed. ``passed`` is True only if every
    record reseals to its stored commit under at least one dialect.
    """
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    summary = doc.get("summary", {}) if isinstance(doc, dict) else {}
    records = doc.get("records", []) if isinstance(doc, dict) else []
    return audit_records(list(records), summary if isinstance(summary, dict) else {})
