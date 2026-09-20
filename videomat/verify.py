"""Weryfikacja renderu: wyciąga klatki w środku czasu trwania napisów/keywordów do out/verify/.
Klatki trzeba OBEJRZEĆ (Claude Code: Read na PNG) przed oddaniem — diakrytyki, safe zones, overflow.
"""
from __future__ import annotations

from pathlib import Path

from . import config, ffmpeg


def frames_for_spec(video: str | Path, spec: dict, max_frames: int = 6, tag: str = "") -> list[Path]:
    config.ensure_dirs()
    events = spec.get("captions", []) + spec.get("keywords", [])
    if not events:
        return []
    # równomiernie wybrane zdarzenia; próbkujemy w środku trwania (nie w pierwszych 100 ms animacji)
    step = max(1, len(events) // max_frames)
    picks = events[::step][:max_frames]
    out = []
    stem = Path(video).stem + (f"_{tag}" if tag else "")
    for i, e in enumerate(picks):
        t = e["start"] + max(0.25, (e["end"] - e["start"]) * 0.5)
        png = config.OUT / "verify" / f"{stem}_{i + 1}_{t:.2f}s.png"
        ffmpeg.extract_frame(video, t, png)
        out.append(png)
    return out


def frames_at(video: str | Path, times: list[float], tag: str = "") -> list[Path]:
    config.ensure_dirs()
    stem = Path(video).stem + (f"_{tag}" if tag else "")
    out = []
    for i, t in enumerate(times):
        png = config.OUT / "verify" / f"{stem}_{i + 1}_{t:.2f}s.png"
        ffmpeg.extract_frame(video, t, png)
        out.append(png)
    return out
