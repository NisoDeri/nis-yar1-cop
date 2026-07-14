"""run_live — a self-contained live GUI demo of one peer with the belief heatmap.

Starts a :class:`PeerWindow` on the MAIN thread and runs ``run_peer`` (fake-opponent by
default, so a SINGLE process shows a whole game) in a daemon thread. The runtime's
``observer`` pushes per-tick snapshots into a queue that :class:`LiveGameDriver` pumps
onto the Tk main loop. Tk is imported lazily and guarded, so importing this module — and
the pure :func:`board_snapshot` builder :class:`PeerRuntime` calls — never needs a display.
"""

from __future__ import annotations

import queue
from pathlib import Path
from typing import Any

from pursuit.exceptions import PursuitError


def board_snapshot(runtime: Any, status: str,
                   hint_in: str = "", hint_out: str = "") -> dict[str, Any]:
    """Pure per-tick view dict for the live observer (no Tk, no I/O)."""
    state = runtime.state
    size = state.board.size
    to_matrix = getattr(runtime.belief, "as_matrix", None)
    matrix = (to_matrix() if callable(to_matrix)
              else [[1.0 / (size * size)] * size for _ in range(size)])
    return {"step": state.step_number, "role": runtime.role.value,
            "my_pos": state.position, "barriers": list(state.barriers),
            "visited": list(state.visited), "belief_matrix": matrix,
            "hint_in": hint_in, "hint_out": hint_out, "status": status}


def _observer(events: queue.Queue) -> Any:
    """A runtime observer that fans a snapshot out to a render + turn-banner event."""
    def push(view: dict[str, Any]) -> None:
        events.put_nowait({"type": "render", **view})
        events.put_nowait({"type": "turn", "mine": view.get("status") == "my_turn"})
    return push


def run_live(config_dir: str | Path, role: str, *, fake_opponent: bool = True) -> dict[str, Any]:
    """Open the live window and play one series in a daemon thread (blocks on mainloop).

    Fake-opponent by default: one process, one window, a full game with the live belief
    heatmap. Raises :class:`PursuitError` on a headless machine (no Tk display).
    """
    from pursuit.shared.config import ConfigManager

    size = int(ConfigManager.load(config_dir).game("board_and_agents.grid_size"))
    events: queue.Queue = queue.Queue()
    holder: dict[str, Any] = {}
    try:
        from pursuit.interface.live_game import LiveGameDriver, start_game_thread
        from pursuit.interface.window import PeerWindow
        from pursuit.sdk import run_peer

        window = PeerWindow(f"pursuit live — {role}", size, role)
    except Exception as exc:  # noqa: BLE001 — headless / missing Tk display
        raise PursuitError(f"live GUI unavailable (headless display?): {exc}") from exc

    def play() -> None:
        holder["summary"] = run_peer(config_dir, role, fake_opponent=fake_opponent,
                                     observer=_observer(events))

    driver = LiveGameDriver(role, events)
    start_game_thread(play)
    driver.attach(window)
    window.mainloop()
    return holder.get("summary", {"status": "gui_closed"})
