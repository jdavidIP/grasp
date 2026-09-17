from app.generation import llm
from app.models.chunk import TranscriptChunk
from app.prompts.rerank import SYSTEM_PROMPT, build_user_prompt

RERANK_KEEP = 5


async def rerank(
    question: str, chunks: list[TranscriptChunk], keep: int = RERANK_KEEP
) -> list[TranscriptChunk]:
    """Reorders candidate chunks by relevance to the question via an LLM scoring
    pass, keeping the top `keep`. Falls back to the original order (truncated) if
    the model's response can't be parsed into a valid ranking."""
    if len(chunks) <= keep:
        return chunks

    result = await llm.generate_json(
        SYSTEM_PROMPT, build_user_prompt(question, [c.text for c in chunks])
    )
    indices = result.get("ranked_indices")
    if not isinstance(indices, list):
        return chunks[:keep]

    seen: set[int] = set()
    ranked: list[TranscriptChunk] = []
    for i in indices:
        if isinstance(i, int) and 0 <= i < len(chunks) and i not in seen:
            ranked.append(chunks[i])
            seen.add(i)

    return ranked[:keep] if ranked else chunks[:keep]
