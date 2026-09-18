import uuid

from app.models.quiz import Quiz

SINGLE_ANSWER_TYPES = {"multiple_choice", "true_false"}


class InvalidAttempt(ValueError):
    """The submitted answers don't fit the quiz (unknown question or option, etc.)."""


def grade_attempt(
    quiz: Quiz, submitted: list[tuple[uuid.UUID, list[uuid.UUID]]]
) -> tuple[float, list[dict]]:
    """Grades a submission against the answer key stored at generation time — no LLM.

    A question is correct iff the selected option set equals the set of options marked
    correct (all-or-nothing). Questions missing from `submitted` count as skipped and
    incorrect. Returns (score, per-question results in quiz order); score is the
    fraction of all the quiz's questions answered correctly.

    Option ids are not FK-checked in `quiz_answers.selected_option_ids`, so every id is
    validated here against the question it was submitted for.
    """
    questions = {q.id: q for q in quiz.questions}
    selections: dict[uuid.UUID, set[uuid.UUID]] = {}
    for question_id, option_ids in submitted:
        question = questions.get(question_id)
        if question is None:
            raise InvalidAttempt(f"Question {question_id} is not part of this quiz.")
        if question_id in selections:
            raise InvalidAttempt(f"Question {question_id} was answered more than once.")
        selected = set(option_ids)
        if len(selected) != len(option_ids):
            raise InvalidAttempt(f"Question {question_id} has duplicate selected options.")
        if not selected <= {o.id for o in question.options}:
            raise InvalidAttempt(
                f"Question {question_id} has an option that does not belong to it."
            )
        if question.question_type in SINGLE_ANSWER_TYPES and len(selected) > 1:
            raise InvalidAttempt(f"Question {question_id} accepts only one selected option.")
        selections[question_id] = selected

    results = []
    for question in quiz.questions:
        selected = selections.get(question.id, set())
        correct = {o.id for o in question.options if o.is_correct}
        results.append(
            {
                "question_id": question.id,
                "is_correct": selected == correct,
                "selected_option_ids": [o.id for o in question.options if o.id in selected],
                "correct_option_ids": [o.id for o in question.options if o.id in correct],
                "explanation": question.explanation,
                "segment_id": question.segment_id,
                "source_start_time": question.source_start_time,
            }
        )
    score = sum(r["is_correct"] for r in results) / len(results) if results else 0.0
    return score, results
