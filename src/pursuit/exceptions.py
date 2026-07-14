"""Exception hierarchy — every failure mode has a name (book rules 4-7 discipline)."""


class PursuitError(Exception):
    """Base for every domain error."""


class ConfigError(PursuitError):
    """Missing/invalid/unagreed configuration term (fail-fast at startup)."""


class IllegalMoveError(PursuitError):
    """A move outside the negotiated move_set or into a blocked cell."""


class IllegalTransitionError(PursuitError):
    """State-machine transition not allowed from the current state (rule 5)."""


class CryptoError(PursuitError):
    """Commit/reveal/signature mismatch — provable tampering or dialect drift."""


class NegotiationError(PursuitError):
    """Pre-game agreement failed (config hash mismatch, refused terms)."""


class DeadlineError(PursuitError):
    """A tracked wait exceeded its negotiated budget (rule 6)."""


class TransportError(PursuitError):
    """MCP wire failure after retries (rule 6/7 handling, never a hang)."""
