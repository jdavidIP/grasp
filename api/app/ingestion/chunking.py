import tiktoken

from app.generation import llm

CHUNK_TARGET_TOKENS = 500
CHUNK_OVERLAP_RATIO = 0.15

try:
    _encoding = tiktoken.encoding_for_model(llm.EMBEDDING_MODEL)
except KeyError:
    _encoding = tiktoken.get_encoding("cl100k_base")


def _token_count(text: str) -> int:
    return len(_encoding.encode(text))


def _cues_for_segment(cues: list[dict], start_time: float, end_time: float) -> list[dict]:
    return [cue for cue in cues if start_time <= cue["start"] < end_time]


def _chunk_cues(cues: list[dict]) -> list[dict]:
    """Greedily batches consecutive cues up to ~CHUNK_TARGET_TOKENS, stepping forward
    by less than a full batch so consecutive chunks overlap by ~CHUNK_OVERLAP_RATIO."""
    chunks: list[dict] = []
    i, n = 0, len(cues)

    while i < n:
        batch: list[dict] = []
        batch_tokens = 0
        j = i
        while j < n and batch_tokens < CHUNK_TARGET_TOKENS:
            batch.append(cues[j])
            batch_tokens += _token_count(cues[j]["text"])
            j += 1

        chunks.append(
            {
                "text": " ".join(cue["text"].strip() for cue in batch),
                "start_time": batch[0]["start"],
                "end_time": batch[-1]["end"],
                "token_count": batch_tokens,
            }
        )

        if j >= n:
            break
        overlap_count = max(1, int(len(batch) * CHUNK_OVERLAP_RATIO))
        i = max(i + 1, j - overlap_count)

    return chunks


async def chunk_transcript(cues: list[dict], segments: list[dict]) -> list[dict]:
    """Chunks cues within each segment's time range and batch-embeds them together.

    Segments aren't persisted yet at this stage, so each chunk carries
    `segment_order_index` rather than a real `segment_id` — the caller maps that back
    to a TranscriptSegment.id once segments are inserted.
    """
    all_chunks: list[dict] = []
    for segment in segments:
        segment_cues = _cues_for_segment(cues, segment["start_time"], segment["end_time"])
        for chunk in _chunk_cues(segment_cues):
            chunk["segment_order_index"] = segment["order_index"]
            all_chunks.append(chunk)

    if not all_chunks:
        return []

    embeddings = await llm.embed_texts([chunk["text"] for chunk in all_chunks])
    for chunk, embedding in zip(all_chunks, embeddings, strict=True):
        chunk["embedding"] = embedding

    return all_chunks
