import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.generation.flashcards import generate_flashcards
from app.models.flashcard import Flashcard
from app.models.flashcard_deck import FlashcardDeck
from app.models.video import Video
from app.schemas.flashcard import FlashcardConfig, FlashcardDeckListItem, FlashcardDeckOut

router = APIRouter()


def _default_title(config: FlashcardConfig) -> str:
    scope_label = "whole video" if config.scope == "whole_video" else "selected topics"
    return f"Flashcards ({scope_label})"


@router.post("/videos/{video_id}/flashcard-decks", response_model=FlashcardDeckOut, status_code=201)
async def create_flashcard_deck(
    video_id: uuid.UUID, payload: FlashcardConfig, db: AsyncSession = Depends(get_db)
) -> FlashcardDeck:
    video = await db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    cards = await generate_flashcards(
        db,
        video_id,
        count=payload.count,
        scope=payload.scope,
        segment_ids=payload.segment_ids,
        difficulty=payload.difficulty,
        style=payload.style,
    )
    if not cards:
        raise HTTPException(
            status_code=422, detail="Could not generate any flashcards for this configuration."
        )

    deck = FlashcardDeck(
        video_id=video_id,
        title=payload.title or _default_title(payload),
        config=payload.model_dump(mode="json"),
    )
    deck.cards = [Flashcard(**card) for card in cards]
    db.add(deck)
    await db.commit()
    await db.refresh(deck)
    return deck


@router.get("/videos/{video_id}/flashcard-decks", response_model=list[FlashcardDeckListItem])
async def list_flashcard_decks(
    video_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[FlashcardDeckListItem]:
    if await db.get(Video, video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    result = await db.execute(
        select(FlashcardDeck)
        .where(FlashcardDeck.video_id == video_id)
        .order_by(FlashcardDeck.created_at.desc())
    )
    decks = result.scalars().all()
    return [
        FlashcardDeckListItem(
            id=deck.id,
            video_id=deck.video_id,
            title=deck.title,
            config=deck.config,
            created_at=deck.created_at,
            card_count=len(deck.cards),
        )
        for deck in decks
    ]


@router.get("/flashcard-decks/{deck_id}", response_model=FlashcardDeckOut)
async def get_flashcard_deck(
    deck_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> FlashcardDeck:
    deck = await db.get(FlashcardDeck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Flashcard deck not found.")
    return deck


@router.delete("/flashcard-decks/{deck_id}", status_code=204)
async def delete_flashcard_deck(deck_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    deck = await db.get(FlashcardDeck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Flashcard deck not found.")
    await db.delete(deck)
    await db.commit()
