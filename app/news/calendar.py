# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Economic News Calendar Engine.

Tự động thu thập, phân tích lịch kinh tế và tin tức tài chính:
- Đồng bộ nguồn cấp dữ liệu lịch kinh tế thời gian thực (ForexFactory Institutional Feed).
- Nhận diện các sự kiện Tin Đỏ (High Impact USD: FOMC, CPI, NFP, GDP, PMI...).
- Thiết lập vùng cấm giao dịch an toàn (News Blackout Window) trước & sau giờ ra tin để chống trượt giá (slippage) và quét SL 2 đầu.
- Phân tích kỳ vọng xu hướng tác động lên Vàng XAUUSD (Gold Impact Bias).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import threading
import time
from typing import List, Optional, Tuple
import urllib.request
import urllib.error

from app.news.models import EconomicEvent, GoldImpactBias, NewsImpact
from logger import get_logger

log = get_logger("vietkey.news")

FOREX_FACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


class NewsManager:
    """Quản lý Lịch Kinh Tế và Vùng An Toàn Tránh Bão Giá cho Vàng XAUUSD."""

    def __init__(self, cache_ttl_seconds: int = 3600):
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cached_events: List[EconomicEvent] = []
        self._last_fetched_at: Optional[datetime] = None
        self._lock = threading.Lock()

    def fetch_calendar(self, force: bool = False) -> List[EconomicEvent]:
        """
        Lấy lịch kinh tế tuần này từ API. Có cơ chế bộ nhớ đệm (Cache) để giảm tải mạng.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            if not force and self._cached_events and self._last_fetched_at:
                age = (now - self._last_fetched_at).total_seconds()
                if age < self.cache_ttl_seconds:
                    return list(self._cached_events)

        try:
            req = urllib.request.Request(
                FOREX_FACTORY_URL,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VietKeyGoldAI/1.0"},
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                raw_data = json.loads(resp.read().decode("utf-8"))

            events: List[EconomicEvent] = []
            for item in raw_data:
                ev = self._parse_event(item)
                if ev:
                    events.append(ev)

            with self._lock:
                self._cached_events = sorted(events, key=lambda x: x.time_utc)
                self._last_fetched_at = now

            log.info("✓ Đã nạp thành công %d sự kiện lịch kinh tế từ ForexFactory.", len(self._cached_events))
            return list(self._cached_events)

        except Exception as e:
            log.warning("Không thể tải lịch kinh tế từ ForexFactory (%s). Sử dụng dữ liệu cache gần nhất.", e)
            with self._lock:
                return list(self._cached_events)

    def _parse_event(self, item: dict) -> Optional[EconomicEvent]:
        """Chuyển đổi một bản ghi JSON ForexFactory thành đối tượng EconomicEvent."""
        try:
            title = str(item.get("title", "")).strip()
            country = str(item.get("country", "")).strip().upper()
            date_str = str(item.get("date", "")).strip()
            impact_raw = str(item.get("impact", "")).strip().lower()

            if not title or not date_str:
                return None

            # Phân loại mức độ tác động
            if impact_raw == "high":
                impact = NewsImpact.HIGH
            elif impact_raw == "medium":
                impact = NewsImpact.MEDIUM
            elif impact_raw == "holiday":
                impact = NewsImpact.HOLIDAY
            else:
                impact = NewsImpact.LOW

            # Parse ISO 8601 timestamp
            time_utc = datetime.fromisoformat(date_str).astimezone(timezone.utc)

            # Dự đoán xu hướng tác động lên Vàng
            bias, note = self._evaluate_gold_bias(title, country, impact)

            event_id = f"{country}_{int(time_utc.timestamp())}_{title[:10].replace(' ', '_')}"

            return EconomicEvent(
                id=event_id,
                title=title,
                country=country,
                impact=impact,
                time_utc=time_utc,
                forecast=str(item.get("forecast", "")),
                previous=str(item.get("previous", "")),
                actual="",
                bias_on_gold=bias,
                note=note,
            )
        except Exception:
            return None

    def _evaluate_gold_bias(self, title: str, country: str, impact: NewsImpact) -> Tuple[GoldImpactBias, str]:
        """Phân tích tính chất tin tức để đưa ra dự báo sơ bộ ảnh hưởng đến Vàng."""
        t_lower = title.lower()

        if country == "USD":
            if impact == NewsImpact.HIGH:
                if any(k in t_lower for k in ["fomc", "funds rate", "fed chair", "rate decision"]):
                    return (
                        GoldImpactBias.HIGH_VOLATILITY,
                        "Lãi suất Fed & FOMC: Rung lắc cực mạnh, giãn spread dữ dội. Tránh vào lệnh trước & trong giờ tin.",
                    )
                if any(k in t_lower for k in ["cpi", "inflation", "ppi"]):
                    return (
                        GoldImpactBias.HIGH_VOLATILITY,
                        "Lạm phát Mỹ: CPI cao hơn dự báo -> USD tăng mạnh -> Vàng giảm. CPI thấp -> Vàng bật tăng.",
                    )
                if any(k in t_lower for k in ["non-farm", "nfp", "employment change", "unemployment rate"]):
                    return (
                        GoldImpactBias.HIGH_VOLATILITY,
                        "Bảng lương Phi nông nghiệp (NFP): Tạo sóng lớn từ 15-30 giá ngay khi công bố.",
                    )
                if any(k in t_lower for k in ["gdp", "retail sales", "ism manufacturing", "ism services"]):
                    return (
                        GoldImpactBias.HIGH_VOLATILITY,
                        "Dữ liệu kinh tế Mỹ trọng yếu: Tác động trực tiếp đến sức mạnh chỉ số DXY và giá Vàng.",
                    )
                return (GoldImpactBias.HIGH_VOLATILITY, "Tin đỏ USD: Dự kiến quét 2 đầu, giãn biên độ.")

            if impact == NewsImpact.MEDIUM:
                return (GoldImpactBias.NEUTRAL, "Tin cam USD: Biến động vừa, theo dõi phản ứng giá tại vùng S/R.")

        return (GoldImpactBias.NEUTRAL, "Ít ảnh hưởng trực tiếp đến giá vàng XAUUSD.")

    def is_in_blackout_window(
        self,
        current_time: Optional[datetime] = None,
        buffer_before_min: int = 30,
        buffer_after_min: int = 20,
    ) -> Tuple[bool, Optional[EconomicEvent]]:
        """
        Kiểm tra xem thời điểm hiện tại có đang nằm trong Vùng Cấm Giao Dịch Tin Đỏ không.

        Quy tắc:
        - Trước khi ra tin đỏ USD [buffer_before_min] phút.
        - Sau khi ra tin đỏ USD [buffer_after_min] phút.

        Returns:
            Tuple (is_blackout, event): True nếu đang trong vùng nguy hiểm kèm thông tin sự kiện.
        """
        events = self.fetch_calendar()
        now = current_time or datetime.now(timezone.utc)

        for ev in events:
            # Chỉ áp dụng vùng cấm cho Tin Đỏ (High Impact) của đồng USD
            if ev.is_high_impact and ev.is_usd:
                start_window = ev.time_utc - timedelta(minutes=buffer_before_min)
                end_window = ev.time_utc + timedelta(minutes=buffer_after_min)

                if start_window <= now <= end_window:
                    return True, ev

        return False, None

    def get_upcoming_events(
        self,
        hours_ahead: int = 24,
        only_high_impact: bool = False,
    ) -> List[EconomicEvent]:
        """Lấy danh sách các sự kiện sắp diễn ra trong vòng N giờ tới."""
        events = self.fetch_calendar()
        now = datetime.now(timezone.utc)
        limit_time = now + timedelta(hours=hours_ahead)

        results = []
        for ev in events:
            if now <= ev.time_utc <= limit_time:
                if only_high_impact and not ev.is_high_impact:
                    continue
                results.append(ev)

        return results

    def get_next_high_impact_event(self) -> Optional[Tuple[EconomicEvent, float]]:
        """
        Tìm sự kiện Tin Đỏ USD tiếp theo gần nhất kèm số phút còn lại.

        Returns:
            Tuple (event, minutes_until) hoặc None nếu không có.
        """
        events = self.fetch_calendar()
        now = datetime.now(timezone.utc)

        for ev in events:
            if ev.is_high_impact and ev.is_usd and ev.time_utc > now:
                mins = (ev.time_utc - now).total_seconds() / 60.0
                return ev, round(mins, 1)

        return None
