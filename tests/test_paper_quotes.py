from datetime import datetime, timezone

from market_events.config import Settings, LiveDataSettings
from market_events.paper_quotes import latest_paper_quotes
from market_events import paper_quotes


def test_quotes_are_bounded_timestamped_and_missing_data_is_not_invented(monkeypatch):
    monkeypatch.setattr(
        paper_quotes,
        "_instruments",
        lambda root, day: [
            {"instrument_id": "LIVE:NSE:TEST", "provider_instrument_key": "NSE_EQ|TEST"},
            {"instrument_id": "LIVE:NSE:MISSING", "provider_instrument_key": "NSE_EQ|MISSING"},
        ],
    )
    last_trade = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

    def get(reader, url, **kwargs):
        assert kwargs["params"]["instrument_key"] == "NSE_EQ|TEST,NSE_EQ|MISSING"
        return {
            "status": "success",
            "data": {
                "NSE_EQ:TEST": {
                    "instrument_token": "NSE_EQ|TEST",
                    "last_price": 123.45,
                    "last_trade_time": str(last_trade),
                },
                "NSE_EQ:MISSING": {
                    "instrument_token": "NSE_EQ|MISSING",
                    "last_price": float("nan"),
                },
            },
        }

    monkeypatch.setattr(paper_quotes._Reader, "get", get)
    result = latest_paper_quotes(Settings(live_data=LiveDataSettings(access_token="fixture")))
    assert result["quotes"] == [
        {
            "instrument_id": "LIVE:NSE:TEST",
            "price": 123.45,
            "last_trade_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    assert result["missing"] == ["LIVE:NSE:MISSING"]
