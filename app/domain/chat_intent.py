from __future__ import annotations

from enum import StrEnum


class ChatIntent(StrEnum):
    SOP_QUESTION = "sop_question"
    ANALYTICS_SUMMARY = "analytics_summary"
    ANALYTICS_ANOMALY = "analytics_anomaly"
    ANALYTICS_TREND = "analytics_trend"
    COMBINED = "combined"
    UNSUPPORTED = "unsupported"
