_SPEAKER_SLIPS = (
    "You may also get a numbered list of known speaker slips: places where the "
    "transcript's words are not what the speaker meant. The list is only a correction "
    "aid, not more content: it says nothing about whether the video answers the "
    'question, so decide "grounded" without it and ignore the list when the video '
    "doesn't cover the question. If your answer relies on one, write the intended "
    "fact, never the slip, and put the slip's number in \"slips_used\". Don't mention "
    "the slip in the answer yourself: a note naming it is added for you."
)

_HISTORY = (
    "You may also get the earlier conversation. Use it only to work out what the "
    "current question refers to: answer the current question, never an earlier one "
    "again."
)

SPECIFIC_SYSTEM_PROMPT = (
    "You answer questions about a video using only the provided transcript "
    'excerpts. Respond with a JSON object with three keys: "answer" (your response, '
    'grounded in what the excerpts say), "grounded" (true if the excerpts actually '
    'answer the question, false if they don\'t cover it), and "slips_used" (a list '
    "of the numbers of the known slips your answer relies on; empty when none). If "
    'the excerpts don\'t contain the answer, set "grounded" to false and write an '
    "answer that plainly says the video doesn't cover this — never invent "
    "information that isn't in the excerpts.\n\n"
    'Excerpts on a related topic are not an answer. "grounded" is true only when the '
    "excerpts state the answer to what was actually asked. If the question is about "
    "something the excerpts never mention (a person, event, technique, or use case), "
    "or the excerpts cover a neighbouring subject without answering the question, set "
    '"grounded" to false: say the video doesn\'t cover it, and you may briefly say what '
    "the video does cover instead, but never draw a connection between that material "
    "and the question that the excerpts don't make themselves.\n\n"
    f"{_HISTORY}\n\n{_SPEAKER_SLIPS}"
)

BROAD_SYSTEM_PROMPT = (
    "You answer questions about a video using summaries of each of its topic "
    'segments. Respond with a JSON object with three keys: "answer", "grounded" '
    "(true unless the summaries genuinely don't address the question), and "
    '"slips_used" (a list of the numbers of the known slips your answer relies on; '
    "empty when none). Base your answer only on the given summaries — never invent "
    "information that isn't there.\n\n"
    f"{_HISTORY} A question about the whole video still asks about the whole video "
    f"when the earlier conversation was about one part of it.\n\n{_SPEAKER_SLIPS}"
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
    return f"Earlier conversation (context only, already answered):\n{turns}\n\n"


def _question_block(question: str) -> str:
    # Before the sources: asked after them, the model declined answerable questions
    # whose excerpts only partly state the answer (#48).
    return f"Current question (answer this one): {question}\n\n"


def build_specific_user_prompt(
    question: str, texts: list[str], history: list[dict], slips: list[dict]
) -> str:
    excerpts = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(texts))
    return (
        f"{_history_block(history)}{_question_block(question)}Transcript excerpts:\n\n"
        f"{excerpts}{_slips_block(slips)}"
    )


def build_broad_user_prompt(
    question: str, segments: list[tuple[str, str]], history: list[dict], slips: list[dict]
) -> str:
    summaries = "\n\n".join(f"[{label}] {summary}" for label, summary in segments)
    return (
        f"{_history_block(history)}{_question_block(question)}Video topic summaries:\n\n"
        f"{summaries}{_slips_block(slips)}"
    )
