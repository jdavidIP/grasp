_SPEAKER_SLIPS = (
    "You may also get a numbered list of known speaker slips: places where the "
    "transcript's words are not what the speaker meant. If your answer relies on one, "
    "write the intended fact, never the slip, and put the slip's number in "
    '"slips_used". Don\'t mention the slip in the answer yourself: a note naming it is '
    "added for you."
)

SPECIFIC_SYSTEM_PROMPT = (
    "You answer questions about a video using only the provided transcript "
    'excerpts. Respond with a JSON object with three keys: "answer" (your response, '
    'grounded in what the excerpts say), "grounded" (true if the excerpts actually '
    'answer the question, false if they don\'t cover it), and "slips_used" (a list '
    "of the numbers of the known slips your answer relies on; empty when none). If "
    'the excerpts don\'t contain the answer, set "grounded" to false and write an '
    "answer that plainly says the video doesn't cover this — never invent "
    f"information that isn't in the excerpts.\n\n{_SPEAKER_SLIPS}"
)

BROAD_SYSTEM_PROMPT = (
    "You answer questions about a video using summaries of each of its topic "
    'segments. Respond with a JSON object with three keys: "answer", "grounded" '
    "(true unless the summaries genuinely don't address the question), and "
    '"slips_used" (a list of the numbers of the known slips your answer relies on; '
    "empty when none). Base your answer only on the given summaries — never invent "
    f"information that isn't there.\n\n{_SPEAKER_SLIPS}"
)


def _slips_block(slips: list[dict]) -> str:
    if not slips:
        return ""
    listed = "\n".join(
        f'Slip {i}: the transcript says "{s["said"]}"; the speaker means "{s["meant"]}".'
        for i, s in enumerate(slips)
    )
    return f"\n\nKnown speaker slips:\n{listed}"


def _history_block(history: list[dict]) -> str:
    if not history:
        return ""
    turns = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
    return f"Recent conversation:\n{turns}\n\n"


def build_specific_user_prompt(
    question: str, texts: list[str], history: list[dict], slips: list[dict]
) -> str:
    excerpts = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(texts))
    return (
        f"{_history_block(history)}Question: {question}\n\nTranscript excerpts:\n\n"
        f"{excerpts}{_slips_block(slips)}"
    )


def build_broad_user_prompt(
    question: str, segments: list[tuple[str, str]], history: list[dict], slips: list[dict]
) -> str:
    summaries = "\n\n".join(f"[{label}] {summary}" for label, summary in segments)
    return (
        f"{_history_block(history)}Question: {question}\n\nVideo topic summaries:\n\n"
        f"{summaries}{_slips_block(slips)}"
    )
