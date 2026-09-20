"""Lektor TTS z ElevenLabs. Wariant z timestampami zwraca słowa z czasami -> napisy bez ASR.

    tts("Tekst po polsku.", out_mp3="work/vo.mp3", timestamps=True)
    -> {"audio": Path, "words": Path|None, "duration": float}

words JSON: [{"w": "Tekst", "start": 0.0, "end": 0.31}, ...] — ten sam format co transcribe.words_flat,
więc captions.run_captions(..., words_json=...) działa bez zmian.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from . import config, ffmpeg
from .elevenlabs_client import _post

DEFAULT_MODEL = "eleven_multilingual_v2"      # PL; alternatywy: eleven_flash_v2_5 (szybszy), eleven_v3 (max 5000 znaków)


def _alignment_to_words(al: dict) -> list[dict]:
    chars = al["characters"]
    starts = al["character_start_times_seconds"]
    ends = al["character_end_times_seconds"]
    words, cur, s0, e0 = [], "", None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append({"w": cur, "start": round(s0, 2), "end": round(e0, 2)})
            cur, s0, e0 = "", None, None
            continue
        if not cur:
            s0 = s
        cur += ch
        e0 = e
    if cur:
        words.append({"w": cur, "start": round(s0, 2), "end": round(e0, 2)})
    return words


def tts(text: str, out_mp3: str | Path, voice_id: str | None = None, model_id: str = DEFAULT_MODEL,
        timestamps: bool = True, stability: float = 0.5, similarity: float = 0.75, speed: float = 1.0,
        output_format: str = "mp3_44100_128", language_code: str | None = "pl") -> dict:
    # mp3_44100_192 wymaga planu Creator+; 128 kb/s działa na free tier
    voice_id = voice_id or config.env("ELEVENLABS_VOICE_ID")
    if not voice_id:
        raise SystemExit("Podaj --voice albo ustaw ELEVENLABS_VOICE_ID w .env (lista: videomat voices).")
    out_mp3 = Path(out_mp3)
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {"stability": stability, "similarity_boost": similarity, "speed": speed},
    }
    if language_code and model_id != "eleven_v3":
        body["language_code"] = language_code
    params = {"output_format": output_format}
    words_path = None
    if timestamps:
        r = _post(f"/v1/text-to-speech/{voice_id}/with-timestamps", body, params=params)
        data = r.json()
        out_mp3.write_bytes(base64.b64decode(data["audio_base64"]))
        al = data.get("normalized_alignment") or data.get("alignment")
        if al:
            words = _alignment_to_words(al)
            words_path = out_mp3.with_suffix(".words.json")
            words_path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        r = _post(f"/v1/text-to-speech/{voice_id}", body, params=params)
        out_mp3.write_bytes(r.content)
    return {"audio": out_mp3, "words": words_path, "duration": ffmpeg.duration(out_mp3)}
