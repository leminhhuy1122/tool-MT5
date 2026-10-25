# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Economic News Models.

Cấu trúc dữ liệu cho Lịch kinh tế và Tin tức tài chính tác động tới Vàng (XAUUSD).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class NewsImpact(str, Enum):
    """Mức độ tác động của tin tức kinh tế."""
    HIGH = "HIGH"        # Tin Đỏ (Non-Farm, CPI, FOMC, GDP...) — Biến động cực mạnh
    MEDIUM = "MEDIUM"    # Tin Cam — Biến động vừa
    LOW = "LOW"          # Tin Vàng — Biến động nhẹ
    HOLIDAY = "HOLIDAY"  # Ngày nghỉ ngân hàng — Thanh khoản thấp


class GoldImpactBias(str, Enum):
    """Kỳ vọng xu hướng tác động lên Vàng XAUUSD."""
    BULLISH_GOLD = "BULLISH_GOLD"      # Tin xấu cho USD -> Vàng tăng
    BEARISH_GOLD = "BEARISH_GOLD"      # Tin tốt cho USD -> Vàng giảm
    HIGH_VOLATILITY = "HIGH_VOLATILITY"# Quét 2 đầu, giãn spread mạnh
    NEUTRAL = "NEUTRAL"                # Ít ảnh hưởng


@dataclass
class EconomicEvent:
    """Sự kiện kinh tế trong lịch tài chính."""
    id: str
    title: str
    country: str
    impact: NewsImpact
    time_utc: datetime
    forecast: str = ""
    previous: str = ""
    actual: str = ""
    bias_on_gold: GoldImpactBias = GoldImpactBias.HIGH_VOLATILITY
    note: str = ""

    @property
    def is_high_impact(self) -> bool:
        """Kiểm tra xem sự kiện có phải tin đỏ hay không."""
        return self.impact == NewsImpact.HIGH

    @property
    def is_usd(self) -> bool:
        """Kiểm tra xem sự kiện có liên quan trực tiếp đến đồng USD hay không."""
        return self.country.upper() == "USD"

    def to_dict(self) -> dict:
        """Chuyển đổi thành từ điển JSON-serializable."""
        return {
            "id": self.id,
            "title": self.title,
            "country": self.country,
            "impact": self.impact.value,
            "timeUtc": self.time_utc.isoformat(),
            "forecast": self.forecast,
            "previous": self.previous,
            "actual": self.actual,
            "biasOnGold": self.bias_on_gold.value,
            "note": self.note,
        }
