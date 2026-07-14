"""Unit tests for pursuit.peer.inboxes — thread-safe channels with named deadlines."""

import threading

import pytest

from pursuit.exceptions import DeadlineError
from pursuit.peer.inboxes import Inbox, PeerInboxes


class TestInbox:
    def test_put_get_roundtrip(self):
        box = Inbox("turns")
        box.put({"step": 1})
        assert box.get(timeout=0.1) == {"step": 1}

    def test_fifo_order(self):
        box = Inbox("turns")
        for step in (1, 2, 3):
            box.put({"step": step})
        assert [box.get(timeout=0.1)["step"] for _ in range(3)] == [1, 2, 3]

    def test_get_timeout_raises_deadline_error(self):
        box = Inbox("negotiation")
        with pytest.raises(DeadlineError, match="negotiation.*0.01"):
            box.get(timeout=0.01)

    def test_deadline_error_is_not_queue_empty_leak(self):
        box = Inbox("audits")
        with pytest.raises(DeadlineError):
            box.get(timeout=0.01)

    def test_get_nowait_returns_none_when_empty(self):
        assert Inbox("controls").get_nowait() is None

    def test_get_nowait_pops_in_order(self):
        box = Inbox("controls")
        box.put("a")
        box.put("b")
        assert box.get_nowait() == "a"
        assert box.get_nowait() == "b"
        assert box.get_nowait() is None

    def test_len_tracks_queued_items(self):
        box = Inbox("turns")
        assert len(box) == 0
        box.put({})
        box.put({})
        assert len(box) == 2

    def test_drain_empties_and_returns_everything(self):
        box = Inbox("turns")
        for step in (1, 2):
            box.put({"step": step})
        assert box.drain() == [{"step": 1}, {"step": 2}]
        assert len(box) == 0
        assert box.drain() == []

    def test_cross_thread_delivery(self):
        """A producer thread unblocks a waiting consumer (server → runtime path)."""
        box = Inbox("turns")
        producer = threading.Thread(target=lambda: box.put({"step": 9}), daemon=True)
        producer.start()
        assert box.get(timeout=2.0) == {"step": 9}
        producer.join(timeout=2.0)

    def test_duplicate_deliveries_are_kept(self):
        """Wire retries can duplicate messages; the queue must NOT dedup (INTEROP §1)."""
        box = Inbox("negotiation")
        box.put({"nonce": "aa"})
        box.put({"nonce": "aa"})
        assert len(box) == 2


class TestPeerInboxes:
    def test_has_the_four_league_channels(self):
        inboxes = PeerInboxes()
        assert PeerInboxes.CHANNELS == ("negotiation", "turns", "audits", "controls")
        for name in PeerInboxes.CHANNELS:
            assert isinstance(getattr(inboxes, name), Inbox)
            assert inboxes.channel(name) is getattr(inboxes, name)
            assert inboxes.channel(name).name == name

    def test_channel_unknown_name_raises(self):
        with pytest.raises(ValueError, match="unknown inbox channel 'agreements'"):
            PeerInboxes().channel("agreements")

    def test_channels_are_independent(self):
        inboxes = PeerInboxes()
        inboxes.turns.put({"step": 1})
        assert inboxes.negotiation.get_nowait() is None
        assert inboxes.turns.get(timeout=0.1) == {"step": 1}

    def test_drain_all_empties_every_channel(self):
        inboxes = PeerInboxes()
        inboxes.negotiation.put({"terms": {}})
        inboxes.controls.put({"kind": "enable"})
        drained = inboxes.drain_all()
        assert drained == {
            "negotiation": [{"terms": {}}],
            "turns": [],
            "audits": [],
            "controls": [{"kind": "enable"}],
        }
        assert all(len(inboxes.channel(name)) == 0 for name in PeerInboxes.CHANNELS)
