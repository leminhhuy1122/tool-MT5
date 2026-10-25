# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Economic News Package.
"""

from app.news.calendar import NewsManager
from app.news.models import EconomicEvent, GoldImpactBias, NewsImpact

__all__ = [
    "NewsManager",
    "EconomicEvent",
    "NewsImpact",
    "GoldImpactBias",
]
