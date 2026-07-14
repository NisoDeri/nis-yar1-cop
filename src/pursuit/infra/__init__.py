"""Infrastructure — MCP wire endpoints (server + client transport), no game logic.

The server enqueues blindly (INTEROP §1 "zero server-side validation"); the
transport retries-until-up toward the opponent. ALL enforcement (physics,
crypto, schema) lives in the consuming peer runtime, never here.
"""
