_SPEAKER_SLIP = (
    "The sources are the source of truth for what the video says, but speakers "
    "misspeak. If the sources contain an apparent slip (wrong name, country, date, "
    "number, or similar) that the answer touches, set speaker_slip to true. Repeating "
    "the slip as the speaker said it counts as supported; so does stating the "
    "corrected fact while naming the discrepancy. Stating the corrected fact with no "
    "mention of the discrepancy is a silent correction: mark it unsupported. Set "
    "speaker_slip to false when there is no apparent slip in play."
)

_FORMAT = (
    "Write the reason first — one or two sentences checking the answer against the "
    "sources — then set the flags so they agree with it."
)

ANSWER_SYSTEM_PROMPT = (
    "You are a strict evaluator of a video Q&A assistant. You get a question the "
    "video is expected to answer, the sources the assistant was given (transcript "
    "excerpts, or summaries of the video's topics), and the assistant's answer. "
    "Judge the answer:\n"
    "- supported: every factual claim in the answer is stated in, or directly implied "
    "by, the sources. Anything invented, embellished, or taken from general knowledge "
    "rather than the sources makes it false. A plain statement that the video doesn't "
    "cover something is not a factual claim.\n"
    "- answers_question: the answer actually answers the question asked, with "
    "substance, rather than declining, hedging, or answering a different question.\n"
    f"{_SPEAKER_SLIP}\n\n"
    'Respond with a JSON object: {"reason": str, "supported": bool, '
    '"answers_question": bool, "speaker_slip": bool}. '
    f"{_FORMAT}"
)

DECLINE_SYSTEM_PROMPT = (
    "You are a strict evaluator of a video Q&A assistant. You get a question the "
    "video does NOT cover, the sources the assistant was given (transcript excerpts, "
    "or summaries of the video's topics), and the assistant's answer. The right "
    "behavior is to say the video doesn't cover it. Judge the answer:\n"
    "- declines: the answer plainly says the video doesn't cover the question. "
    "Briefly pointing to related material the video does cover is fine.\n"
    "- supported: every factual claim in the answer is stated in, or directly implied "
    "by, the sources. Answering the question anyway from general knowledge makes it "
    "false. The statement that the video doesn't cover the question is not a factual "
    "claim, so a plain decline is supported.\n"
    f"{_SPEAKER_SLIP}\n\n"
    'Respond with a JSON object: {"reason": str, "declines": bool, "supported": bool, '
    '"speaker_slip": bool}. '
    f"{_FORMAT}"
)


def build_user_prompt(question: str, sources: list[dict], answer: str) -> str:
    listed = "\n\n".join(f"[{i}] ({s['segment_label']}) {s['text']}" for i, s in enumerate(sources))
    return (
        f"Question: {question}\n\n"
        f"Sources:\n\n{listed or '(none: the assistant retrieved nothing)'}\n\n"
        f"Answer: {answer}"
    )
