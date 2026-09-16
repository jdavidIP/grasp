# CLAUDE.md

Project guide for Claude Code. Read this before making changes. Detailed specs live in `docs/`.

## What this project is

A study companion built on a RAG pipeline over video transcripts. A user adds YouTube videos to a persistent library. Inside each video they can:

1. **Chat** — ask questions about the video, get answers grounded in the transcript with clickable timestamps.
2. **Flashcards** — configure and generate decks (count, topics, etc.), which are saved and reviewable.
3. **Quizzes** — configure and generate quizzes (count, question types, topics, difficulty), which are saved with attempt history.

The portfolio thesis is the **retrieval and generation quality**, not the surrounding app. Everything else is deliberately minimal.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.11+), SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Frontend | React + TypeScript + Vite |
| Database | PostgreSQL 16 with the `pgvector` extension |
| LLM | OpenAI — `gpt-4o-mini` for generation, `text-embedding-3-small` for embeddings |
| Transcripts | `youtube-transcript-api` first; `yt-dlp` + Whisper API as fallback |
| Local dev | Docker Compose (`api`, `db`, `web`) |

Do not add a separate vector database. pgvector in the same Postgres instance is the deliberate choice — it lets retrieval and relational filters live in one SQL query.

## Repo layout

```
.
├── docker-compose.yml
├── CLAUDE.md
├── docs/
│   ├── ARCHITECTURE.md      # pipelines in detail
│   ├── DATA_MODEL.md        # schema + pgvector setup
│   ├── API.md               # endpoint contracts
│   └── ROADMAP.md           # build order
├── api/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── routers/         # videos, chat, flashcards, quizzes
│   │   ├── ingestion/       # fetch, transcribe, segment, chunk, embed
│   │   ├── retrieval/       # search + reranking
│   │   ├── generation/      # answer, flashcard, quiz generators
│   │   ├── prompts/         # prompt templates as separate files
│   │   └── eval/            # retrieval + faithfulness evaluation
│   ├── alembic/
│   └── tests/
└── web/
    └── src/
        ├── api/             # typed fetch client
        ├── components/
        ├── pages/
        └── types/
```

## Commands

```bash
docker compose up --build          # run everything
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "message"
docker compose exec api pytest
docker compose exec api ruff check . && docker compose exec api ruff format .
docker compose exec web npm run typecheck
```

## Conventions

**Backend**
- Type hints everywhere. Pydantic v2 models for every request and response body.
- Routers stay thin — they validate input, call a service function, return a response. Business logic lives in `ingestion/`, `retrieval/`, `generation/`.
- Prompts live in `app/prompts/` as separate `.py` or `.txt` files, never inline in business logic. They are the most iterated-on part of the codebase and need to be easy to find and diff.
- Every LLM call goes through a single wrapper in `app/generation/llm.py` that handles retries, timeouts, and token logging. No direct `openai` client calls elsewhere.
- Async endpoints. Ingestion runs as a FastAPI `BackgroundTask`; do not block the request.
- Never invent transcript content. If retrieval returns nothing relevant, the response says so explicitly.

**Frontend**
- TypeScript strict mode. No `any`.
- Types for API payloads live in `web/src/types/` and mirror the Pydantic schemas exactly.
- Server state via TanStack Query. No Redux.
- Keep components presentational where possible; data fetching lives in hooks.

**General**
- Small, focused commits. Conventional commit messages.
- When a design decision has a tradeoff, write it down in `docs/` rather than only in a code comment.

## Scope guardrails

These are intentionally out of scope. Do not build them unless explicitly asked:

- Authentication, user accounts, multi-user support. Assume a single local user.
- Spaced-repetition scheduling algorithms (SM-2 etc.).
- A custom video player. Use a plain YouTube iframe embed.
- Deployment infrastructure, CI/CD, monitoring.
- Sharing, collaboration, or export features.
- Any second datastore (Redis, Elasticsearch, a vector DB).

If a task seems to require one of these, stop and ask rather than building it.

## Where the effort should go

In rough order of how much they matter to this project:

1. Topic segmentation quality — it determines both retrieval and the topic list users pick from.
2. Prompt design for flashcard and quiz generation, especially plausible-but-wrong distractors.
3. Grounding and citation accuracy — every answer, card, and question traces back to a timestamp.
4. Evaluation — retrieval metrics and faithfulness checks on generated content.
5. Everything else.

## Key reading

- `docs/ARCHITECTURE.md` — how ingestion, retrieval, and the two generation pipelines work.
- `docs/DATA_MODEL.md` — tables, relationships, pgvector index config.
- `docs/API.md` — endpoint contracts, including generation config payloads.
- `docs/ROADMAP.md` — suggested build order in phases.
