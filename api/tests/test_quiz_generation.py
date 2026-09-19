import uuid
from unittest.mock import AsyncMock

from app.db import async_session
from app.generation import quizzes
from app.models.chunk import TranscriptChunk
from app.models.segment import TranscriptSegment
from app.models.video import Video


def _embedding(*nonzero_indices: int) -> list[float]:
    vec = [0.0] * 1536
    for i in nonzero_indices:
        vec[i] = 1.0
    return vec


def _options(*flags: bool) -> list[dict]:
    return [{"text": f"opt {i}", "is_correct": f} for i, f in enumerate(flags)]


def _raw(question_type: str = "multiple_choice", **overrides) -> dict:
    raw = {
        "type": question_type,
        "prompt": "What weighs tokens?",
        "options": _options(True, False, False, False),
        "explanation": "Attention does.",
        "topic_index": 0,
        "difficulty": "easy",
    }
    raw.update(overrides)
    return raw


def test_parse_question_accepts_valid_multiple_choice():
    parsed = quizzes._parse_question(_raw(), options_per_question=4, topic_count=1)
    assert parsed is not None
    assert parsed["question_type"] == "multiple_choice"
    assert sum(o["is_correct"] for o in parsed["options"]) == 1


def test_parse_question_multiple_choice_requires_exactly_one_correct():
    for flags in [(False, False, False, False), (True, True, False, False)]:
        raw = _raw(options=_options(*flags))
        assert quizzes._parse_question(raw, 4, 1) is None


def test_parse_question_multi_select_needs_a_correct_and_an_incorrect_option():
    ok = _raw("multi_select", options=_options(True, True, False, False))
    assert quizzes._parse_question(ok, 4, 1) is not None
    for flags in [(False, False, False, False), (True, True, True, True)]:
        assert quizzes._parse_question(_raw("multi_select", options=_options(*flags)), 4, 1) is None


def test_parse_question_multi_select_prompt_gets_select_all_suffix_once():
    raw = _raw("multi_select", options=_options(True, True, False, False))
    parsed = quizzes._parse_question(raw, 4, 1)
    assert parsed["prompt"].endswith(quizzes.SELECT_ALL_SUFFIX)

    raw["prompt"] = "Which apply? Select all that apply."
    assert quizzes._parse_question(raw, 4, 1)["prompt"] == "Which apply? Select all that apply."


def test_parse_question_true_false_builds_true_false_options():
    raw = {
        "type": "true_false",
        "prompt": "Attention is cheap.",
        "answer_is_true": False,
        "explanation": "It is quadratic.",
        "topic_index": 0,
        "difficulty": "easy",
    }
    parsed = quizzes._parse_question(raw, 4, 1)
    assert [(o["text"], o["is_correct"]) for o in parsed["options"]] == [
        ("True", False),
        ("False", True),
    ]


def test_parse_question_rejects_structural_problems():
    bad = [
        _raw(type="short_answer"),
        _raw(prompt="  "),
        _raw(explanation=""),
        _raw(topic_index=5),
        _raw(options=_options(True, False, False)),  # wrong option count
        _raw(options=[{"text": "same", "is_correct": True}] * 4),  # duplicate options
        _raw(options=[{"text": "a", "is_correct": "yes"}] * 4),  # non-bool key
        _raw("true_false", options=None),  # missing answer_is_true
        "not a dict",
    ]
    for raw in bad:
        assert quizzes._parse_question(raw, 4, 1) is None


def test_duplicate_options_are_case_insensitive():
    raw = _raw(
        options=[
            {"text": "Softmax", "is_correct": True},
            {"text": " softmax ", "is_correct": False},
            {"text": "ReLU", "is_correct": False},
            {"text": "Tanh", "is_correct": False},
        ]
    )
    assert quizzes._parse_question(raw, 4, 1) is None


def test_ordered_options_keeps_answer_key_and_true_false_order():
    question = {"question_type": "multiple_choice", "options": _options(True, False, False, False)}
    ordered = quizzes._ordered_options(question)
    assert sorted(o["order_index"] for o in ordered) == [0, 1, 2, 3]
    assert [o["text"] for o in ordered if o["is_correct"]] == ["opt 0"]

    tf = {
        "question_type": "true_false",
        "options": [{"text": "True", "is_correct": True}, {"text": "False", "is_correct": False}],
    }
    assert [o["text"] for o in quizzes._ordered_options(tf)] == ["True", "False"]


