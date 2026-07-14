from __future__ import annotations

import tkinter as tk

CELL_PX = 52
ROLE_COLORS = {"thief": "#e67e22", "police": "#2980b9"}


class BoardView(tk.Canvas):
    def __init__(self, parent: tk.Misc, board_size: int) -> None:
        self.board_size = board_size
        side = board_size * CELL_PX
        super().__init__(
            parent, width=side, height=side, bg="white",
            highlightthickness=1, highlightbackground="#888",
        )

    def _cell_rect(self, row: int, col: int) -> tuple[int, int, int, int]:
        x0, y0 = col * CELL_PX, row * CELL_PX
        return x0, y0, x0 + CELL_PX, y0 + CELL_PX

    @staticmethod
    def _heat_color(probability: float, peak: float) -> str:
        if peak <= 0:
            return "#ffffff"
        level = min(1.0, probability / peak)
        green_blue = int(255 * (1 - 0.8 * level))
        return f"#ff{green_blue:02x}{green_blue:02x}"

    def _draw_agent(self, pos: tuple[int, int], role: str, inset: int, outline: str) -> None:
        x0, y0, x1, y1 = self._cell_rect(*pos)
        self.create_oval(
            x0 + inset, y0 + inset, x1 - inset, y1 - inset,
            fill=ROLE_COLORS.get(role, "#555"), outline=outline, width=2,
        )
        self.create_text(
            (x0 + x1) // 2, (y0 + y1) // 2,
            text=role[0].upper(), fill="white", font=("Segoe UI", 14, "bold"),
        )

    def render(
        self,
        my_pos: tuple[int, int] | None,
        role: str,
        barriers: list[tuple[int, int]],
        visited: list[tuple[int, int]],
        belief_matrix: list[list[float]],
        opponent_pos: tuple[int, int] | None = None,
        opponent_role: str | None = None,
        message: str | None = None,
    ) -> None:
        self.delete("all")
        peak = max((p for row in belief_matrix for p in row), default=0.0)
        for row in range(self.board_size):
            for col in range(self.board_size):
                self.create_rectangle(
                    *self._cell_rect(row, col),
                    outline="#ccc",
                    fill=self._heat_color(belief_matrix[row][col], peak),
                )
        for cell in visited:
            x0, y0, x1, y1 = self._cell_rect(*cell)
            self.create_oval(x0 + 21, y0 + 21, x1 - 21, y1 - 21, fill="#b0bec5", outline="")
        for cell in barriers:
            x0, y0, x1, y1 = self._cell_rect(*cell)
            self.create_rectangle(x0 + 4, y0 + 4, x1 - 4, y1 - 4, fill="#263238", outline="")
        if opponent_pos is not None and opponent_role:
            self._draw_agent(opponent_pos, opponent_role, 14, "black")
        if my_pos is not None:
            self._draw_agent(my_pos, role, 8, "black")
        if message:
            w = self.board_size * CELL_PX
            self.create_rectangle(0, 0, w, 22, fill="#ffe082", outline="")
            self.create_text(
                w // 2, 11, text=message, fill="#5d4037",
                font=("Segoe UI", 10, "bold"),
            )
