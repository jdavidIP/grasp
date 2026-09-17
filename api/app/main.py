from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, flashcards, videos

app = FastAPI(title="Grasp")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(flashcards.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