async def test_generate_candidates_drops_invalid_and_unrequested_types(monkeypatch):
    monkeypatch.setattr(
        quizzes.llm,
        "generate_json",
        AsyncMock(
            return_value={
                "questions": [
                    _raw(),
                    _raw(options=_options(False, False, False, False)),  # no correct option
                    _raw(
                        "multi_select", options=_options(True, True, False, False)
                    ),  # not requested
                    _raw(difficulty="impossible"),
                ]
            }
        ),
    )

    questions = await quizzes._generate_candidates(
        3, "medium", ["multiple_choice"], 4, [("Topic", "text")], []
    )

    assert len(questions) == 2
    assert questions[1]["difficulty"] == "medium"  # invalid difficulty falls back to the request


async def test_generate_candidates_malformed_response_returns_empty(monkeypatch):
    monkeypatch.setattr(quizzes.llm, "generate_json", AsyncMock(return_value={}))
    assert await quizzes._generate_candidates(3, "easy", ["true_false"], 4, [("T", "x")], []) == []


async def test_filter_valid_keeps_only_listed_indices(monkeypatch):
    monkeypatch.setattr(
        quizzes.llm, "generate_json", AsyncMock(return_value={"valid_question_indices": [1]})
    )
    questions = [quizzes._parse_question(_raw(prompt=f"Q{i}"), 4, 1) for i in range(2)]

    valid = await quizzes._filter_valid(["text"], questions)

    assert valid == [questions[1]]


async def test_filter_valid_malformed_response_drops_all(monkeypatch):
    monkeypatch.setattr(quizzes.llm, "generate_json", AsyncMock(return_value={}))
    questions = [quizzes._parse_question(_raw(), 4, 1)]
    assert await quizzes._filter_valid(["text"], questions) == []


async def test_filter_valid_audits_each_cited_segment_against_its_own_transcript(monkeypatch):
    mock_generate = AsyncMock(
        side_effect=[{"valid_question_indices": [0]}, {"valid_question_indices": []}]
    )
    monkeypatch.setattr(quizzes.llm, "generate_json", mock_generate)
    questions = [
        quizzes._parse_question(_raw(prompt="A", topic_index=0), 4, 2),
        quizzes._parse_question(_raw(prompt="B", topic_index=1), 4, 2),
        quizzes._parse_question(_raw(prompt="C", topic_index=0), 4, 2),
    ]

    valid = await quizzes._filter_valid(["zero text", "one text"], questions)

    # One call per cited segment, each seeing only its own transcript.
    prompts = [call.args[1] for call in mock_generate.call_args_list]
    assert len(prompts) == 2
    assert "zero text" in prompts[0] and "one text" not in prompts[0]
    assert "one text" in prompts[1]
    # Segment 0 kept its first question (A) only; segment 1 kept nothing.
    assert valid == [questions[0]]


async def test_dedupe_drops_near_duplicate_prompts(monkeypatch):
    monkeypatch.setattr(
        quizzes.llm,
        "embed_texts",
        AsyncMock(return_value=[_embedding(0), _embedding(0), _embedding(1)]),
    )
    questions = [{"prompt": "Q1"}, {"prompt": "Q1 rephrased"}, {"prompt": "Q2"}]

    assert await quizzes._dedupe(questions) == [questions[0], questions[2]]


async def test_generate_quiz_no_matching_segments_returns_empty(monkeypatch):
    mock_generate = AsyncMock()
    monkeypatch.setattr(quizzes.llm, "generate_json", mock_generate)

    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.commit()

        result = await quizzes.generate_quiz(
            session, video.id, 5, "whole_video", [], ["multiple_choice"], 4, "mixed"
        )

        assert result == []
        mock_generate.assert_not_called()

        await session.delete(video)
        await session.commit()


