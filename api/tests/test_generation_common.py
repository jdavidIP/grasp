import uuid

from app.generation import common
from app.models.chunk import TranscriptChunk


def _embedding(*nonzero_indices: int) -> list[float]:
    vec = [0.0] * 1536
    for i in nonzero_indices:
        vec[i] = 1.0
    return vec


def _chunk(text: str, embedding: list[float] | None = None) -> TranscriptChunk:
    return TranscriptChunk(
        id=uuid.uuid4(), text=text, start_time=0.0, end_time=1.0, embedding=embedding
    )


def test_cosine_similarity_identical_vectors_is_one():
    assert common.cosine_similarity(_embedding(0), _embedding(0)) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert common.cosine_similarity(_embedding(0), _embedding(1)) == 0.0


def test_top_chunks_by_centrality_keeps_fewer_than_requested():
    chunks = [_chunk("a", _embedding(0)), _chunk("b", _embedding(1))]
    assert common.top_chunks_by_centrality(chunks, keep=5) == chunks


def test_top_chunks_by_centrality_drops_outlier():
    close_a = _chunk("a", _embedding(0))
    close_b = _chunk("b", _embedding(0, 1))
    outlier = _chunk("c", _embedding(2))
    kept = common.top_chunks_by_centrality([close_a, close_b, outlier], keep=2)
    assert outlier not in kept


def test_overgenerate_count_adds_a_buffer():
    assert common.overgenerate_count(10) >= 13
