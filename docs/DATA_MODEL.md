# Data model

Single PostgreSQL 16 database with the `pgvector` extension. No second datastore.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Tables

### videos

The library. One row per added video.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| youtube_id | text unique not null | |
| title | text not null | |
| channel | text | |
| duration_seconds | int | |
| thumbnail_url | text | |
| transcript_source | text | `captions` or `whisper` |
| transcript | jsonb | list of `{start, end, text}` cues; raw transcript between fetch and Phase 3 segmentation |
| status | text not null | `pending`, `processing`, `ready`, `failed` |
| error_message | text | populated when `failed` |
| created_at | timestamptz not null default now() | |

Deleting a video cascades to everything below.

### transcript_segments

Topic segments from the segmentation step. These populate the topic checkboxes in the generation forms.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| video_id | uuid FK → videos on delete cascade | |
| order_index | int not null | |
| label | text not null | short topic name |
| summary | text not null | 1–2 sentences |
| start_time | numeric not null | seconds |
| end_time | numeric not null | seconds |

Index: `(video_id, order_index)`.

### transcript_chunks

Retrievable units. Always nested inside one segment.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| video_id | uuid FK → videos on delete cascade | |
| segment_id | uuid FK → transcript_segments on delete cascade | |
| text | text not null | |
| start_time | numeric not null | |
| end_time | numeric not null | |
| token_count | int | |
| embedding | vector(1536) | `text-embedding-3-small` |
| tsv | tsvector generated | for hybrid search |

Indexes:
```sql
CREATE INDEX ON transcript_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON transcript_chunks (video_id);
CREATE INDEX ON transcript_chunks (segment_id);
CREATE INDEX ON transcript_chunks USING gin (tsv);
```

Use HNSW rather than IVFFlat — it needs no training step and performs better at this scale.

### chat_messages

Per-video conversation history.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| video_id | uuid FK → videos on delete cascade | |
| role | text not null | `user` or `assistant` |
| content | text not null | |
| cited_chunk_ids | uuid[] | sources for assistant messages |
| created_at | timestamptz not null default now() | |

### flashcard_decks

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| video_id | uuid FK → videos on delete cascade | |
| title | text not null | |
| config | jsonb not null | the generation request that produced it |
| created_at | timestamptz not null default now() | |

Storing `config` as jsonb means you can show the user how a deck was generated and regenerate with tweaks, without a migration every time you add a parameter.

### flashcards

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| deck_id | uuid FK → flashcard_decks on delete cascade | |
| front | text not null | |
| back | text not null | |
| segment_id | uuid FK → transcript_segments on delete set null | |
| source_start_time | numeric | for the jump-to-timestamp link |
| difficulty | text | `easy`, `medium`, `hard` |
| order_index | int not null | |
| note | text | set when front/back state the corrected fact for a speaker slip the transcript contains (see below) |

**Speaker slips.** The transcript is the source of truth, but speakers misspeak and captions mishear. If front/back would otherwise repeat an apparent slip (wrong name, date, number) as fact, generation either avoids that card or states the corrected, intended fact and names the slip in `note` — never a silent correction. Quiz questions have no `note` column; the same information goes into their existing `explanation`, which already stores and reveals post-submit. See [#18](https://github.com/jdavidIP/grasp/issues/18).

### quizzes

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| video_id | uuid FK → videos on delete cascade | |
| title | text not null | |
| config | jsonb not null | |
| created_at | timestamptz not null default now() | |

### quiz_questions

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| quiz_id | uuid FK → quizzes on delete cascade | |
| order_index | int not null | |
| question_type | text not null | `multiple_choice`, `multi_select`, `true_false` |
| prompt | text not null | |
| explanation | text not null | why the correct answer is correct |
| segment_id | uuid FK → transcript_segments on delete set null | |
| source_start_time | numeric | |
| difficulty | text | |

### quiz_options

Options for every question type. `is_correct` is the answer key, fixed when the question is generated; grading never calls an LLM.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| question_id | uuid FK → quiz_questions on delete cascade | |
| text | text not null | |
| is_correct | bool not null default false | |
| order_index | int not null | |

Correct-option counts are enforced in the service layer at generation time, not by a constraint (a per-type count rule is awkward to express in SQL):

| `question_type` | Options | Correct options |
|---|---|---|
| `multiple_choice` | 3–5 | exactly 1 |
| `multi_select` | 3–5 | at least 1, and at least 1 incorrect |
| `true_false` | 2 (`True`, `False`) | exactly 1 |

### quiz_attempts and quiz_answers

Attempt history, so a user can retake and compare.

**quiz_attempts**: `id`, `quiz_id` FK, `score` numeric, `started_at`, `completed_at`.

**quiz_answers**: `id`, `attempt_id` FK, `question_id` FK, `selected_option_ids` uuid[] (empty when the question was skipped), `is_correct` bool.

An answer is correct iff the selected set equals the set of options with `is_correct = true` — all-or-nothing, no partial credit. `score` is the fraction of questions answered correctly.

**Tradeoff — `uuid[]` vs. a join table for `selected_option_ids`.** A join table (`quiz_answer_options`) would keep foreign-key integrity, but nothing queries by selected option — answers are only ever read back per attempt — so it costs a table and a join for no query we run. The array loses the FK, so the service layer checks that every submitted option id belongs to the question before grading. Revisit if we ever want per-option statistics ("which distractor is chosen most").

## Why this shape

The entity graph is genuinely relational — a video has segments, segments have chunks, decks have cards, quizzes have questions which have options which get answered in attempts. Foreign keys and joins handle this natively; a document store would either duplicate data or push joins into application code.

Keeping embeddings in the same database means retrieval can filter relationally in one query:

```sql
SELECT c.id, c.text, c.start_time
FROM transcript_chunks c
WHERE c.video_id = $1
  AND c.segment_id = ANY($2)          -- only the topics the user selected
ORDER BY c.embedding <=> $3
LIMIT 8;
```

That combination — vector similarity plus a relational filter on user-selected topics — is exactly what the flashcard and quiz config forms need, and it is one query rather than a round trip between two systems.
