from app.prompts.flashcards import DIFFICULTY_GUIDE

TYPE_GUIDE = {
    "multiple_choice": "multiple_choice: exactly one option is correct.",
    "multi_select": (
        "multi_select: at least one and at most all-but-one options are correct; the "
        'question must end with "Select all that apply."'
    ),
    "true_false": (
        "true_false: the prompt is a single declarative statement to judge true or false, "
        'answered with "answer_is_true". Make about half the statements false. A true '
        "statement must restate something the video explicitly says. A false statement "
        "must be a plausible distortion that the video explicitly contradicts (a changed "
        "name, number, cause, or outcome), so someone who watched can point to the line "
        "that makes it false. Never make a statement whose truth the video simply doesn't "
        "address, and never judge what a speaker believes, thinks, or considers serious "
        "unless they say it in so many words."
    ),
}

GENERATION_SYSTEM_PROMPT = (
    "You write quiz questions from a video's transcript for someone studying it. Each "
    "topic below is numbered. Respond with a JSON object: "
    '{"questions": [{"type": "multiple_choice"|"multi_select"|"true_false", '
    '"prompt": str, "options": [{"text": str, "is_correct": bool}, ...], '
    '"answer_is_true": bool, "explanation": str, "topic_index": int, '
    '"difficulty": "easy"|"medium"|"hard"}, ...]}. "options" is only for multiple_choice '
    'and multi_select; "answer_is_true" is only for true_false. "topic_index" is the '
    "number of the topic the question is drawn from, and the correct answer must be "
    "supported by that topic's content alone — never invent facts that aren't there.\n\n"
    "Every claim the answer key relies on must be stated in the topic's content, not "
    "inferred from it, combined from separate remarks, or filled in from general "
    "knowledge. If the content only implies something, don't key it as correct.\n\n"
    "Distractors (incorrect options) are what make a quiz worth taking. Draw them from "
    "things actually said elsewhere in the video — other topics, or the sections listed "
    'under "Other topics in the video" — that do NOT answer this question. They must be '
    'plausible and on-topic but verifiably wrong. Never use "all of the above" or '
    '"none of the above". Keep every option about the same length and style so the '
    "correct one is not obvious from its shape. Don't manufacture distractors by adding "
    'absolute words ("only", "always", "never", "all", "must") to a true statement — '
    "those are either arguable or trivially wrong. A distractor must be wrong because "
    "the video says something different, not merely because the video doesn't say it.\n\n"
    '"explanation" says in one to three sentences why the correct answer is right and, '
    f"where useful, why a tempting distractor is wrong. {DIFFICULTY_GUIDE}"
)

VALIDATION_SYSTEM_PROMPT = (
    "You audit quiz questions against video transcript topics. Each topic and each "
    "candidate question is numbered. A question is valid only if ALL of these hold: "
    "(1) its cited topic's content explicitly states every claim marked correct — "
    "reject keys that are only inferred, combined from separate remarks, or supplied by "
    "general knowledge; "
    "(2) every option marked incorrect is actually wrong according to the video — none "
    "is correct, partially correct, or arguably correct under a reasonable reading, and "
    "for multi_select the correct set is exactly the set of correct options; "
    "(3) the question is unambiguous and answerable from the video alone; "
    "(4) for true_false, a true statement restates something said, and a false one is "
    "contradicted by something said — reject statements the video doesn't address, and "
    "statements about a speaker's beliefs or attitudes they never stated. When in doubt, "
    "reject: a missing question costs less than a wrong answer key. Respond with "
    'a JSON object: {"valid_question_indices": [int, ...]} listing the numbers of every '
    "valid question."
)


def _numbered_topics(topics: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"[{i}] {label}\n{text}" for i, (label, text) in enumerate(topics))


def _other_topics_block(other_topics: list[tuple[str, str]]) -> str:
    if not other_topics:
        return ""
    lines = "\n".join(f"- {label}: {summary}" for label, summary in other_topics)
    return f"\n\nOther topics in the video (distractor source only):\n{lines}"


def build_generation_user_prompt(
    count: int,
    difficulty: str,
    question_types: list[str],
    options_per_question: int,
    topics: list[tuple[str, str]],
    other_topics: list[tuple[str, str]],
) -> str:
    difficulty_instruction = (
        "Use a mix of difficulties."
        if difficulty == "mixed"
        else f'Every question should be "{difficulty}" difficulty.'
    )
    type_lines = "\n".join(f"- {TYPE_GUIDE[t]}" for t in question_types)
    spread = (
        " Spread the questions roughly evenly across these types."
        if len(question_types) > 1
        else ""
    )
    return (
        f"Write {count} questions. {difficulty_instruction}\n\n"
        f"Question types:{spread}\n{type_lines}\n\n"
        f"Every multiple_choice and multi_select question has exactly {options_per_question} "
        f"options.\n\nTopics:\n\n{_numbered_topics(topics)}{_other_topics_block(other_topics)}"
    )


def _render_question(index: int, question: dict) -> str:
    if question["question_type"] == "true_false":
        answer = "True" if question["options"][0]["is_correct"] else "False"
        body = f"Statement: {question['prompt']}\nAnswer: {answer}"
    else:
        options = "\n".join(
            f"  - [{'correct' if o['is_correct'] else 'incorrect'}] {o['text']}"
            for o in question["options"]
        )
        body = f"Question: {question['prompt']}\nOptions:\n{options}"
    return (
        f"[{index}] type {question['question_type']}, topic {question['topic_index']}\n"
        f"{body}\nExplanation: {question['explanation']}"
    )


def build_validation_user_prompt(topics: list[tuple[str, str]], questions: list[dict]) -> str:
    numbered_questions = "\n\n".join(_render_question(i, q) for i, q in enumerate(questions))
    return f"Topics:\n\n{_numbered_topics(topics)}\n\nCandidate questions:\n\n{numbered_questions}"
