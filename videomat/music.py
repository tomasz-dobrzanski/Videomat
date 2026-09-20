"""Muzyka i efekty dźwiękowe z ElevenLabs + normalizacja głośności.

    music("energetic tech intro, no vocals", "work/music.mp3", length_s=30, instrumental=True)
    sfx("short digital whoosh", "work/whoosh.mp3", duration_s=1.2)
    loudnorm("in.mp3", "out.wav", lufs=-14)
"""
from __future__ import annotations

from pathlib import Path

from . import ffmpeg
from .elevenlabs_client import _post

MUSIC_MODELS = ("music_v1", "music_v2", "music_v2_5")


def music(prompt: str, out_path: str | Path, length_s: float | None = 30, instrumental: bool = True,
          model_id: str = "music_v2", output_format: str = "mp3_44100_192", seed: int | None = None,
          composition_plan: dict | None = None) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body: dict = {"model_id": model_id, "force_instrumental": instrumental, "output_format": output_format}
    if composition_plan:
        body["composition_plan"] = composition_plan
    else:
        body["prompt"] = prompt
        if length_s:
            body["music_length_ms"] = int(max(3, min(600, length_s)) * 1000)
    if seed is not None:
        body["seed"] = seed
    r = _post("/v1/music", body, timeout=600)
    out_path.write_bytes(r.content)
    return out_path


def sfx(text: str, out_path: str | Path, duration_s: float | None = None, prompt_influence: float = 0.3,
        loop: bool = False, output_format: str = "mp3_44100_128") -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body: dict = {"text": text, "prompt_influence": prompt_influence, "loop": loop}
    if duration_s:
        body["duration_seconds"] = max(0.5, min(30.0, duration_s))
    r = _post("/v1/sound-generation", body, params={"output_format": output_format}, timeout=180)
    out_path.write_bytes(r.content)
    return out_path


def loudnorm(src: str | Path, out_path: str | Path, lufs: float = -14.0, tp: float = -1.5) -> Path:
    ffmpeg.run(["-i", str(src), "-af", f"loudnorm=I={lufs}:TP={tp}:LRA=11", "-ar", "48000", str(out_path)])
    return Path(out_path)


def measure_lufs(src: str | Path) -> float | None:
    import re
    import subprocess
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.findall(r"I:\s*(-?[0-9.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None
