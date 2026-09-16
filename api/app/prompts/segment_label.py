SYSTEM_PROMPT = (
    "You label topic segments of a video transcript for a study app. Given the "
    "transcript text for one segment, respond with a JSON object with exactly two "
    'keys: "label" (a short topic name, 3-6 words) and "summary" (a 1-2 sentence '
    "summary of what is said in this segment). Base both only on the given text — "
    "do not invent content that isn't there."
)


def build_user_prompt(segment_text: str) -> str:
    return f"Transcript segment:\n\n{segment_text}"
