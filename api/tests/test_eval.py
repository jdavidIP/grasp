from types import SimpleNamespace

import pytest

from app.eval.chat import parse_judgment, question_kind
from app.eval.chat import summarize as summarize_chat
from app.eval.draft_golden import sample_windows, spread_pick
from app.eval.faithfulness import (
    _parse_judgments,
)
from app.eval.faithfulness import (
    summarize as summarize_faithfulness,
)
from app.eval.retrieval import first_hit_rank, span_coverage, summarize
from app.generation.common import segment_text
from app.prompts.faithfulness_judge import build_flashcard_user_prompt


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


def _judgment(**flags):
    base = {"supported": True, "answerable": True, "key_correct": True, "speaker_slip": False}
    return base | flags


def test_faithfulness_summary_splits_raw_and_kept():
    records = [
        {"kind": "quizzes", "validated": True, "kept": True, "judgment": _judgment()},
        {
            "kind": "quizzes",
            "validated": True,
            "kept": True,
            "judgment": _judgment(speaker_slip=True),
        },
        {
            "kind": "quizzes",
            "validated": False,
            "kept": False,
            "judgment": _judgment(key_correct=False),
        },
        {"kind": "quizzes", "validated": True, "kept": False, "judgment": None},
    ]
    summary = summarize_faithfulness(records)["quizzes"]
    assert summary["raw"]["n"] == 4
    assert summary["raw"]["unjudged"] == 1
    assert summary["raw"]["key_correct"] == pytest.approx(2 / 3)
    assert summary["raw"]["faithful"] == pytest.approx(2 / 3)
    assert summary["rejected"]["n"] == 1
    assert summary["rejected"]["faithful"] == 0.0
    assert summary["kept"]["faithful"] == 1.0
    assert summary["kept"]["speaker_slips"] == 1  # a slip is flagged, not failed


def test_parse_judgments_drops_malformed_and_out_of_range():
    result = {
        "judgments": [
            {"index": 0, "supported": True, "answerable": False, "speaker_slip": False},
            {"index": 1, "supported": "yes", "answerable": True, "speaker_slip": False},
            {"index": 7, "supported": True, "answerable": True, "speaker_slip": False},
        ]
    }
    parsed = _parse_judgments(result, 2, ("supported", "answerable"))
    assert parsed[0]["answerable"] is False
    assert parsed[1] is None


def test_segment_text_takes_cues_overlapping_the_segment():
    cues = [{"start": s, "end": s + 5, "text": str(s)} for s in (0, 5, 10, 15)]
    segment = SimpleNamespace(start_time=6, end_time=12)
    assert segment_text(cues, segment) == "5 10"


def test_build_flashcard_user_prompt_shows_the_judge_a_note_when_present():
    cards = [
        {"front": "F1", "back": "B1", "note": "The speaker says X; it's actually Y."},
        {"front": "F2", "back": "B2"},
    ]
    prompt = build_flashcard_user_prompt("transcript text", cards)
    assert "Note: The speaker says X; it's actually Y." in prompt
    assert prompt.count("Note:") == 1


def test_question_kind_separates_broad_from_out_of_scope():
    assert question_kind({"span": [1.0, 2.0]}) == "specific"
    assert question_kind({"span": None}) == "out_of_scope"
    assert question_kind({"span": None, "kind": "broad"}) == "broad"


def test_chat_parse_judgment_requires_every_flag_for_the_kind():
    ok = {"reason": "r", "declines": True, "supported": False, "speaker_slip": False}
    assert parse_judgment(ok, "out_of_scope") == ok
    # An out-of-scope judgment lacks answers_question, so it can't pass for a specific question.
    assert parse_judgment(ok, "specific") is None
    assert parse_judgment({**ok, "declines": "yes"}, "out_of_scope") is None


def test_chat_summary_rates_checks_grounding_and_routing():
    def record(kind, judgment, grounded=True, path="specific"):
        return {"kind": kind, "judgment": judgment, "grounded": grounded, "path": path}

    good = {"supported": True, "answers_question": True, "speaker_slip": False}
    unsupported = {"supported": False, "answers_question": True, "speaker_slip": True}
    records = [
        record("specific", good),
        record("specific", unsupported),
        record("specific", None, grounded=False),
        record("broad", good, path="broad"),
        record("broad", good),
    ]

    summary = summarize_chat(records)

    specific = summary["specific"]
    assert (specific["n"], specific["unjudged"]) == (3, 1)
    assert specific["supported"] == 0.5 and specific["faithful"] == 0.5
    assert specific["speaker_slips"] == 1
    assert specific["grounded"] == pytest.approx(2 / 3)
    assert summary["broad"]["routed_broad"] == 0.5
    assert "out_of_scope" not in summary
