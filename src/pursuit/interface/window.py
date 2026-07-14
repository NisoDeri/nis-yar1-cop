from __future__ import annotations

import tkinter as tk
from typing import Any

from pursuit.interface.board_view import CELL_PX, BoardView

_LABEL_KEYS = (
    "step", "role", "barriers",
    "hint_in", "hint_out", "verdict",
    "commit", "status",
)
_BANNER_MINE = "#27ae60"
_BANNER_WAIT = "#7f8c8d"


class PeerWindow:
    """Main Tkinter window: banner + BoardView + side-panel labels."""

    def __init__(self, title: str, board_size: int, role: str) -> None:
        self._root = tk.Tk()
        self._root.title(title)
        self._root.resizable(False, False)
        self._board_size = board_size
        self._role = role

        self._banner = tk.Label(
            self._root, text="", bg=_BANNER_WAIT, fg="white",
            font=("Segoe UI", 12, "bold"), pady=6,
        )
        self._banner.pack(fill="x")

        body = tk.Frame(self._root)
        body.pack(fill="both", expand=True)

        self._board = BoardView(body, board_size)
        self._board.pack(side="left", padx=4, pady=4)

        panel = tk.Frame(body, padx=8, pady=4)
        panel.pack(side="left", fill="y")

        self._labels: dict[str, tk.Label] = {}
        for key in _LABEL_KEYS:
            tk.Label(
                panel, text=f"{key}:", font=("Segoe UI", 9, "bold"), anchor="w",
            ).pack(fill="x")
            lbl = tk.Label(
                panel, text="—", font=("Segoe UI", 9), anchor="w", wraplength=160,
            )
            lbl.pack(fill="x", pady=(0, 4))
            self._labels[key] = lbl

        self._blank_belief: list[list[float]] = [[0.0] * board_size for _ in range(board_size)]

    # ---- public API ----

    def render(self, view_dict: dict[str, Any]) -> None:
        """Update board canvas and side-panel labels from a view snapshot dict."""
        belief = view_dict.get("belief_matrix", self._blank_belief)
        self._board.render(
            my_pos=view_dict.get("my_pos"),
            role=view_dict.get("role", self._role),
            barriers=view_dict.get("barriers", []),
            visited=view_dict.get("visited", []),
            belief_matrix=belief,
            opponent_pos=view_dict.get("opponent_pos"),
            opponent_role=view_dict.get("opponent_role"),
            message=view_dict.get("message"),
        )
        for key, lbl in self._labels.items():
            if key in view_dict:
                lbl.config(text=str(view_dict[key]))

    def set_turn(self, mine: bool, text: str | None = None) -> None:
        """Green banner on my turn; grey while waiting."""
        color = _BANNER_MINE if mine else _BANNER_WAIT
        label = text or ("YOUR TURN" if mine else "Waiting for opponent…")
        self._banner.config(bg=color, text=label)

    def set_label(self, key: str, value: Any) -> None:
        """Update a single side-panel label by key."""
        if key in self._labels:
            self._labels[key].config(text=str(value))

    def show_verified_ok(self) -> None:
        """Draw a big green 'VERIFIED OK' overlay on the board (for replay screenshot)."""
        side = self._board_size * CELL_PX
        self._board.create_rectangle(0, side // 3, side, 2 * side // 3, fill="#27ae60", outline="")
        self._board.create_text(
            side // 2, side // 2,
            text="VERIFIED OK", fill="white", font=("Segoe UI", 22, "bold"),
        )

    def mainloop(self) -> None:
        self._root.mainloop()

    def after(self, ms: int, fn: Any) -> None:
        self._root.after(ms, fn)
