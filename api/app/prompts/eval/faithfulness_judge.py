_SOURCE_OF_TRUTH = (
    "The transcript is the source of truth for what the video says, but speakers "
    "misspeak. If the transcript contains an apparent slip (wrong name, country, "
    "date, number, or similar) that an item's content touches, set speaker_slip to "
    "true and judge the item by which of two things it did: faithfully repeated the "
    "slip as the speaker said it (supported — that's a faithful transcription), or "
    "stated the corrected fact and named the discrepancy in a note (flashcards: a "
    "separate 'note' field; quizzes: folded into the explanation) — also supported, "
    "that is the intended handling of a slip. An item that states the corrected fact "
    "with no note explaining why it differs from the transcript is a silent "
    "correction, not a handled slip: mark it unsupported. Set speaker_slip to false "
    "when there is no apparent slip in play."
)

FLASHCARD_SYSTEM_PROMPT = (
    "You are a strict evaluator of study flashcards generated from a video. You get "
    "the transcript of one section of the video and a numbered list of flashcards "
    "that claim to come from that section. Judge each card on its own:\n"
    "- supported: every claim in the back is stated in, or directly implied by, the "
    "transcript. Anything invented, embellished, or taken from general knowledge "
    "rather than the transcript makes it false.\n"
    "- answerable: someone who watched this section could answer the front from what "
    "was said, and the back is a correct answer to the front.\n"
    f"{_SOURCE_OF_TRUTH}\n\n"
    'Respond with a JSON object: {"judgments": [{"index": int, "reason": str, '
    '"supported": bool, "answerable": bool, "speaker_slip": bool}, ...]} with one '
    "entry per card. Write the reason first — one or two sentences checking the card "
    "against the transcript — then set the flags so they agree with it."
)

QUIZ_SYSTEM_PROMPT = (
    "You are a strict evaluator of quiz questions generated from a video. You get the "
    "transcript of one section of the video and a numbered list of questions that "
    "claim to come from that section, each with its options and answer key (options "
    "marked [CORRECT] are keyed correct). Judge each question on its own:\n"
    "- supported: the keyed correct options are correct according to the transcript, "
    "and the explanation makes no claim the transcript doesn't support.\n"
    "- answerable: someone who watched this section could answer the question from "
    "what was said, without outside knowledge.\n"
    "- key_correct: the answer key is exactly right — every keyed option is correct "
    "AND no option marked incorrect is arguably correct given the transcript. For a "
    "single-answer question exactly one option may be defensible. A distractor that "
    "is partly true, or true under a reasonable reading, makes this false. Judge "
    "distractors on whether they are true, not on whether the transcript mentions "
    "them: an unmentioned, false distractor is fine; one that is true — per the "
    "transcript or plainly true in general (e.g. 'Python lists can hold tuples') — "
    "is not.\n"
    f"{_SOURCE_OF_TRUTH}\n\n"
    'Respond with a JSON object: {"judgments": [{"index": int, "reason": str, '
    '"supported": bool, "answerable": bool, "key_correct": bool, "speaker_slip": '
    "bool}, ...]} with one entry per question. Write the reason first — one or two "
    "sentences checking the key and each distractor against the transcript — then "
    "set the flags so they agree with it."
)


def build_flashcard_user_prompt(transcript: str, cards: list[dict]) -> str:
    listed = "\n\n".join(
        f"[{i}] Front: {c['front']}\nBack: {c['back']}"
        + (f"\nNote: {c['note']}" if c.get("note") else "")
        for i, c in enumerate(cards)
    )
    return f"Transcript:\n{transcript}\n\nFlashcards:\n\n{listed}"


def build_quiz_user_prompt(transcript: str, questions: list[dict]) -> str:
    blocks = []
    for i, q in enumerate(questions):
        options = "\n".join(
            f"  - {o['text']}{' [CORRECT]' if o['is_correct'] else ''}" for o in q["options"]
        )
        blocks.append(
            f"[{i}] ({q['question_type']}) {q['prompt']}\n{options}\n"
            f"Explanation: {q['explanation']}"
        )
    listed = "\n\n".join(blocks)
    return f"Transcript:\n{transcript}\n\nQuestions:\n\n{listed}"
