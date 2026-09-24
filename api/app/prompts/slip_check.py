SYSTEM_PROMPT = (
    "You check one section of a video transcript for speaker slips: places where the "
    "words in the transcript are plainly not what the speaker meant, because they "
    "misspoke or the captions misheard them. List only slips that change a fact or a "
    "term: a wrong name, country, organization, date, number, or technical term (e.g. "
    '"Einstein published special relativity in 1805" when 1905 is meant, or captions '
    'writing "cash" for the programming term "cache"). Do not list grammar, filler '
    "words, stutters, "
    "punctuation, simplifications, or claims you merely disagree with. When in doubt, "
    "leave it out: a missed slip costs less than a wrong correction.\n\n"
    'Respond with a JSON object: {"slips": [{"reason": str, "said": str, "meant": '
    "str}, ...]}, or an empty list when there are none. Write the reason first — one "
    'sentence on why this is plainly a slip — then fill the rest. "said" must be '
    'copied exactly from the transcript, a few words long; "meant" is the same words '
    "with the slip corrected."
)


def build_user_prompt(transcript: str) -> str:
    return f"Transcript section:\n\n{transcript}"
