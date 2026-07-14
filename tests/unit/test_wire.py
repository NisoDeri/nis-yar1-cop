"""Unit tests for the MCP wire layer — server tools + opponent transport.

No sockets, no processes, no network: tool handlers are called as plain
functions (pre-.run), the port probe gets a fake socket factory, and the
transport gets a stub caller + fake clock.
"""

import asyncio
import inspect
import json

import pytest

from pursuit.exceptions import ConfigError, DeadlineError, TransportError
from pursuit.infra.mcp_server import (
    ACK,
    TOOL_NAMES,
    PeerMcpServer,
    ensure_port_free,
    make_handlers,
)
from pursuit.infra.transport import (
    REQUIRED_TIMEOUT_KEYS,
    TOOL_SPEC,
    FakeTransport,
    OpponentTransport,
    rpc_result,
    tool_ack,
)
from pursuit.peer.inboxes import PeerInboxes

TIMEOUTS = {"retry_interval": 1.0, "connect_timeout": 60.0,
            "audit_timeout": 10.0, "control_timeout": 2.0}


# ---------------------------------------------------------------- mcp_server


class TestHandlers:
    def setup_method(self):
        self.inboxes = PeerInboxes()
        self.handlers = make_handlers(self.inboxes)

    def test_exactly_the_four_frozen_tools(self):
        assert tuple(self.handlers) == TOOL_NAMES == (
            "negotiate", "receive_turn", "submit_audit", "receive_control")

    @pytest.mark.parametrize(("tool", "channel"), [
        ("negotiate", "negotiation"), ("receive_turn", "turns"),
        ("submit_audit", "audits"), ("receive_control", "controls")])
    def test_each_tool_enqueues_and_acks(self, tool, channel):
        body = {"marker": tool}
        assert self.handlers[tool](body) == {"ok": True}
        assert self.inboxes.channel(channel).get(timeout=0.1) is body
        for other in PeerInboxes.CHANNELS:
            assert len(self.inboxes.channel(other)) == 0  # nothing leaked elsewhere

    def test_submit_audit_param_is_payload_others_message(self):
        """INTEROP §2.3 — the one asymmetry in the API, frozen."""
        for tool in TOOL_NAMES:
            params = list(inspect.signature(self.handlers[tool]).parameters)
            assert params == ["payload" if tool == "submit_audit" else "message"], tool

    @pytest.mark.parametrize("tool", TOOL_NAMES)
    def test_non_object_argument_rejected(self, tool):
        with pytest.raises(TypeError, match=f"{tool}.*JSON object.*str"):
            self.handlers[tool]("not-a-dict")
        for channel in PeerInboxes.CHANNELS:
            assert len(self.inboxes.channel(channel)) == 0

    def test_ack_is_a_fresh_dict_each_call(self):
        first = self.handlers["negotiate"]({"a": 1})
        first["tampered"] = True
        assert self.handlers["negotiate"]({"b": 2}) == dict(ACK)

    def test_duplicate_deliveries_both_enqueued(self):
        message = {"step": 3, "sender": "thief"}
        self.handlers["receive_turn"](message)
        self.handlers["receive_turn"](message)
        assert len(self.inboxes.turns) == 2  # dedup is the runtime's job


class _FakeSocket:
    def __init__(self, in_use):
        self.in_use = in_use
        self.closed = False

    def bind(self, addr):
        if self.in_use:
            raise OSError(f"address in use: {addr}")

    def close(self):
        self.closed = True


class TestPortPreflight:
    def test_free_port_passes_and_probe_closed(self):
        probe = _FakeSocket(in_use=False)
        ensure_port_free("127.0.0.1", 8801, probe_factory=lambda: probe)
        assert probe.closed

    def test_bound_port_raises_transport_error(self):
        probe = _FakeSocket(in_use=True)
        with pytest.raises(TransportError, match="port already in use.*8802"):
            ensure_port_free("127.0.0.1", 8802, probe_factory=lambda: probe)
        assert probe.closed


class TestPeerMcpServer:
    def test_registers_the_four_tools_under_frozen_names(self):
        server = PeerMcpServer("police", "127.0.0.1", 8802, PeerInboxes())
        registered = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
        assert registered == set(TOOL_NAMES)
        assert server.mcp.name == "police-thief-police"

    def test_registered_handlers_still_route_to_inboxes(self):
        inboxes = PeerInboxes()
        server = PeerMcpServer("thief", "127.0.0.1", 8801, inboxes)
        server.handlers["submit_audit"]({"sender": "police", "records": []})
        assert inboxes.audits.get(timeout=0.1)["sender"] == "police"


# ----------------------------------------------------------------- transport


class _FakeResponse:
    def __init__(self, body, content_type="application/json", status_code=200):
        self.headers = {"content-type": content_type}
        self.text = body
        self.status_code = status_code


