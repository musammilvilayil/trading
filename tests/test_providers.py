from trading_agent.providers import resolve_instrument


def test_instrument_mapping_supports_multiple_markets():
    assert resolve_instrument("RELIANCE", "stocks").quote_currency == "INR"
    assert resolve_instrument("BTC-USD", "crypto").quote_currency == "USD"
    assert resolve_instrument("EURUSD", "forex").quote_currency == "USD"
    assert resolve_instrument("GC=F", "commodities").quote_currency == "USD"


def test_forex_symbol_requires_six_letter_pair():
    import pytest
    with pytest.raises(ValueError):
        resolve_instrument("EUR", "forex")
