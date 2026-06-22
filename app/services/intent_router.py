from __future__ import annotations

from app.domain.chat_intent import ChatIntent

SOP_KEYWORDS = {
    "sop",
    "aturan",
    "prosedur",
    "absensi",
    "bonus",
    "insentif",
    "keterlambatan",
    "kpi",
    "spg",
}

ANALYTICS_KEYWORDS = {
    "revenue",
    "penjualan",
    "pengunjung",
    "visitor",
    "anomali",
    "outlier",
    "tren",
    "mingguan",
    "dataset",
    "total",
    "jumlah",
    "rata-rata",
    "average",
}


def route_intent(message: str) -> ChatIntent:
    lowered = message.lower()
    sop_terms = {kw for kw in SOP_KEYWORDS if kw in lowered}
    analytics_terms = {kw for kw in ANALYTICS_KEYWORDS if kw in lowered}

    if sop_terms and analytics_terms:
        return ChatIntent.COMBINED
    if sop_terms:
        return ChatIntent.SOP_QUESTION
    if analytics_terms:
        if "anomali" in lowered or "outlier" in lowered:
            return ChatIntent.ANALYTICS_ANOMALY
        if "tren" in lowered or "mingguan" in lowered or "trend" in lowered:
            return ChatIntent.ANALYTICS_TREND
        return ChatIntent.ANALYTICS_SUMMARY
    return ChatIntent.UNSUPPORTED
