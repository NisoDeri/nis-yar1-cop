"""Static ``_schema``/``_remark`` text and filename helpers for the four game JSON
artifacts (book Appendix F). Kept separate from :mod:`pursuit.report.artifacts` so the
builder module stays well under the 150-line ceiling; both are pure (no I/O).

The self-documenting ``_schema`` strings are copied from the reference templates so
emitted files stay as explanatory as the reference examples. Per App. F table 20 the
match-level files (declaration, result) are named ``<kind>_<game_id>.json`` while the
per-sub-game files (config, log) carry a zero-padded ``_g<NN>`` suffix.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = "1.1"
DEFAULT_TIMEZONE = "Asia/Jerusalem"

SCHEMA_DECLARATION = (
    "Static declaration for the WHOLE game (the full series of sub-games) between two "
    "teams. Single home for every field that does NOT change while the sub-games play: "
    "team identity, members, cop/thief repository URLs, hardware spec, LLM model, the "
    "public key, and the counted-games ledger. Roles switch across sub-games, so no role "
    "and no sub_game_number appear here. Both teams sign it before play (book ch5 Step-0)."
)
SCHEMA_CONFIG = (
    "Agreed game configuration for the series. Values come from the master parameter "
    "table (Appendix F). Both teams must hold BYTE-IDENTICAL values and lock them "
    "cryptographically (config_sha256) — the pre-game signature exchange refuses to play "
    "on any mismatch."
)
SCHEMA_LOG = (
    "Per-sub-game match log consumed by the Replay Viewer for cryptographic audit. Each "
    "step is committed as SHA-256(State || Move || Intent || Nonce) and revealed only at "
    "the final audit (book ch5 commit-reveal, ch7 replay). Static team metadata lives in "
    "the declaration; join by game_uid."
)
SCHEMA_RESULT = (
    "Summary and final result for the WHOLE game (all sub-games) between two teams. It "
    "condenses the per-sub-game logs into a per-group score for every sub-game plus the "
    "aggregate outcome the lecturer needs to build the league standings. Static team "
    "metadata (identity, members, repos, MCP, hardware, model) is NOT repeated here — it "
    "lives in 1-pre-game-declaration.json and is referenced via game_id / group_id. Both "
    "teams must agree on this result and each sends its own copy to the lecturer (book ch9)."
)
LINKS_REMARK = (
    "These are logical roles, NOT fixed filenames. Each actual file name MUST be derived "
    "from the game_id so that files from different games are never mixed. Match-level files "
    "(declaration, result) are named <role>_<game_id>.json; per-sub-game files (config, "
    "log) are named <role>_<game_id>_g<NN>.json where <NN> is the sub_game_number. The "
    "names below are derived from this report's own game_id."
)


def declaration_filename(game_id: str) -> str:
    return f"declaration_{game_id}.json"


def config_filename(game_id: str, sub_game_number: int) -> str:
    return f"config_{game_id}_g{sub_game_number:02d}.json"


def log_filename(game_id: str, sub_game_number: int) -> str:
    return f"log_{game_id}_g{sub_game_number:02d}.json"


def result_filename(game_id: str) -> str:
    return f"result_{game_id}.json"


def links(
    game_id: str,
    github: Mapping[str, Mapping[str, str]] | None = None,
    *,
    include_remark: bool = True,
) -> dict[str, Any]:
    """Shared links block: logical role -> filename. Config and log keep the literal
    ``g<NN>`` placeholder because ``<NN>`` (sub_game_number) varies per sub-game file."""
    block: dict[str, Any] = {
        "_remark": LINKS_REMARK,
        "declaration": declaration_filename(game_id),
        "config": f"config_{game_id}_g<NN>.json",
        "log": f"log_{game_id}_g<NN>.json",
        "result": result_filename(game_id),
    }
    if not include_remark:
        block.pop("_remark", None)
    if github:  # sorted group order — both teams emit the identical github block
        block["github"] = {gid: dict(github[gid]) for gid in sorted(github)}
    return block


_PASSTHROUGH_RESULTS = frozenset({"capture", "survival", "tie"})


def hardware_spec(sysinfo: Mapping[str, Any]) -> dict[str, Any]:
    """The 6 book hardware fields, tolerating either ``gpu_model`` or ``gpu_type``."""
    return {
        "cpu_type": sysinfo.get("cpu_type"),
        "cpu_freq_mhz": sysinfo.get("cpu_freq_mhz"),
        "cpu_cores": sysinfo.get("cpu_cores"),
        "ram_gb": sysinfo.get("ram_gb"),
        "gpu_model": sysinfo.get("gpu_model", sysinfo.get("gpu_type")),
        "vram_gb": sysinfo.get("vram_gb"),
    }


def winner_group(sub: Mapping[str, Any]) -> str | None:
    """The group_id that held the winning role this sub-game (None on tie/technical)."""
    winner_role = sub.get("winner_role")
    if winner_role is None:
        return None
    for gid, role in sub.get("roles", {}).items():
        if role == winner_role:
            return gid
    return None


def result_string(sub: Mapping[str, Any]) -> str:
    """Normalize an outcome to one of capture/survival/tie/technical_loss (A6/A9a)."""
    result = sub.get("result")
    return result if result in _PASSTHROUGH_RESULTS else "technical_loss"


def sub_result_row(sub: Mapping[str, Any], game_id: str,
                   group_ids: Sequence[str]) -> dict[str, Any]:
    """One condensed per-sub-game result row for the final result artifact."""
    audit = sub.get("audit", {})
    result = result_string(sub)
    return {
        "sub_game_number": sub.get("sub_game_number"),
        "roles": {gid: sub.get("roles", {})[gid] for gid in group_ids
                  if gid in sub.get("roles", {})},
        **({"started_at": sub.get("started_at")} if sub.get("started_at") else {}),
        **({"ended_at": sub.get("ended_at")} if sub.get("ended_at") else {}),
        "result": result,
        "winner_group": winner_group(sub),
        "tie": result == "tie",
        "github_commit": {gid: sub.get("github_commit", {})[gid] for gid in group_ids
                          if gid in sub.get("github_commit", {})},
        "tokens": {gid: (sub.get("tokens") or {}).get(gid, 0) for gid in group_ids},
        "score": {gid: sub.get("score", {})[gid] for gid in group_ids
                  if gid in sub.get("score", {})},
        "log_files": {gid: log_filename(game_id, sub.get("sub_game_number", 0))
                      for gid in group_ids},
        "audit": {"log_verified": bool(audit.get("passed", False)),
                  "tampered": bool(audit.get("forgery", False))},
    }
