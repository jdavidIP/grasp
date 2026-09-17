SYSTEM_PROMPT = (
    "You rank transcript excerpts by how well they help answer a question, for a "
    "video Q&A system. Given a question and a numbered list of excerpts, respond "
    'with a JSON object with one key "ranked_indices": a list of the excerpt '
    "numbers (integers), ordered from most to least relevant to the question. "
    "Include every excerpt number exactly once."
)


def build_user_prompt(question: str, texts: list[str]) -> str:
    numbered = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(texts))
    return f"Question: {question}\n\nExcerpts:\n\n{numbered}"
