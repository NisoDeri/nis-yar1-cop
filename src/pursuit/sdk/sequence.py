"""Cross-process ordering gate for fixed-role league series."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from pursuit.exceptions import DeadlineError


class FileSeriesGate:
    """Keep both role servers online while admitting sub-games strictly in order."""

    def __init__(
        self,
        directory: str | Path,
        *,
        timeout: float,
        poll_interval: float = 0.25,
        reporter: Callable[[str], None] | None = None,
    ) -> None:
        self.directory = Path(directory).resolve()
        self.timeout = float(timeout)
        self.poll_interval = float(poll_interval)
        self.reporter = reporter
        self.directory.mkdir(parents=True, exist_ok=True)

    def _marker(self, number: int) -> Path:
        return self.directory / f"sub-game-{number:02d}.complete.json"

    def wait(self, number: int) -> None:
        """Wait until the immediately preceding sub-game has fully settled."""
        if number <= 1:
            return
        previous = self._marker(number - 1)
        if self.reporter is not None:
            self.reporter(f"waiting_for_sub_game={number - 1}")
        deadline = time.monotonic() + self.timeout
        while not previous.is_file():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DeadlineError(
                    f"sub-game {number} gate timed out waiting for sub-game {number - 1}"
                )
            time.sleep(min(self.poll_interval, remaining))
        if self.reporter is not None:
            self.reporter(f"gate_open_after_sub_game={number - 1}")

    def complete(self, number: int) -> None:
        """Atomically publish completion after the window's audit attempt."""
        marker = self._marker(number)
        temporary = marker.with_name(f".{marker.name}.{os.getpid()}.tmp")
        payload = {
            "sub_game_number": number,
            "completed_at": datetime.now(UTC).isoformat(),
            "pid": os.getpid(),
        }
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.replace(temporary, marker)
        if self.reporter is not None:
            self.reporter(f"sub_game_complete={number}")
