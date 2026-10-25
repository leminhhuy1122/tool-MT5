# -*- coding: utf-8 -*-
"""
Unit tests cho Economic News Calendar Engine.
"""

from datetime import datetime, timedelta, timezone
import json
from unittest.mock import MagicMock, patch
import pytest

from app.news.calendar import NewsManager
from app.news.models import EconomicEvent, GoldImpactBias, NewsImpact


def test_economic_event_properties():
    """Kiểm tra các thuộc tính của EconomicEvent."""
    event = EconomicEvent(
        id="USD_123_CPI",
        title="CPI m/m",
        country="USD",
        impact=NewsImpact.HIGH,
        time_utc=datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc),
        forecast="0.3%",
        previous="0.2%",
        bias_on_gold=GoldImpactBias.HIGH_VOLATILITY,
    )

    assert event.is_high_impact is True
    assert event.is_usd is True
    assert event.to_dict()["country"] == "USD"
    assert event.to_dict()["impact"] == "HIGH"


def test_news_manager_parse_event():
    """Kiểm tra hàm parse_event từ cấu trúc dữ liệu ForexFactory."""
    manager = NewsManager()

    raw_item = {
        "title": "Federal Funds Rate",
        "country": "USD",
        "date": "2026-10-28T14:00:00-04:00",
        "impact": "High",
        "forecast": "4.00%",
        "previous": "4.00%",
    }

    event = manager._parse_event(raw_item)
    assert event is not None
    assert event.title == "Federal Funds Rate"
    assert event.country == "USD"
    assert event.impact == NewsImpact.HIGH
    assert event.bias_on_gold == GoldImpactBias.HIGH_VOLATILITY
    assert "FOMC" in event.note or "Lãi suất Fed" in event.note


def test_news_manager_is_in_blackout_window():
    """Kiểm tra logic vùng cấm giao dịch khi có tin đỏ USD."""
    manager = NewsManager()

    event_time = datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)
    mock_event = EconomicEvent(
        id="USD_TEST",
        title="Non-Farm Employment Change",
        country="USD",
        impact=NewsImpact.HIGH,
        time_utc=event_time,
    )

    manager._cached_events = [mock_event]
    manager._last_fetched_at = datetime.now(timezone.utc)

    # 1. 20 phút trước giờ tin -> Phải là Blackout (True)
    check_time_1 = event_time - timedelta(minutes=20)
    in_blackout, ev = manager.is_in_blackout_window(current_time=check_time_1, buffer_before_min=30, buffer_after_min=20)
    assert in_blackout is True
    assert ev.title == "Non-Farm Employment Change"

    # 2. 10 phút sau giờ tin -> Vẫn là Blackout (True)
    check_time_2 = event_time + timedelta(minutes=10)
    in_blackout, ev = manager.is_in_blackout_window(current_time=check_time_2, buffer_before_min=30, buffer_after_min=20)
    assert in_blackout is True

    # 3. 40 phút trước giờ tin -> An toàn (False)
    check_time_3 = event_time - timedelta(minutes=40)
    in_blackout, ev = manager.is_in_blackout_window(current_time=check_time_3, buffer_before_min=30, buffer_after_min=20)
    assert in_blackout is False
    assert ev is None


@patch("urllib.request.urlopen")
def test_news_manager_fetch_calendar_mock(mock_urlopen):
    """Kiểm tra fetch_calendar với dữ liệu giả lập."""
    mock_data = [
        {
            "title": "CPI m/m",
            "country": "USD",
            "date": "2026-10-29T08:30:00-04:00",
            "impact": "High",
            "forecast": "0.3%",
            "previous": "0.2%",
        },
        {
            "title": "German Flash Manufacturing PMI",
            "country": "EUR",
            "date": "2026-10-29T03:30:00-04:00",
            "impact": "Medium",
            "forecast": "42.0",
            "previous": "40.6",
        },
    ]

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    manager = NewsManager(cache_ttl_seconds=300)
    events = manager.fetch_calendar(force=True)

    assert len(events) == 2
    assert events[0].country in ("USD", "EUR")
    assert any(e.title == "CPI m/m" for e in events)
