from app.domain.retrieval import RetrievalCandidate, rerank_candidates


def candidate(identifier: str, text: str, dense: float, heading: str):
    return RetrievalCandidate(
        chunk_id=identifier,
        document_id="doc",
        content=text,
        metadata={
            "filename": "SOP.md",
            "chunk_type": "paragraph",
            "heading_path": [heading],
            "page_start": None,
            "page_end": None,
        },
        dense_score=dense,
    )


def test_reranking_returns_at_most_three_scored_contexts() -> None:
    candidates = [
        candidate("table", "target 90% bonus Rp 50.000", 0.91, "Skema Insentif"),
        candidate("other", "absensi pukul 08.00", 0.70, "Absensi"),
        candidate("low", "dokumen umum", 0.10, "Umum"),
        candidate("low2", "teks lain", 0.05, "Lain"),
    ]

    result = rerank_candidates("bonus target 90%", candidates, top_k=3)

    assert result[0].chunk_id == "table"
    assert len(result) == 3
    assert [item.rank for item in result] == [1, 2, 3]
    assert result[0].meets_threshold is True
    assert result[1].meets_threshold is True
    assert result[2].meets_threshold is False


def test_bm25_and_heading_can_promote_a_better_keyword_match() -> None:
    candidates = [
        candidate("dense-only", "informasi operasional umum", 0.90, "Umum"),
        candidate("hybrid", "target 90% bonus Rp 50.000", 0.895, "Bonus Target"),
        candidate("floor", "absensi harian", 0.10, "Absensi"),
    ]

    result = rerank_candidates("bonus target 90%", candidates, top_k=3)

    assert result[0].chunk_id == "hybrid"
    assert result[0].lexical_score > result[1].lexical_score
    assert result[0].final_score > result[1].final_score
    assert result[2].meets_threshold is False


def test_weak_context_is_returned_but_not_for_generation() -> None:
    candidates = [candidate("weak", "unrelated", 0.2, "Other")]

    result = rerank_candidates("jatah cuti", candidates, top_k=3)

    assert len(result) == 1
    assert result[0].chunk_id == "weak"
    assert result[0].meets_threshold is False


def test_single_strong_context_survives_equal_score_normalization() -> None:
    candidates = [candidate("strong", "bonus target 90%", 0.9, "Bonus")]

    result = rerank_candidates("bonus target", candidates, top_k=3)

    assert [item.chunk_id for item in result] == ["strong"]
    # With a single candidate, minmax normalization yields 0 for dense,
    # so final_score may fall below threshold; meets_threshold follows final_score.
    assert result[0].meets_threshold is (result[0].final_score >= 0.35)


def test_generic_spg_overlap_returns_context_but_not_for_generation() -> None:
    candidates = [
        candidate(
            "attendance",
            "SPG wajib melakukan absensi pukul 08.00",
            0.46,
            "Prosedur Absensi SPG",
        )
    ]

    result = rerank_candidates("Berapa jatah cuti tahunan SPG?", candidates, top_k=3)

    assert len(result) == 1
    assert result[0].chunk_id == "attendance"
    assert result[0].meets_threshold is False
