from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from rank_bm25 import BM25Okapi

TOKEN_RE = re.compile(r"[\w]+(?:[.,]\d+)*%?|[<>]", re.UNICODE)
GENERIC_QUERY_TERMS = {
    "apa",
    "apakah",
    "berapa",
    "dari",
    "dan",
    "di",
    "jika",
    "lebih",
    "mengenai",
    "spg",
    "yang",
}
MINIMUM_DENSE_WITHOUT_KEYWORD = 0.60
DENSE_WEIGHT = 0.75
LEXICAL_WEIGHT = 0.20
HEADING_WEIGHT = 0.05
RETRIEVAL_STRATEGY = "dense_retrieval_bm25_heading_rerank"
RERANKER_NAME = "dense_bm25_heading_v1"


@dataclass(slots=True)
class RetrievalCandidate:
    chunk_id: str
    document_id: str
    content: str
    metadata: dict[str, Any]
    dense_score: float
    lexical_score: float = 0.0
    heading_bonus: float = 0.0
    final_score: float = 0.0
    rank: int = 0
    meets_threshold: bool = False


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if high == low:
        return [0.0] * len(values)
    return [(value - low) / (high - low) for value in values]


def rerank_candidates(
    question: str,
    candidates: list[RetrievalCandidate],
    *,
    top_k: int = 3,
    minimum_final_score: float = 0.35,
) -> list[RetrievalCandidate]:
    if not candidates:
        return []
    query_tokens = tokenize(question)
    candidate_tokens = [tokenize(candidate.content) for candidate in candidates]
    bm25 = BM25Okapi(candidate_tokens)
    lexical_raw = (
        [float(value) for value in bm25.get_scores(query_tokens)]
        if query_tokens
        else [0.0] * len(candidates)
    )
    dense_normalized = _minmax([candidate.dense_score for candidate in candidates])
    lexical_normalized = _minmax(lexical_raw)
    meaningful_query = {
        token for token in query_tokens if len(token) > 2 and token not in GENERIC_QUERY_TERMS
    }

    scored: list[RetrievalCandidate] = []
    keyword_matches: dict[str, bool] = {}
    for position, candidate in enumerate(candidates):
        heading_text = " ".join(candidate.metadata.get("heading_path", []))
        heading_tokens = set(tokenize(heading_text))
        content_tokens = set(candidate_tokens[position])
        heading_match = bool(meaningful_query & heading_tokens)
        keyword_matches[candidate.chunk_id] = bool(
            meaningful_query & (heading_tokens | content_tokens)
        )
        heading_bonus = 1.0 if heading_match else 0.0
        final = (
            DENSE_WEIGHT * dense_normalized[position]
            + LEXICAL_WEIGHT * lexical_normalized[position]
            + HEADING_WEIGHT * heading_bonus
        )
        scored.append(
            replace(
                candidate,
                lexical_score=lexical_normalized[position],
                heading_bonus=heading_bonus,
                final_score=final,
            )
        )
    scored.sort(key=lambda item: (item.final_score, item.dense_score), reverse=True)

    top_k_items = scored[:top_k]
    ranked: list[RetrievalCandidate] = []
    for index, item in enumerate(top_k_items):
        meets_threshold = item.final_score >= minimum_final_score
        ranked.append(replace(item, rank=index + 1, meets_threshold=meets_threshold))
    return ranked
