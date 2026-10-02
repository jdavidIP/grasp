SYSTEM_PROMPT = (
    "Decide whether answering a question about a video needs the whole video or "
    "just one part of it. The video may be a lecture, tutorial, podcast, interview, "
    'or conversation; "this", "here", "the episode", "the talk" all mean the video.\n'
    '- "broad": the question asks about the video itself as a whole: what it is '
    "about, what it covers or teaches, its topics, themes, or takeaways, or a summary "
    'or recap of all of it. Examples: "what\'s the gist?", "which ideas does the '
    'speaker go through?", "give me a rundown".\n'
    '- "specific": the question asks about a subject, concept, claim, person, event, '
    "or moment, even when it asks for a summary of that subject or is a general "
    '"why" or "how" question about it. Examples: "summarize the part on inflation", '
    '"why do bridges need expansion joints?", "what is recursion?".\n'
    "A question can be wide-ranging in subject (history, society, human nature) and "
    "still be specific. It is broad only when what it asks you to describe is the "
    "video's own content as a whole, not a subject. Asking which topics, concepts, or "
    "subjects the video covers is broad, even when it names the field.\n"
    'If unsure, answer "specific". Respond with a JSON object: {"broad": true or false}.'
)
