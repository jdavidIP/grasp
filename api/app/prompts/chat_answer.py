SPECIFIC_SYSTEM_PROMPT = (
    "You answer questions about a video using only the provided transcript "
    'excerpts. Respond with a JSON object with two keys: "answer" (your response, '
    'grounded in what the excerpts say) and "grounded" (true if the excerpts '
    "actually answer the question, false if they don't cover it). If the excerpts "
    'don\'t contain the answer, set "grounded" to false and write an answer that '
    "plainly says the video doesn't cover this — never invent information that "
    "isn't in the excerpts."
)

BROAD_SYSTEM_PROMPT = (
    "You answer questions about a video using summaries of each of its topic "
    'segments. Respond with a JSON object with two keys: "answer" and "grounded" '
    "(true unless the summaries genuinely don't address the question). Base your "
    "answer only on the given summaries — never invent information that isn't "
    "there."
)


def _history_block(history: list[dict]) -> str:
    if not history:
        return ""
    turns = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
    return f"Recent conversation:\n{turns}\n\n"


def build_specific_user_prompt(question: str, texts: list[str], history: list[dict]) -> str:
    excerpts = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(texts))
    return f"{_history_block(history)}Question: {question}\n\nTranscript excerpts:\n\n{excerpts}"


def build_broad_user_prompt(
    question: str, segments: list[tuple[str, str]], history: list[dict]
) -> str:
    summaries = "\n\n".join(f"[{label}] {summary}" for label, summary in segments)
    return f"{_history_block(history)}Question: {question}\n\nVideo topic summaries:\n\n{summaries}"
