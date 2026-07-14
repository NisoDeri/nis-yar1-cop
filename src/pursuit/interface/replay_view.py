"""Tkinter step-through replay of a sealed series log, gated on a live commit audit.

This is OUR own single-side log: only my positions are known, so the belief heatmap is
uniform (nothing is inferred about the opponent). The banner reflects
:func:`replay_verify.verify_log` — green ``VERIFIED OK`` when every sealed commit
reseals, red ``AUDIT FAILED`` otherwise. Import is headless-safe: on a machine without a
display the tkinter import is caught and any attempt to build a viewer raises a clear
RuntimeError instead of crashing at import time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pursuit.interface.replay_verify import grid_size, parse_state, verify_log

try:
    import tkinter as tk

    from pursuit.interface.board_view import CELL_PX, BoardView
except Exception as exc:  # pragma: no cover - headless / no Tk display
    _IMPORT_ERROR: Exception | None = exc
    tk = None  # type: ignore[assignment]
    CELL_PX = 52
    BoardView = None  # type: ignore[assignment]
else:
    _IMPORT_ERROR = None


def _cell(raw: Any) -> tuple[int, int] | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return (int(raw[0]), int(raw[1]))
    return None


class ReplayViewer:
    """Prev/Next replay of a ``{summary, records}`` log with a verification banner."""

    def __init__(self, log_path: str | Path) -> None:
        if _IMPORT_ERROR is not None:
            raise RuntimeError(f"tkinter unavailable — cannot open replay GUI: {_IMPORT_ERROR}")
        self._path = Path(log_path)
        doc = json.loads(self._path.read_text(encoding="utf-8"))
        summary = doc.get("summary", {}) if isinstance(doc, dict) else {}
        records = doc.get("records", []) if isinstance(doc, dict) else []
        self._role = str(summary.get("role", "police"))
        self._audit = verify_log(self._path)
        self._frames = [
            r for r in records
            if isinstance(r, dict) and isinstance(r.get("payload"), dict)
            and r["payload"].get("position") is not None
        ]
        self._size = self._detect_size(records)
        self._idx = 0

    @staticmethod
    def _detect_size(records: list[Any]) -> int:
        for rec in records:
            payload = rec.get("payload", {}) if isinstance(rec, dict) else {}
            size = grid_size(payload.get("state")) if isinstance(payload, dict) else None
            if size:
                return size
        raise RuntimeError("board size not present in log (no grid=NxN state string)")

    def _uniform(self) -> list[list[float]]:
        val = 1.0 / (self._size * self._size)
        return [[val] * self._size for _ in range(self._size)]

    def run(self) -> None:
        """Open the window and drive the interactive replay (blocks on mainloop)."""
        root = self._make_root()
        self._banner(root)
        board = BoardView(root, self._size)
        board.pack(padx=4, pady=4)
        info = tk.StringVar(value="")
        tk.Label(root, textvariable=info, font=("Segoe UI", 10)).pack()
        belief = self._uniform()

        def show(idx: int) -> None:
            payload = self._frames[idx]["payload"]
            _, barriers = parse_state(payload.get("state"))
            board.render(
                my_pos=_cell(payload.get("position")), role=self._role,
                barriers=barriers, visited=[], belief_matrix=belief,
                message=payload.get("hint"),
            )
            if not self._audit["passed"]:
                self._overlay_failed(board)
            info.set(
                f"Step {payload.get('step', idx)} / {len(self._frames)}"
                f"   move={payload.get('move', '')}"
            )

        self._buttons(root, show)
        if self._frames:
            show(0)
        root.mainloop()

    def _make_root(self) -> Any:
        try:
            root = tk.Tk()
        except Exception as exc:  # pragma: no cover - headless
            raise RuntimeError(f"cannot create Tk window (headless display?): {exc}") from exc
        root.title(f"Replay — {self._path.name}")
        root.resizable(False, False)
        return root

    def _banner(self, root: Any) -> None:
        passed = self._audit["passed"]
        text = "VERIFIED OK" if passed else "AUDIT FAILED"
        color = "#27ae60" if passed else "#c0392b"
        tk.Label(
            root, text=f"{text}   ({self._audit['dialect']} dialect)", bg=color, fg="white",
            font=("Segoe UI", 12, "bold"), pady=6,
        ).pack(fill="x")

    def _buttons(self, root: Any, show: Any) -> None:
        frame = tk.Frame(root)
        frame.pack(pady=4)

        def step(delta: int) -> None:
            self._idx = max(0, min(len(self._frames) - 1, self._idx + delta))
            if self._frames:
                show(self._idx)

        tk.Button(frame, text="< Prev", command=lambda: step(-1)).pack(side="left", padx=4)
        tk.Button(frame, text="Next >", command=lambda: step(1)).pack(side="left", padx=4)

    @staticmethod
    def _overlay_failed(board: Any) -> None:
        side = board.board_size * CELL_PX
        board.create_rectangle(0, side // 3, side, 2 * side // 3, fill="#c0392b", outline="")
        board.create_text(
            side // 2, side // 2, text="AUDIT FAILED",
            fill="white", font=("Segoe UI", 22, "bold"),
        )
