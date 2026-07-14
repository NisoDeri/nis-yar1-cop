"""SDK / Orchestrator layer — the single entry point every interface uses (rule 3).

``run_peer`` plays a real (or fake-opponent) series; ``run_lab`` runs the D7
self-play lab. Nothing above this layer may import game logic from anywhere else.
"""

from pursuit.sdk.lab_gate import run_lab, run_lab_versus
from pursuit.sdk.sdk import run_peer

__all__ = ["run_lab", "run_lab_versus", "run_peer"]
