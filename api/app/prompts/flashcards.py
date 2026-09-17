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
    'str, "back": str, "topic_index": int, "difficulty": "easy"|"medium"|"hard"}, '
    '...]}. "front" is a question or prompt, "back" is the answer, grounded '
    "only in the given topic's content — never invent facts that aren't there. "
    f'"topic_index" is the number of the topic the card is drawn from. {DIFFICULTY_GUIDE}'
)

GROUNDING_SYSTEM_PROMPT = (
    "You check flashcards for accuracy against video transcript topics. Each topic "
    "and each candidate card is numbered. A card is grounded only if its claimed "
    "topic's content actually supports both its front and back. Respond with a "
    'JSON object: {"grounded_card_indices": [int, ...]} listing the numbers of '
    "every card that is grounded."
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


def build_grounding_user_prompt(topics: list[tuple[str, str]], cards: list[dict]) -> str:
    numbered_topics = "\n\n".join(
        f"[{i}] {label}\n{text}" for i, (label, text) in enumerate(topics)
    )
    numbered_cards = "\n\n".join(
        f"[{i}] topic {card['topic_index']}\nFront: {card['front']}\nBack: {card['back']}"
        for i, card in enumerate(cards)
    )
    return f"Topics:\n\n{numbered_topics}\n\nCandidate cards:\n\n{numbered_cards}"
