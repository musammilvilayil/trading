import pytest

from app.gemini import (
    GeminiMarketBrief,
    GeminiNotConfiguredError,
    generate_market_brief,
    get_gemini_status,
)


def test_gemini_status_never_exposes_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    status = get_gemini_status()
    assert status["configured"] is True
    assert status["role"] == "advisory_only"
    assert status["live_trading_enabled"] is False
    assert "test-secret-key" not in str(status)


def test_gemini_is_optional_when_key_is_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    status = get_gemini_status()
    assert status["configured"] is False
    with pytest.raises(GeminiNotConfiguredError):
        generate_market_brief("RELIANCE", "stocks", {"signal": "hold"})


def test_market_brief_schema_restricts_ai_output():
    brief = GeminiMarketBrief.model_validate({
        "overall_bias": "neutral",
        "confidence": "low",
        "news_sentiment": "not_assessed",
        "signal_alignment": "unclear",
        "summary": "Signals are mixed.",
        "technical_interpretation": "No clear trend is present in the supplied analysis.",
        "key_factors": ["Momentum is weak."],
        "risks": ["Historical data may be delayed."],
        "bull_case": "A stronger trend could develop.",
        "bear_case": "Momentum could weaken further.",
        "invalidation_conditions": ["The supplied trend structure changes."],
    })
    assert brief.news_sentiment == "not_assessed"
    assert brief.overall_bias == "neutral"
