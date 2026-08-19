from __future__ import annotations

import threading
import time

import pytest

from pursuit.exceptions import DeadlineError
from pursuit.sdk.sequence import FileSeriesGate


def test_gate_blocks_until_previous_sub_game_completes(tmp_path):
    gate = FileSeriesGate(tmp_path / "gate", timeout=1.0, poll_interval=0.01)
    opened = threading.Event()

    waiter = threading.Thread(target=lambda: (gate.wait(2), opened.set()), daemon=True)
    waiter.start()
    time.sleep(0.05)
    assert not opened.is_set()

    gate.complete(1)
    waiter.join(timeout=1.0)
    assert opened.is_set()


def test_gate_times_out_when_previous_sub_game_never_completes(tmp_path):
    gate = FileSeriesGate(tmp_path / "gate", timeout=0.03, poll_interval=0.005)
    with pytest.raises(DeadlineError, match="waiting for sub-game 1"):
        gate.wait(2)


def test_first_sub_game_never_waits(tmp_path):
    gate = FileSeriesGate(tmp_path / "gate", timeout=0.01)
    gate.wait(1)


def test_two_fixed_role_processes_admit_windows_in_global_order(tmp_path):
    gate = FileSeriesGate(tmp_path / "gate", timeout=1.0, poll_interval=0.005)
    admitted = []
    lock = threading.Lock()

    def play(numbers):
        for number in numbers:
            gate.wait(number)
            with lock:
                admitted.append(number)
            gate.complete(number)

    thief = threading.Thread(target=play, args=([1, 3, 5],), daemon=True)
    police = threading.Thread(target=play, args=([2, 4, 6],), daemon=True)
    police.start()
    thief.start()
    thief.join(timeout=2.0)
    police.join(timeout=2.0)

    assert admitted == [1, 2, 3, 4, 5, 6]
