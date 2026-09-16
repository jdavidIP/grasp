from unittest.mock import AsyncMock

from app.ingestion import segmentation as seg


def _cue(start: float, end: float, text: str) -> dict:
    return {"start": start, "end": end, "text": text}


def test_group_cues_splits_on_sentence_end():
    cues = [
        _cue(0.0, 1.0, "Hello there."),
        _cue(1.0, 2.0, "How are"),
        _cue(2.0, 2.5, "you?"),
    ]
    units = seg._group_cues_into_units(cues)
    assert [u.text for u in units] == ["Hello there.", "How are you?"]
    assert units[0].start == 0.0
    assert units[0].end == 1.0
    assert units[1].start == 1.0
    assert units[1].end == 2.5


def test_group_cues_splits_on_silence_gap():
    cues = [
        _cue(0.0, 1.0, "First thought here"),
        _cue(5.0, 6.0, "second thought here"),
    ]
    units = seg._group_cues_into_units(cues)
    assert [u.text for u in units] == ["First thought here", "second thought here"]


def test_group_cues_skips_blank_cues():
    cues = [_cue(0.0, 1.0, "  "), _cue(1.0, 2.0, "Real text.")]
    units = seg._group_cues_into_units(cues)
    assert [u.text for u in units] == ["Real text."]


def test_find_breakpoints_below_minimum_units_returns_none():
    embeddings = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    assert seg._find_breakpoints(embeddings) == []


def test_find_breakpoints_detects_clear_topic_shift(monkeypatch):
    monkeypatch.setattr(seg.settings, "segmentation_breakpoint_percentile", 90.0)
    monkeypatch.setattr(seg.settings, "max_segments_per_video", 40)
    embeddings = [[1.0, 0.0]] * 3 + [[0.0, 1.0]] * 3
    assert seg._find_breakpoints(embeddings) == [3]


def test_find_breakpoints_respects_max_segments_cap(monkeypatch):
    monkeypatch.setattr(seg.settings, "segmentation_breakpoint_percentile", 1.0)
    monkeypatch.setattr(seg.settings, "max_segments_per_video", 2)
    # Three evenly-spaced clusters would normally yield 2 breakpoints (3 segments).
    # The second boundary (opposite vectors, max cosine distance) is the stronger
    # break; capping to max_segments_per_video=2 should keep only that one.
    embeddings = [[1.0, 0.0]] * 3 + [[0.0, 1.0]] * 3 + [[0.0, -1.0]] * 3
    breakpoints = seg._find_breakpoints(embeddings)
    assert breakpoints == [6]


def test_build_segments_splits_at_breakpoints():
    units = [seg.Unit(float(i), float(i + 1), f"u{i}") for i in range(5)]
    segments = seg._build_segments(units, [2, 4])
    assert [len(s.units) for s in segments] == [2, 2, 1]


def test_merge_short_segments_merges_into_previous(monkeypatch):
    monkeypatch.setattr(seg.settings, "min_segment_duration_seconds", 60)
    long_seg = seg.SegmentDraft([seg.Unit(0.0, 100.0, "long")])
    short_seg = seg.SegmentDraft([seg.Unit(100.0, 110.0, "short")])
    merged = seg._merge_short_segments([long_seg, short_seg])
    assert len(merged) == 1
    assert [u.text for u in merged[0].units] == ["long", "short"]


def test_merge_short_segments_merges_leading_segment_forward(monkeypatch):
    monkeypatch.setattr(seg.settings, "min_segment_duration_seconds", 60)
    short_seg = seg.SegmentDraft([seg.Unit(0.0, 10.0, "short")])
    long_seg = seg.SegmentDraft([seg.Unit(10.0, 200.0, "long")])
    merged = seg._merge_short_segments([short_seg, long_seg])
    assert len(merged) == 1
    assert [u.text for u in merged[0].units] == ["short", "long"]


async def test_segment_transcript_end_to_end(monkeypatch):
    monkeypatch.setattr(seg.settings, "segmentation_breakpoint_percentile", 90.0)
    monkeypatch.setattr(seg.settings, "max_segments_per_video", 40)
    monkeypatch.setattr(seg.settings, "min_segment_duration_seconds", 0)

    cues = [_cue(float(i), float(i + 1), f"Sentence {i}.") for i in range(6)]

    async def fake_embed(texts):
        # first half of units cluster together, second half cluster together
        return [[1.0, 0.0] if i < 3 else [0.0, 1.0] for i in range(len(texts))]

    monkeypatch.setattr(seg.llm, "embed_texts", fake_embed)
    monkeypatch.setattr(
        seg.llm,
        "generate_json",
        AsyncMock(return_value={"label": "Topic", "summary": "Summary."}),
    )

    segments = await seg.segment_transcript(cues)

    assert len(segments) == 2
    assert [s["order_index"] for s in segments] == [0, 1]
    assert all(s["label"] == "Topic" for s in segments)
    assert segments[0]["start_time"] == 0.0
    assert segments[-1]["end_time"] == 6.0


async def test_segment_transcript_empty_cues_returns_empty():
    assert await seg.segment_transcript([]) == []
