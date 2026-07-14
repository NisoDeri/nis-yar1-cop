"""Peer runtime — one peer's lifecycle for a single sub-game (negotiate → turns → audit).

Home of the guarded turn state machine (book rules 4-5), the signed-terms
handshake, turn handling/sending with sealed commit-reveal records, the
watchdog (rule 7), and the end-game mutual audit — which runs on EVERY
ending, timeout included (decision D4; fixes reference gap #5).
"""
