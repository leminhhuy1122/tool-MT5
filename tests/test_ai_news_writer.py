# -*- coding: utf-8 -*-
"""
Tests for AINewsWriter (Economic Calendar Digest & Gold Market Article Generator).
"""

from datetime import datetime, timezone
import pytest

from app.news.ai_writer import AINewsWriter
from app.news.models import EconomicEvent, NewsImpact, GoldImpactBias
from config import OpenAIConfig


def test_generate_daily_calendar_local():
    """Kiểm tra tạo bài Lịch Kinh Tế hàng ngày chuẩn định dạng hình ảnh mẫu 1."""
    writer = AINewsWriter()

    # Tạo mock events giống hình 1
    events = [
        EconomicEvent(
            id="gbp_1",
            title="Retail Sales m/m",
            country="GBP",
            impact=NewsImpact.MEDIUM,
            time_utc=datetime(2026, 10, 23, 6, 0, tzinfo=timezone.utc),  # 13:00 VN
        ),
        EconomicEvent(
            id="eur_1",
            title="French Flash Manufacturing PMI",
            country="EUR",
            impact=NewsImpact.MEDIUM,
            time_utc=datetime(2026, 10, 23, 7, 15, tzinfo=timezone.utc),  # 14:15 VN
        ),
        EconomicEvent(
            id="eur_2",
            title="German Flash Manufacturing PMI",
            country="EUR",
            impact=NewsImpact.MEDIUM,
            time_utc=datetime(2026, 10, 23, 7, 30, tzinfo=timezone.utc),  # 14:30 VN
        ),
        EconomicEvent(
            id="usd_1",
            title="Flash Manufacturing PMI",
            country="USD",
            impact=NewsImpact.MEDIUM,
            time_utc=datetime(2026, 10, 23, 13, 45, tzinfo=timezone.utc),  # 20:45 VN
        ),
        EconomicEvent(
            id="usd_2",
            title="Revised UoM Consumer Sentiment",
            country="USD",
            impact=NewsImpact.MEDIUM,
            time_utc=datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc),  # 21:00 VN
        ),
    ]

    post_text = writer.generate_daily_calendar_post(
        events=events,
        target_date=datetime(2026, 10, 23).date(),
        use_ai=False,
    )

    assert "LỊCH KINH TẾ" in post_text
    assert "TÂM ĐIỂM HÔM NAY" in post_text
    assert "Doanh số bán lẻ" in post_text
    assert "PMI" in post_text
    assert "Tâm lý tiêu dùng" in post_text
    assert "Chúc ACE giao dịch thuận lợi!" in post_text
    assert "🇪🇺" in post_text
    assert "🇬🇧" in post_text
    assert "🇺🇸" in post_text


def test_generate_gold_market_article_local():
    """Kiểm tra tạo bài báo điểm tin giá vàng chuẩn định dạng hình ảnh mẫu 2."""
    writer = AINewsWriter()

    article = writer.generate_gold_market_article(
        current_price=3994.9,
        change_pct=-0.71,
        sjc_buy=139.0,
        sjc_sell=142.0,
        session_name="sáng",
        use_ai=False,
    )

    assert "Giá vàng sáng" in article
    assert "142 triệu đồng/lượng" in article
    assert "SJC" in article
    assert "PNJ" in article
    assert "3.994,9 USD/ounce" in article
    assert "0,71%" in article or "0.71%" in article
    assert "LỜI CẢNH BÁO" in article


def test_generate_realtime_flash_news_post_local():
    """Kiểm tra tạo bài viết TIN NÓNG THỜI GIAN THỰC (Flash News) sau khi tin ra 2-3 phút."""
    writer = AINewsWriter()

    event = EconomicEvent(
        id="usd_cpi_flash",
        title="Core CPI m/m",
        country="USD",
        impact=NewsImpact.HIGH,
        time_utc=datetime(2026, 10, 26, 12, 30, tzinfo=timezone.utc),
        forecast="0.3%",
        previous="0.2%",
        actual="0.4%",
    )

    post = writer.generate_realtime_flash_news_post(
        event=event,
        current_price=2040.5,
        price_before=2052.0,
        minutes_ago=2,
        use_ai=False,
    )

    assert "TIN NÓNG THỜI GIAN THỰC" in post
    assert "Vừa phát hành cách đây 2 phút" in post
    assert "Chỉ số CPI lõi" in post or "Core CPI" in post
    assert "0.4%" in post
    assert "0.3%" in post
    assert "DIỄN BIẾN GIÁ VÀNG" in post
    assert "-11.5 giá" in post
    assert "GIẢM MẠNH" in post
    assert "LỜI CẢNH BÁO" in post

