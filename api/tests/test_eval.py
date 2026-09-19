import pytest

from app.eval.draft_golden import sample_windows, spread_pick
from app.eval.retrieval import first_hit_rank, span_coverage, summarize


def test_first_hit_rank_is_one_based_and_ignores_touching_edges():
    span = (10.0, 20.0)
    assert first_hit_rank([(0, 10), (15, 30)], span) == 2  # (0,10) only touches
    assert first_hit_rank([(0, 5), (25, 30)], span) is None


def test_span_coverage_unions_overlapping_ranges():
    span = (10.0, 20.0)
    assert span_coverage([(0, 14), (12, 16)], span) == pytest.approx(0.6)
    assert span_coverage([(0, 100)], span) == 1.0
    assert span_coverage([], span) == 0.0


def test_summarize_hit_rate_recall_and_mrr():
    results = [
        ([(10, 20), (30, 40)], (10.0, 20.0)),  # hit at rank 1, full coverage
        ([(30, 40), (15, 20)], (10.0, 20.0)),  # hit at rank 2, half coverage
    ]
    summary = summarize(results, ks=(1, 2, 5))
    assert summary["hit_rate@1"] == 0.5
    assert summary["hit_rate@2"] == 1.0
    assert summary["recall@2"] == pytest.approx(0.75)
    assert summary["mrr"] == pytest.approx(0.75)
    assert "hit_rate@5" not in summary  # beyond what was retrieved


def test_sample_windows_spreads_across_transcript():
    cues = [{"start": i * 5.0, "end": i * 5.0 + 5, "text": str(i)} for i in range(100)]
    windows = sample_windows(cues, 4)
    assert len(windows) == 4
    assert [w[0]["start"] for w in windows] == [60.0, 185.0, 310.0, 435.0]
    assert all(w[-1]["end"] - w[0]["start"] >= 40 for w in windows)


def test_spread_pick_keeps_order_and_spreads():
    assert spread_pick(list(range(10)), 3) == [0, 3, 6]
    assert spread_pick([1, 2], 5) == [1, 2]
