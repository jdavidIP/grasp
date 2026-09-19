QUESTION_SYSTEM_PROMPT = (
    "You help build an evaluation set for a video Q&A retrieval system. Given the "
    "video's topic list and a short excerpt from its transcript, write ONE question a "
    "student studying the video's subject matter might ask, whose answer is contained "
    "in this excerpt.\n\n"
    "Rules:\n"
    "- The question must be about the subject matter the video teaches or discusses "
    "(its concepts, arguments, facts, examples, techniques), as listed in the topics. "
    "Never ask about incidental or meta content: course logistics (assignments, "
    "grading, exams, slides, schedules, platforms), classroom or recording remarks, "
    "the speaker's plans for what the course or video will cover or focus on (a "
    "roadmap of upcoming sections is not subject matter), channel plugs, sponsors, "
    "greetings, or small talk. If a lecture on quantum physics mentions the room is "
    "hot, that is not a question.\n"
    "- Write the question as a student would ask it after watching: standalone, about "
    "the subject itself. Never mention 'the excerpt', 'the snippet', 'the course', or "
    "'according to the speaker'.\n"
    "- If the excerpt contains no subject-matter content by that standard, set "
    "question to null. Returning null is expected and better than a weak question.\n"
    "- Paraphrase. Do not copy distinctive words or phrases from the excerpt into the "
    "question — use synonyms or describe the idea — so the question can't be answered "
    "by keyword matching alone.\n"
    "- The question must be specific enough that this excerpt, not the video in "
    "general, is where the answer lives. No summary or 'what is this about' questions.\n"
    "- The transcript is the source of truth for what the video says, but speakers "
    "misspeak. If the excerpt contains an apparent slip or factual error (wrong name, "
    "country, date, number), phrase the question so it doesn't depend on the slip, "
    "and describe the slip in note. Otherwise note is null.\n\n"
    'Respond with a JSON object: {"question": string or null, "answer": string '
    '(one short sentence, or null), "note": string or null}.'
)


def build_question_user_prompt(
    video_title: str, topics: list[tuple[str, str]], excerpt: str
) -> str:
    listed = "\n".join(f"- {label}: {summary}" for label, summary in topics)
    return f"Video title: {video_title}\n\nTopics covered:\n{listed}\n\nExcerpt:\n{excerpt}"


OUT_OF_SCOPE_SYSTEM_PROMPT = (
    "You help build an evaluation set for a video Q&A system that must say when a "
    "video does NOT cover something. Given a video's topic list, write questions "
    "that sound like they belong to this video — same subject area, adjacent "
    "concepts, plausible follow-ups — but that the video does not actually answer, "
    "judging from the topics and summaries. Avoid questions that are obviously "
    "off-topic (a cooking question for a physics lecture is useless); the point is "
    "to tempt the system into answering from general knowledge.\n\n"
    'Respond with a JSON object: {"questions": [string, ...]}.'
)


def build_out_of_scope_user_prompt(
    video_title: str, topics: list[tuple[str, str]], count: int
) -> str:
    listed = "\n".join(f"- {label}: {summary}" for label, summary in topics)
    return f"Video title: {video_title}\n\nTopics covered:\n{listed}\n\nWrite {count} questions."
