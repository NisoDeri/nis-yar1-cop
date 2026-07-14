"""Shared services — configuration loading/validation and the API Gatekeeper.

Every parameter Appendix F defines enters the program through this package
(private game.toml, shared/agreed game.json, rate_limits.json); nothing
downstream hardcodes a game value (brief §10, zero-hardcoding gate).
"""
