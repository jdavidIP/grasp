# API contracts

All routes prefixed `/api`. No auth — single local user.

## Library

### `GET /videos`
Returns the library. Each item: `id`, `youtube_id`, `title`, `channel`, `duration_seconds`, `thumbnail_url`, `status`, `error_message`, `created_at`.

### `POST /videos`
```json
{ "url": "https://www.youtube.com/watch?v=..." }
```
Creates the row with `status: "pending"`, kicks off ingestion as a background task, returns `201` with the video immediately. The client polls `GET /videos/{id}` until `status` is `ready` or `failed`.

Returns `409` if the video is already in the library.

### `GET /videos/{id}`
Full detail including `segments` (id, label, summary, start_time, end_time) once ready, and `error_message` if failed.

### `DELETE /videos/{id}`
Cascades to segments, chunks, chat, decks, quizzes, attempts. Returns `204`.

### `POST /videos/{id}/reprocess`
Re-runs segmentation and embedding on the stored transcript without re-fetching. Useful while tuning segmentation parameters. Leaves decks and quizzes intact but nulls their `segment_id` references.

---

## Chat

### `GET /videos/{id}/chat`
Message history, oldest first.

### `POST /videos/{id}/chat`
```json
{ "message": "What did they say about attention heads?" }
```

Response:
```json
{
  "answer": "They describe attention heads as...",
  "sources": [
    {
      "chunk_id": "…",
      "segment_label": "Transformer internals",
      "start_time": 842.5,
      "end_time": 901.0,
      "text": "…"
    }
  ],
  "grounded": true
}
```

`grounded` is `false` when retrieval found nothing relevant and the model declined to answer. The UI should render that case differently — it is a feature, not an error.

Broad questions ("summarize this video," "what's this about") are answered from segment summaries instead of individual chunks — see `docs/ARCHITECTURE.md`'s broad-vs-specific split. Their `sources` entries have `chunk_id: null` and cite a whole segment (`start_time`/`end_time` span the segment, `text` is its summary) rather than one chunk.

### `DELETE /videos/{id}/chat`
Clears history.

---

## Flashcards

### `POST /videos/{id}/flashcard-decks`

Config payload from the form:
```json
{
  "count": 15,
  "scope": "topics",
  "segment_ids": ["…", "…"],
  "difficulty": "mixed",
  "style": "definition",
  "title": "Attention and embeddings"
}
```

| Field | Values | Notes |
|---|---|---|
| `count` | 5–50 | |
| `scope` | `whole_video`, `topics` | `segment_ids` required when `topics` |
| `segment_ids` | uuid[] | ignored when scope is `whole_video` |
| `difficulty` | `easy`, `medium`, `hard`, `mixed` | |
| `style` | `definition`, `concept`, `detail`, `mixed` | shapes the prompt |
| `title` | string, optional | auto-generated if omitted |

Synchronous is acceptable here (a few seconds). If generation exceeds ~20s for whole-video requests on long content, switch to the same background-task-plus-polling pattern as ingestion.

Response: the created deck with its cards, each carrying `front`, `back`, `segment_id`, `source_start_time`, `difficulty`, `note` (null unless the card corrects a speaker slip in the transcript — see `DATA_MODEL.md`).

`422` if the generation + validation pipeline (see ARCHITECTURE.md) yields zero cards — e.g. the model's output failed every grounding check. No deck is persisted in that case.

### `GET /videos/{id}/flashcard-decks`
Decks for a video, with card counts.

### `GET /flashcard-decks/{id}`
Full deck with cards.

### `DELETE /flashcard-decks/{id}`

---

## Quizzes

### `POST /videos/{id}/quizzes`

```json
{
  "count": 10,
  "scope": "topics",
  "segment_ids": ["…"],
  "question_types": ["multiple_choice", "multi_select", "true_false"],
  "options_per_question": 4,
  "difficulty": "mixed",
  "title": "Mid-episode check"
}
```

| Field | Values | Notes |
|---|---|---|
| `count` | 3–30 | |
| `scope` | `whole_video`, `topics` | |
| `segment_ids` | uuid[] | required when scope is `topics` |
| `question_types` | non-empty subset of `multiple_choice` (one correct option), `multi_select` (select all that apply), `true_false` | more than one means assorted |
| `options_per_question` | 3–5, default 4 | `multiple_choice` and `multi_select` only; `true_false` always has two options |
| `difficulty` | `easy`, `medium`, `hard`, `mixed` | |

Response: the quiz with questions and options. **Never return `is_correct` or `explanation` from this endpoint or from `GET /quizzes/{id}`** — the client would leak the answers. The answer key is fixed when the quiz is generated and is revealed only through the submit response.

`422` if the generation + validation pipeline yields zero questions. No quiz is persisted in that case.

### `GET /videos/{id}/quizzes`
Quizzes for a video, each with `question_count` and `best_score` (fraction 0–1, `null` if never attempted).

### `GET /quizzes/{id}`
Questions and options, answers withheld.

### `POST /quizzes/{id}/attempts`
```json
{
  "answers": [
    { "question_id": "…", "selected_option_ids": ["…"] },
    { "question_id": "…", "selected_option_ids": ["…", "…"] }
  ]
}
```

One entry per answered question; a question left out counts as skipped (incorrect). `selected_option_ids` has exactly one id for `multiple_choice` and `true_false`, any number for `multi_select`.

`422` (and nothing is persisted) if a `question_id` is not in the quiz or appears twice, if a selected option does not belong to that question, if an option id is repeated, or if a single-answer question has more than one selection.

Response:
```json
{
  "attempt_id": "…",
  "score": 0.8,
  "results": [
    {
      "question_id": "…",
      "is_correct": true,
      "selected_option_ids": ["…"],
      "correct_option_ids": ["…"],
      "explanation": "…",
      "segment_id": "…",
      "source_start_time": 412.0
    }
  ]
}
```

Grading is deterministic and makes no LLM call: a question is correct only if the selected set of options exactly equals the set marked correct at generation time (all-or-nothing, no partial credit). `score` is correct questions divided by all questions in the quiz, skipped ones included.

### `GET /quizzes/{id}/attempts`
Attempt history for comparison, newest first: `id`, `score`, `correct_count`, `question_count`, `started_at`, `completed_at`.

### `GET /quizzes/{id}/attempts/{attempt_id}`
Per-question detail for one past attempt, in the same shape as the submit response (`attempt_id`, `score`, `results` with the selected and correct options, explanation, and source timestamp). `404` if the attempt does not belong to that quiz.

### `DELETE /quizzes/{id}`

---

## Errors

Consistent shape:
```json
{ "detail": "Captions are disabled for this video and audio transcription failed." }
```

Use real status codes: `400` bad input, `404` missing, `409` duplicate video, `422` validation, `502` upstream LLM or YouTube failure. Ingestion failures do not return an error status — they land in `videos.status = "failed"` with `error_message`, since the request already returned.
