from __future__ import annotations

from pursuit.constants import GameResult, Role
from pursuit.domain.protocol_audit import AuditPayload, AuditRecord
from pursuit.peer.audit import exchange_audits
from pursuit.peer.deadlines import DeadlineTracker
from pursuit.peer.inboxes import Inbox
from pursuit.peer.sealing import SealedLog


class AuditTransport:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.sent = []

    def submit_audit(self, payload):
        self.sent.append(payload)
        return {"ok": True} if self.accepted else None


def audit_wire(role: Role, sub_game: int):
    log = SealedLog({"dialect": "reference"})
    log.seal_step({"step": 0, "type": "system_spec", "sub_game_number": sub_game})
    return AuditPayload(
        sender=role.value,
        result_claim=GameResult.CAPTURE.value,
        records=[AuditRecord(**record) for record in log.audit_reveal()],
    ).to_wire()


def local_log(sub_game: int):
    log = SealedLog({"dialect": "reference"})
    log.seal_step({"step": 0, "type": "system_spec", "sub_game_number": sub_game})
    return log


def test_exchange_ignores_stale_audit_and_accepts_matching_window():
    inbox = Inbox("audits")
    inbox.put(audit_wire(Role.THIEF, 1))
    inbox.put(audit_wire(Role.THIEF, 2))
    transport = AuditTransport()

    result = exchange_audits(
        Role.POLICE, GameResult.CAPTURE, local_log(2), transport, inbox,
        DeadlineTracker(), 0.5, None,
    )

    assert result["passed"] is True
    assert result["opponent_received"] is True
    assert result["outbound_accepted"] is True
    assert result["ignored_payloads"] == 1
    assert len(transport.sent) == 1


def test_exchange_reports_missing_outbound_and_inbound_without_forgery():
    result = exchange_audits(
        Role.POLICE, GameResult.TECHNICAL_LOSS, local_log(2), AuditTransport(False),
        Inbox("audits"), DeadlineTracker(), 0.01, None,
    )

    assert result["passed"] is False
    assert result["forgery"] is False
    assert result["opponent_received"] is False
    assert result["outbound_accepted"] is False
