# Grasp web

The React + TypeScript (Vite) frontend for Grasp. See the [root README](../README.md) for what the project is and how to run it; the app is normally run through Docker Compose with the API and database.

## Layout

```
src/
  pages/        LibraryPage, VideoDetailPage (one per route)
  components/   grouped by feature:
    chat/ flashcards/ quizzes/   the three workspace tabs
    library/                     adding and listing videos
    video/                       player, topic list, workspace tabs
    layout/                      header, toasts
    ui/                          shared form pieces and decoration
  hooks/        TanStack Query hooks; data fetching lives here, not in components
  api/          typed fetch client, one file per resource
  types/        API payload types, mirroring the backend's Pydantic schemas
  lib/          formatting, time and theme helpers
  styles/       design tokens (industry.css)
  test/         test setup and render helpers
```

Tests sit next to the file they test (`QuizTake.test.tsx` beside `QuizTake.tsx`).

## Scripts

Run inside the container, e.g. `docker compose exec web npm test`:

| Script | |
|---|---|
| `npm run dev` | Vite dev server (the container runs this) |
| `npm test` | Vitest + React Testing Library |
| `npm run typecheck` | `tsc` in strict mode |
| `npm run lint` | oxlint |
| `npm run build` | type-check and production build |

## Configuration

`VITE_API_URL` points the client at the API (default `http://localhost:8000/api`, see `.env.example`).
