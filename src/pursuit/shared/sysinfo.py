"""Best-effort machine spec + real git commit — step-0 declaration inputs (D9, rules 24/53).

``collect()`` is psutil-free (stdlib :mod:`platform`/:mod:`os`/:mod:`ctypes` only) and
DETERMINISTIC IN SHAPE: the same seven keys with the same types every call, so the sealed
step-0 payload hashes stably. Value semantics are best-effort — ``cpu_freq_mhz``/``ram_gb``
fall back to 0 and the GPU fields to ``"unknown"``/0.0 where the platform gives no cheap
answer; honesty about a modest machine is exactly what the computational-fairness bonus
rewards (D9). The GPU probe (``nvidia-smi``, the one subprocess) is injectable so unit
tests never spawn it.

``get_git_commit`` fixes the reference's bug of emitting the literal ``"unknown"`` as
``github_commit`` (INTEROP §5.5 item 1): OUR artifacts carry the real short hash; the
``"unknown"`` fallback survives only for a non-repo runtime dir, with a warning logged.
"""

from __future__ import annotations

import contextlib
import logging
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

GIT_COMMIT_UNKNOWN = "unknown"
_PROBE_TIMEOUT_SECONDS = 10  # local-process ceiling, not a game parameter

#: () -> (gpu_model, vram_gb) — inject a fake in unit tests (no-subprocess gate).
GpuProbe = Callable[[], tuple[str, float]]


def _cpu_freq_mhz() -> int:
    """Nominal CPU MHz: Windows registry, else /proc/cpuinfo, else 0 (best-effort)."""
    if sys.platform == "win32":
        import winreg  # noqa: PLC0415 — Windows-only stdlib

        key_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with (
            contextlib.suppress(OSError),
            winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key,
        ):
            return int(winreg.QueryValueEx(key, "~MHz")[0])
        return 0
    with contextlib.suppress(OSError, ValueError, IndexError):
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("cpu mhz"):
                return int(float(line.split(":")[1]))
    return 0


def _ram_gb() -> float:
    """Physical RAM in GiB (1 dp): Win32 kernel call, else POSIX sysconf, else 0.0."""
    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415 — Windows-only use

        kilobytes = ctypes.c_uint64(0)
        with contextlib.suppress(OSError, AttributeError):
            if ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(
                ctypes.byref(kilobytes)
            ):
                return round(kilobytes.value / (1024 * 1024), 1)
        return 0.0
    with contextlib.suppress(OSError, ValueError, AttributeError):
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    return 0.0


def _gpu_via_nvidia_smi() -> tuple[str, float]:
    """Default GPU probe: first nvidia-smi device, VRAM MiB -> GiB (1 dp)."""
    query = ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]
    try:
        proc = subprocess.run(
            query, capture_output=True, text=True, timeout=_PROBE_TIMEOUT_SECONDS, check=True
        )
        name, _, vram_mib = proc.stdout.strip().splitlines()[0].partition(",")
        return name.strip(), round(float(vram_mib) / 1024, 1)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        logger.warning("nvidia-smi probe failed; gpu fields fall back to unknown/0.0")
        return "unknown", 0.0


def collect(gpu_probe: GpuProbe | None = None) -> dict[str, object]:
    """Machine spec for the sealed step-0 declaration — fixed 7-key shape.

    Keys mirror the declaration's ``hardware_spec`` naming (``gpu_model``, not the
    identity block's ``gpu_type`` — INTEROP §2.1 note) plus ``os``.
    """
    gpu_model, vram_gb = (_gpu_via_nvidia_smi if gpu_probe is None else gpu_probe)()
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu_type": platform.processor() or platform.machine() or "unknown",
        "cpu_freq_mhz": _cpu_freq_mhz(),
        "cpu_cores": os.cpu_count() or 0,
        "ram_gb": _ram_gb(),
        "gpu_model": gpu_model,
        "vram_gb": vram_gb,
    }


def get_git_commit(repo_root: str | Path) -> str:
    """Short HEAD hash of ``repo_root`` — the REAL ``github_commit`` (rules 24/53).

    Falls back to ``"unknown"`` (with a warning) only when git/HEAD is unavailable;
    the reference peer emits that literal unconditionally — a bug we fix (D9).
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            check=True,
        )
        commit = proc.stdout.strip()
        if commit:
            return commit
    except (OSError, subprocess.SubprocessError):
        pass
    logger.warning(
        "git rev-parse failed under %s; github_commit falls back to %r — league artifacts "
        "must carry the real hash, run from the git checkout",
        repo_root,
        GIT_COMMIT_UNKNOWN,
    )
    return GIT_COMMIT_UNKNOWN
