"""sysinfo behavior — stable 7-key spec shape (injected GPU probe) + real git commit.

The GPU probe is injected in every collect() call here, so no subprocess is spawned for
the spec. get_git_commit intentionally shells out to git (the one sanctioned process:
the task is literally "read this repo's HEAD"); the negative case uses tmp_path.
"""

from __future__ import annotations

import logging
import string
from pathlib import Path

from pursuit.shared.sysinfo import GIT_COMMIT_UNKNOWN, collect, get_git_commit

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_KEYS = ("os", "cpu_type", "cpu_freq_mhz", "cpu_cores", "ram_gb", "gpu_model", "vram_gb")


def fake_gpu() -> tuple[str, float]:
    return "Fake GPU 12GB", 12.0


def test_collect_shape_is_exactly_the_seven_declaration_keys() -> None:
    spec = collect(gpu_probe=fake_gpu)
    assert tuple(spec) == EXPECTED_KEYS  # deterministic shape AND order


def test_collect_field_types_and_best_effort_bounds() -> None:
    spec = collect(gpu_probe=fake_gpu)
    assert isinstance(spec["os"], str) and spec["os"]
    assert isinstance(spec["cpu_type"], str) and spec["cpu_type"]
    assert isinstance(spec["cpu_freq_mhz"], int) and spec["cpu_freq_mhz"] >= 0
    assert isinstance(spec["cpu_cores"], int) and spec["cpu_cores"] > 0
    assert isinstance(spec["ram_gb"], float) and spec["ram_gb"] >= 0.0
    assert spec["gpu_model"] == "Fake GPU 12GB"  # injected probe honored
    assert spec["vram_gb"] == 12.0


def test_collect_is_deterministic_across_calls() -> None:
    assert collect(gpu_probe=fake_gpu) == collect(gpu_probe=fake_gpu)


def test_collect_with_failed_probe_reports_unknown_gpu() -> None:
    spec = collect(gpu_probe=lambda: ("unknown", 0.0))  # what the default fallback yields
    assert spec["gpu_model"] == "unknown"
    assert spec["vram_gb"] == 0.0
    assert tuple(spec) == EXPECTED_KEYS  # shape survives a dead probe


def test_get_git_commit_returns_short_hex_hash_in_this_repo() -> None:
    commit = get_git_commit(REPO_ROOT)
    assert commit != GIT_COMMIT_UNKNOWN  # OUR artifacts carry the real hash (D9 fix)
    assert 7 <= len(commit) <= 40
    assert set(commit) <= set(string.hexdigits.lower())


def test_get_git_commit_falls_back_to_unknown_outside_a_repo(
    tmp_path: Path, caplog: object
) -> None:
    with caplog.at_level(logging.WARNING, logger="pursuit.shared.sysinfo"):
        assert get_git_commit(tmp_path) == GIT_COMMIT_UNKNOWN
    assert any("github_commit" in rec.message for rec in caplog.records)