async def test_generate_quiz_happy_path_keeps_key_and_feeds_other_segments_as_distractors(
    monkeypatch,
):
    mock_generate = AsyncMock(
        side_effect=[
            {"questions": [_raw(prompt="What weighs tokens?")]},
            {"valid_question_indices": [0]},
        ]
    )
    monkeypatch.setattr(quizzes.llm, "generate_json", mock_generate)
    monkeypatch.setattr(quizzes.llm, "embed_texts", AsyncMock(return_value=[_embedding(0)]))

    async with async_session() as session:
        video = Video(
            youtube_id=f"test-{uuid.uuid4().hex[:8]}",
            title="t",
            status="ready",
            transcript=[
                {"start": 5.0, "end": 10.0, "text": "attention weighs tokens by relevance"},
                {"start": 20.0, "end": 25.0, "text": "adam adapts the learning rate"},
            ],
        )
        session.add(video)
        await session.flush()

        selected = TranscriptSegment(
            video_id=video.id,
            order_index=0,
            label="Attention",
            summary="Attention mechanisms explained.",
            start_time=5.0,
            end_time=15.0,
        )
        other = TranscriptSegment(
            video_id=video.id,
            order_index=1,
            label="Optimizers",
            summary="Adam and SGD compared.",
            start_time=20.0,
            end_time=30.0,
        )
        session.add_all([selected, other])
        await session.flush()
        session.add(
            TranscriptChunk(
                video_id=video.id,
                segment_id=selected.id,
                text="attention weighs tokens by relevance",
                start_time=5.0,
                end_time=10.0,
                embedding=_embedding(0),
            )
        )
        await session.commit()

        result = await quizzes.generate_quiz(
            session, video.id, 1, "topics", [selected.id], ["multiple_choice"], 4, "mixed"
        )

        assert len(result) == 1
        question = result[0]
        assert question["segment_id"] == selected.id
        assert float(question["source_start_time"]) == 5.0
        assert question["order_index"] == 0
        assert [o["text"] for o in question["options"] if o["is_correct"]] == ["opt 0"]
        # The unselected segment reaches the generation prompt as distractor material.
        generation_prompt = mock_generate.call_args_list[0].args[1]
        assert "Optimizers: Adam and SGD compared." in generation_prompt
        # The validator checks the cited segment's raw transcript, not the summary.
        validation_prompt = mock_generate.call_args_list[1].args[1]
        assert "attention weighs tokens by relevance" in validation_prompt
        assert "adam adapts" not in validation_prompt

        await session.delete(video)
        await session.commit()


async def test_generate_quiz_whole_video_has_no_other_topics_block(monkeypatch):
    mock_generate = AsyncMock(
        side_effect=[{"questions": [_raw()]}, {"valid_question_indices": [0]}]
    )
    monkeypatch.setattr(quizzes.llm, "generate_json", mock_generate)
    monkeypatch.setattr(quizzes.llm, "embed_texts", AsyncMock(return_value=[_embedding(0)]))

    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.flush()
        session.add_all(
            [
                TranscriptSegment(
                    video_id=video.id,
                    order_index=i,
                    label=f"Topic {i}",
                    summary=f"Summary {i}.",
                    start_time=float(i * 10),
                    end_time=float(i * 10 + 9),
                )
                for i in range(2)
            ]
        )
        await session.commit()

        result = await quizzes.generate_quiz(
            session, video.id, 1, "whole_video", [], ["multiple_choice"], 4, "mixed"
        )

        assert len(result) == 1
        generation_prompt = mock_generate.call_args_list[0].args[1]
        assert "Other topics in the video" not in generation_prompt
        assert "[0] Topic 0" in generation_prompt and "[1] Topic 1" in generation_prompt

        await session.delete(video)
        await session.commit()


async def test_generate_quiz_tops_up_a_shortfall_once_without_repeats(monkeypatch):
    mock_generate = AsyncMock(
        side_effect=[
            {"questions": [_raw(prompt="First?"), _raw(prompt="Rejected?")]},
            {"valid_question_indices": [0]},  # validator keeps only "First?"
            {"questions": [_raw(prompt="Second?")]},
            {"valid_question_indices": [0]},
        ]
    )
    monkeypatch.setattr(quizzes.llm, "generate_json", mock_generate)
    monkeypatch.setattr(
        quizzes.llm, "embed_texts", AsyncMock(return_value=[_embedding(0), _embedding(1)])
    )

    async with async_session() as session:
        video = Video(youtube_id=f"test-{uuid.uuid4().hex[:8]}", title="t", status="ready")
        session.add(video)
        await session.flush()
        session.add(
            TranscriptSegment(
                video_id=video.id,
                order_index=0,
                label="Topic",
                summary="Summary.",
                start_time=0.0,
                end_time=10.0,
            )
        )
        await session.commit()

        trace: dict = {}
        result = await quizzes.generate_quiz(
            session, video.id, 2, "whole_video", [], ["multiple_choice"], 4, "mixed", trace=trace
        )

        assert [q["prompt"] for q in result] == ["First?", "Second?"]
        assert mock_generate.call_count == 4  # one top-up round, then stop
        # The top-up asks only for the shortfall and lists what's already kept.
        top_up_prompt = mock_generate.call_args_list[2].args[1]
        assert "Already in this quiz" in top_up_prompt and "- First?" in top_up_prompt
        assert [c["prompt"] for c in trace["candidates"]] == ["First?", "Rejected?", "Second?"]

        await session.delete(video)
        await session.commit()
