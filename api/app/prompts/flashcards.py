DIFFICULTY_GUIDE = (
    '"easy" means the answer is stated directly in one excerpt. "medium" means it '
    'requires combining two statements or recalling a specific detail. "hard" '
    "means it requires inference across topics, or distinguishing between closely "
    "related points."
)

STYLE_GUIDE = {
    "definition": "Every card asks for the definition or meaning of a term or concept mentioned in the video.",
    "concept": "Every card tests understanding of a broader concept or relationship explained in the video.",
    "detail": "Every card tests recall of a specific fact, number, name, or detail mentioned in the video.",
    "mixed": "Vary the cards between definitions, broader concepts, and specific details.",
}

GENERATION_SYSTEM_PROMPT = (
    "You write flashcards from a video's transcript for someone studying it. Each "
    'topic below is numbered. Respond with a JSON object: {"cards": [{"front": '
    'str, "back": str, "topic_index": int, "difficulty": "easy"|"medium"|"hard", '
    '"note": str or null}, ...]}. "front" is a question or prompt, "back" is the '
    "answer, grounded only in the given topic's content — never invent facts that "
    "aren't there. "
    f'"topic_index" is the number of the topic the card is drawn from. {DIFFICULTY_GUIDE}\n\n'
    "Speakers misspeak, and captions mishear. If a topic contains an apparent slip "
    "(wrong name, date, number, or similar) that a card would otherwise be built on, "
    "don't state it as fact, and don't silently correct it either — prefer a "
    "different card from the same topic when one exists. When the idea is worth "
    "testing anyway, phrase front/back around the correct, intended meaning and set "
    '"note" to one short sentence naming the slip (e.g. "The speaker says \'angle '
    'brackets\'; Python lists use square brackets."). Leave "note" null otherwise.'
)

GROUNDING_SYSTEM_PROMPT = (
    "You check flashcards against the transcript of the video section they were "
    "written from. Each candidate card is numbered. A card is grounded if the "
    "transcript states or directly implies what its front asks about and what its back "
    "answers, and the back is a correct answer to the front. Reject a card whose back "
    "adds facts the transcript doesn't contain (embellishment or general knowledge). "
    "Don't reject a card just for paraphrasing, or for condensing what the section "
    "says.\n\n"
    "Speakers misspeak. If a card's note names an apparent slip in the transcript and "
    "the back states the corrected fact instead of the slip, treat the back as "
    "grounded — that is the intended handling of a slip, not embellishment. A card "
    "whose back diverges from the transcript with no note explaining why is not "
    'grounded. Respond with a JSON object: {"grounded_card_indices": [int, ...]} '
    "listing the numbers of every card that is grounded."
)


def build_generation_user_prompt(
    count: int, difficulty: str, style: str, topics: list[tuple[str, str]]
) -> str:
    numbered_topics = "\n\n".join(
        f"[{i}] {label}\n{text}" for i, (label, text) in enumerate(topics)
    )
    difficulty_instruction = (
        "Use a mix of difficulties."
        if difficulty == "mixed"
        else f'Every card should be "{difficulty}" difficulty.'
    )
    style_instruction = STYLE_GUIDE.get(style, STYLE_GUIDE["mixed"])
    return (
        f"Write {count} flashcards. {difficulty_instruction} {style_instruction}\n\n"
        f"Topics:\n\n{numbered_topics}"
    )


def build_grounding_user_prompt(transcript: str, cards: list[dict]) -> str:
    numbered_cards = "\n\n".join(
        f"[{i}] Front: {card['front']}\nBack: {card['back']}"
        + (f"\nNote: {card['note']}" if card.get("note") else "")
        for i, card in enumerate(cards)
    )
    return f"Transcript:\n{transcript}\n\nCandidate cards:\n\n{numbered_cards}"
