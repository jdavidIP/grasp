import asyncio
import re
import statistics
from dataclasses import dataclass, field

from app.config import settings
from app.generation import llm
from app.prompts.segment_label import SYSTEM_PROMPT, build_user_prompt

SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]?\s*$")
SILENCE_GAP_SECONDS = 0.6
# Auto-generated captions have no punctuation and almost no gaps, so without a cap
# one "sentence" swallows minutes of speech (issue #15). ~2x the typical unit length
# on punctuated captions (~8s), so punctuated transcripts are essentially unaffected.
MAX_UNIT_SECONDS = 15.0
MIN_UNITS_FOR_BREAKPOINTS = 5


@dataclass
class Unit:
    start: float
    end: float
    text: str


@dataclass
class SegmentDraft:
    units: list[Unit] = field(default_factory=list)

    @property
    def start(self) -> float:
        return self.units[0].start

    @property
    def end(self) -> float:
        return self.units[-1].end

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def text(self) -> str:
        return " ".join(unit.text for unit in self.units)


def _group_cues_into_units(cues: list[dict]) -> list[Unit]:
    """Groups fragmentary transcript cues into sentence-ish units, splitting on
    sentence-ending punctuation, a gap in speech, or MAX_UNIT_SECONDS of speech —
    whichever comes first."""
    units: list[Unit] = []
    buffer: list[str] = []
    buffer_start: float | None = None
    buffer_end: float | None = None

    for cue in cues:
        text = cue["text"].strip()
        if not text:
            continue

        gap = cue["start"] - buffer_end if buffer_end is not None else 0
        if buffer and gap > SILENCE_GAP_SECONDS:
            units.append(Unit(buffer_start, buffer_end, " ".join(buffer)))
            buffer, buffer_start = [], None

        if buffer_start is None:
            buffer_start = cue["start"]
        buffer.append(text)
        buffer_end = cue["end"]

        if SENTENCE_END_RE.search(text) or buffer_end - buffer_start >= MAX_UNIT_SECONDS:
            units.append(Unit(buffer_start, buffer_end, " ".join(buffer)))
            buffer, buffer_start = [], None

    if buffer:
        units.append(Unit(buffer_start, buffer_end, " ".join(buffer)))

    return units


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return 1 - dot / (norm_a * norm_b)


def _find_breakpoints(embeddings: list[list[float]]) -> list[int]:
    """Returns unit indices where a new segment should start, picked from cosine
    distance between consecutive units at the configured percentile — capped to the
    strongest breaks so the video never exceeds max_segments_per_video."""
    if len(embeddings) < MIN_UNITS_FOR_BREAKPOINTS:
        return []

    distances = [
        _cosine_distance(embeddings[i], embeddings[i + 1]) for i in range(len(embeddings) - 1)
    ]
    percentile_index = min(max(int(settings.segmentation_breakpoint_percentile) - 1, 0), 97)
    threshold = statistics.quantiles(distances, n=100, method="inclusive")[percentile_index]

    candidates = [i + 1 for i, d in enumerate(distances) if d > threshold]
    max_breakpoints = max(settings.max_segments_per_video - 1, 0)
    if len(candidates) > max_breakpoints:
        candidates = sorted(candidates, key=lambda i: distances[i - 1], reverse=True)[
            :max_breakpoints
        ]
        candidates.sort()
    return candidates


def _build_segments(units: list[Unit], breakpoints: list[int]) -> list[SegmentDraft]:
    breakpoints_set = set(breakpoints)
    segments: list[SegmentDraft] = []
    current = SegmentDraft()
    for i, unit in enumerate(units):
        if i in breakpoints_set and current.units:
            segments.append(current)
            current = SegmentDraft()
        current.units.append(unit)
    if current.units:
        segments.append(current)
    return segments


def _merge_short_segments(segments: list[SegmentDraft]) -> list[SegmentDraft]:
    """Merges segments under the minimum duration into the preceding one, and a
    too-short leading segment into the one after it.

    The minimum scales with video length: a fixed floor keeps short videos from
    fragmenting, while the fraction keeps a 3-hour podcast's topic list at a size a
    person can pick from, without folding a tutorial's genuine 1-minute topics away.
    """
    if len(segments) <= 1:
        return segments

    total_duration = segments[-1].end - segments[0].start
    min_duration = max(
        settings.min_segment_duration_seconds,
        total_duration * settings.min_segment_duration_fraction,
    )

    merged: list[SegmentDraft] = []
    for segment in segments:
        if merged and segment.duration < min_duration:
            merged[-1].units.extend(segment.units)
        else:
            merged.append(segment)

    if len(merged) > 1 and merged[0].duration < min_duration:
        merged[1].units = merged[0].units + merged[1].units
        merged = merged[1:]

    return merged


async def segment_transcript(cues: list[dict]) -> list[dict]:
    """Turns raw transcript cues into labelled topic segments, ready for
    TranscriptSegment rows: order_index, label, summary, start_time, end_time."""
    units = _group_cues_into_units(cues)
    if not units:
        return []

    embeddings = await llm.embed_texts([unit.text for unit in units])
    breakpoints = _find_breakpoints(embeddings)
    segments = _merge_short_segments(_build_segments(units, breakpoints))

    labels = await asyncio.gather(
        *(llm.generate_json(SYSTEM_PROMPT, build_user_prompt(segment.text)) for segment in segments)
    )

    return [
        {
            "order_index": i,
            "label": label["label"],
            "summary": label["summary"],
            "start_time": segment.start,
            "end_time": segment.end,
        }
        for i, (segment, label) in enumerate(zip(segments, labels, strict=True))
    ]
