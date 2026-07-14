"""Report stage: pure builders for the four standardized game JSON artifacts
(declaration, config, log, result) emitted per counted game (book Appendix F)."""

from __future__ import annotations

from pursuit.report.artifacts import (
    build_config_artifact,
    build_declaration,
    build_log_artifact,
    build_result_artifact,
    write_artifacts,
)

__all__ = [
    "build_config_artifact",
    "build_declaration",
    "build_log_artifact",
    "build_result_artifact",
    "write_artifacts",
]
