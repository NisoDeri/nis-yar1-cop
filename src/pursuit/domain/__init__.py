"""Pure domain layer — board physics, state, rules, scoring (zero I/O, zero network).

Everything here is deterministic and side-effect free: geometry and game law only.
Randomness, transport, LLMs, and files all live in outer layers (architecture.md §1).
"""