class TestRpcParsing:
    def test_plain_json_result(self):
        response = _FakeResponse(json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"x": 1}}))
        assert rpc_result(response, 2) == {"x": 1}

    def test_sse_body_result(self):
        body = ("event: message\n"
                'data: {"jsonrpc":"2.0","id":2,"result":{"structuredContent":{"ok":true}}}\n\n')
        response = _FakeResponse(body, content_type="text/event-stream; charset=utf-8")
        assert rpc_result(response, 2)["structuredContent"] == {"ok": True}

    def test_error_reply_raises(self):
        response = _FakeResponse(json.dumps(
            {"jsonrpc": "2.0", "id": 2, "error": {"code": -32602, "message": "bad params"}}))
        with pytest.raises(TransportError, match="bad params"):
            rpc_result(response, 2)

    def test_http_error_status_raises(self):
        response = _FakeResponse("Bad Request", status_code=400)
        with pytest.raises(TransportError, match="HTTP 400"):
            rpc_result(response, 1)

    def test_missing_result_raises(self):
        response = _FakeResponse(json.dumps({"jsonrpc": "2.0", "id": 7, "result": {}}))
        with pytest.raises(TransportError, match="no JSON-RPC result"):
            rpc_result(response, 2)

    def test_tool_ack_prefers_structured_content(self):
        assert tool_ack({"structuredContent": {"ok": True}, "content": []}) == {"ok": True}

    def test_tool_ack_falls_back_to_text_content(self):
        assert tool_ack({"content": [{"type": "text", "text": '{"ok": true}'}]}) == {"ok": True}

    def test_tool_ack_remote_error_raises(self):
        with pytest.raises(TransportError, match="failed remotely"):
            tool_ack({"isError": True, "content": []})


class _Clock:
    """Deterministic monotonic clock; sleep() advances it."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class _StubCaller:
    """httpx-like callable: fails `failures` times, then returns an ack."""

    def __init__(self, failures=0, exc=None):
        self.failures = failures
        self.exc = exc if exc is not None else TransportError("connect refused")
        self.calls = []

    def __call__(self, url, tool, arguments, timeout):
        self.calls.append((url, tool, arguments, timeout))
        if len(self.calls) <= self.failures:
            raise self.exc
        return {"ok": True}


def _transport(caller, clock, timeouts=TIMEOUTS):
    return OpponentTransport("http://opp:8802/mcp", timeouts,
                             caller=caller, sleep=clock.sleep, clock=clock.monotonic)


class TestOpponentTransport:
    def test_missing_timeout_keys_fail_fast(self):
        with pytest.raises(ConfigError, match="audit_timeout"):
            OpponentTransport("http://opp/mcp", {"retry_interval": 1.0}, caller=_StubCaller())
        assert set(REQUIRED_TIMEOUT_KEYS) == set(TIMEOUTS)

    def test_success_first_try_wraps_argument_key(self):
        caller, clock = _StubCaller(), _Clock()
        assert _transport(caller, clock).negotiate({"terms": {}}) == {"ok": True}
        url, tool, arguments, _ = caller.calls[0]
        assert (url, tool, arguments) == ("http://opp:8802/mcp", "negotiate",
                                          {"message": {"terms": {}}})

    def test_submit_audit_uses_payload_key(self):
        caller, clock = _StubCaller(), _Clock()
        _transport(caller, clock).submit_audit({"sender": "thief"})
        assert caller.calls[0][2] == {"payload": {"sender": "thief"}}
        assert TOOL_SPEC["submit_audit"][0] == "payload"

    def test_retries_until_up_then_delivers(self):
        caller, clock = _StubCaller(failures=3), _Clock()
        assert _transport(caller, clock).receive_turn({"step": 1}) == {"ok": True}
        assert len(caller.calls) == 4
        assert clock.sleeps == [1.0, 1.0, 1.0]

    def test_negotiate_hard_fails_after_deadline(self):
        caller, clock = _StubCaller(failures=10_000), _Clock()
        with pytest.raises(TransportError, match="unreachable.*negotiate"):
            _transport(caller, clock).negotiate({"terms": {}})
        assert clock.now <= TIMEOUTS["connect_timeout"]
        assert len(caller.calls) == int(TIMEOUTS["connect_timeout"])  # one try per second

    @pytest.mark.parametrize(("method", "budget"), [
        ("submit_audit", 10.0), ("receive_control", 2.0)])
    def test_best_effort_tools_suppress_to_none(self, method, budget):
        caller, clock = _StubCaller(failures=10_000), _Clock()
        assert getattr(_transport(caller, clock), method)({"kind": "status"}) is None
        assert clock.now <= budget  # gave up within its own per-tool deadline

    def test_wire_timeout_never_below_retry_interval(self):
        caller, clock = _StubCaller(failures=1), _Clock()
        _transport(caller, clock).receive_control({"kind": "enable"})
        assert all(call[3] >= TIMEOUTS["retry_interval"] for call in caller.calls)


class TestFakeTransport:
    def test_pair_delivers_both_ways_on_all_channels(self):
        inboxes_a, inboxes_b = PeerInboxes(), PeerInboxes()
        to_b, to_a = FakeTransport.pair(inboxes_a, inboxes_b)
        assert to_b.negotiate({"terms": 1}) == {"ok": True}
        to_b.receive_turn({"step": 1})
        to_b.submit_audit({"sender": "thief"})
        to_b.receive_control({"kind": "enable"})
        to_a.receive_turn({"step": 2})
        assert inboxes_b.negotiation.get(timeout=0.1) == {"terms": 1}
        assert inboxes_b.turns.get(timeout=0.1) == {"step": 1}
        assert inboxes_b.audits.get(timeout=0.1) == {"sender": "thief"}
        assert inboxes_b.controls.get(timeout=0.1) == {"kind": "enable"}
        assert inboxes_a.turns.get(timeout=0.1) == {"step": 2}
        with pytest.raises(DeadlineError):
            inboxes_a.negotiation.get(timeout=0.01)  # nothing crossed back

    def test_sent_log_records_traffic(self):
        transport = FakeTransport(PeerInboxes())
        transport.negotiate({"terms": {}})
        transport.receive_turn({"step": 1})
        assert [tool for tool, _ in transport.sent] == ["negotiate", "receive_turn"]
