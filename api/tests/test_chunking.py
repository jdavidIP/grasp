from app.ingestion import chunking


def _cue(start: float, end: float, text: str) -> dict:
    return {"start": start, "end": end, "text": text}


def test_cues_for_segment_filters_by_time_range():
    cues = [_cue(0.0, 5.0, "a"), _cue(5.0, 10.0, "b"), _cue(10.0, 15.0, "c")]
    result = chunking._cues_for_segment(cues, 5.0, 10.0)
    assert [c["text"] for c in result] == ["b"]


def test_chunk_cues_single_chunk_when_under_target(monkeypatch):
    monkeypatch.setattr(chunking, "CHUNK_TARGET_TOKENS", 100)
    monkeypatch.setattr(chunking, "_token_count", lambda text: 1)
    cues = [_cue(float(i), float(i + 1), f"word{i}") for i in range(5)]
    chunks = chunking._chunk_cues(cues)
    assert len(chunks) == 1
    assert chunks[0]["start_time"] == 0.0
    assert chunks[0]["end_time"] == 5.0
    assert chunks[0]["token_count"] == 5


def test_chunk_cues_splits_with_overlap(monkeypatch):
    monkeypatch.setattr(chunking, "CHUNK_TARGET_TOKENS", 3)
    monkeypatch.setattr(chunking, "_token_count", lambda text: 1)
    cues = [_cue(float(i), float(i + 1), f"word{i}") for i in range(10)]

    chunks = chunking._chunk_cues(cues)

    assert [c["token_count"] for c in chunks] == [3, 3, 3, 3, 2]
    assert chunks[0]["start_time"] == 0.0
    assert chunks[-1]["end_time"] == 10.0
    # consecutive chunks overlap: chunk 1 starts one cue before chunk 0 ends
    assert chunks[1]["start_time"] < chunks[0]["end_time"]


def test_chunk_cues_huge_single_cue_does_not_loop_forever(monkeypatch):
    monkeypatch.setattr(chunking, "CHUNK_TARGET_TOKENS", 3)
    monkeypatch.setattr(chunking, "_token_count", lambda text: 10)
    cues = [_cue(0.0, 1.0, "one giant cue"), _cue(1.0, 2.0, "next cue")]

    chunks = chunking._chunk_cues(cues)

    assert len(chunks) == 2
    assert chunks[0]["token_count"] == 10


def test_chunk_cues_empty_input_returns_empty():
    assert chunking._chunk_cues([]) == []


async def test_chunk_transcript_assigns_segment_order_index_and_embeddings(monkeypatch):
    monkeypatch.setattr(chunking, "CHUNK_TARGET_TOKENS", 100)
    monkeypatch.setattr(chunking, "_token_count", lambda text: 1)

    cues = [_cue(float(i), float(i + 1), f"word{i}") for i in range(6)]
    segments = [
        {"order_index": 0, "start_time": 0.0, "end_time": 3.0},
        {"order_index": 1, "start_time": 3.0, "end_time": 6.0},
    ]

    async def fake_embed(texts):
        return [[float(i)] for i in range(len(texts))]

    monkeypatch.setattr(chunking.llm, "embed_texts", fake_embed)

    chunks = await chunking.chunk_transcript(cues, segments)

    assert len(chunks) == 2
    assert [c["segment_order_index"] for c in chunks] == [0, 1]
    assert [c["embedding"] for c in chunks] == [[0.0], [1.0]]


async def test_chunk_transcript_no_segments_returns_empty():
    assert await chunking.chunk_transcript([], []) == []
