import struct

import pytest

from app.brokers.dhan_feed import (
    DhanFeedError,
    DhanMarketFeed,
    DhanFeedService,
    parse_dhan_packet,
)


def make_quote_packet():
    packet = bytearray(50)
    packet[0] = 4
    struct.pack_into("<H", packet, 1, 50)
    packet[3] = 1
    struct.pack_into("<I", packet, 4, 1333)
    struct.pack_into("<f", packet, 8, 100.5)
    struct.pack_into("<h", packet, 12, 2)
    struct.pack_into("<i", packet, 14, 1700000000)
    struct.pack_into("<f", packet, 18, 100.2)
    struct.pack_into("<i", packet, 22, 10000)
    struct.pack_into("<i", packet, 26, 400)
    struct.pack_into("<i", packet, 30, 600)
    struct.pack_into("<f", packet, 34, 99.0)
    struct.pack_into("<f", packet, 38, 98.0)
    struct.pack_into("<f", packet, 42, 101.0)
    struct.pack_into("<f", packet, 46, 97.0)
    return bytes(packet)


def test_parse_dhan_quote_packet():
    result = parse_dhan_packet(make_quote_packet())

    assert result["response_code"] == 4
    assert result["exchange_segment"] == "NSE_EQ"
    assert result["security_id"] == "1333"
    assert result["last_price"] == pytest.approx(100.5)
    assert result["volume"] == 10000
    assert result["total_buy_quantity"] == 600
    assert result["day_high"] == pytest.approx(101.0)
    assert result["exchange_time"].endswith("+00:00")


def test_reject_truncated_dhan_packet():
    with pytest.raises(DhanFeedError):
        parse_dhan_packet(b"\x04\x00\x00")


def test_dhan_subscription_batches_at_100_instruments():
    instruments = [
        {"exchange_segment": "NSE_EQ", "security_id": str(i)}
        for i in range(205)
    ]
    messages = list(DhanMarketFeed._subscription_messages(instruments, "quote"))

    assert [item["InstrumentCount"] for item in messages] == [100, 100, 5]
    assert all(item["RequestCode"] == 17 for item in messages)


def test_dhan_subscription_rejects_unknown_mode():
    with pytest.raises(DhanFeedError):
        list(DhanMarketFeed._subscription_messages(
            [{"exchange_segment": "NSE_EQ", "security_id": "1333"}], "bad"
        ))


def test_dhan_feed_status_never_exposes_access_token(monkeypatch):
    monkeypatch.setenv("DHAN_CLIENT_ID", "test-client")
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "super-secret-token")
    status = DhanFeedService().status()

    assert status["configured"] is True
    assert status["live_order_execution_enabled"] is False
    assert "super-secret-token" not in str(status)
