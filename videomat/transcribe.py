"""Transkrypcja mowy: faster-whisper na GPU (CUDA) z timestampami słów.

Wynik (transcript.json):
{
  "language": "pl",
  "segments": [ {"start": 1.2, "end": 4.8, "text": "...", "words": [{"w": "słowo", "start": 1.2, "end": 1.5}, ...]} ]
}
ZASADA: na ekran trafiają tylko prawdziwe słowa lektora. ASR na podkładzie muzycznym myli się —
słowa z niską pewnością (probability < 0.5) są oznaczane w polu "uncertain" do ręcznej weryfikacji.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, ffmpeg

UNCERTAIN_P = 0.5


def transcribe(src: str | Path, out_json: str | Path | None = None, language: str = "pl",
               model_size: str | None = None, device: str = "auto") -> dict:
    from faster_whisper import WhisperModel

    model_size = model_size or config.env("WHISPER_MODEL", "small")
    config.ensure_dirs()
    wav = config.WORK / (Path(src).stem + "_16k.wav")
    ffmpeg.to_wav16k(src, wav)

    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    compute = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute)

    segments, info = model.transcribe(
        str(wav), language=language, word_timestamps=True, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 350, "speech_pad_ms": 120},
        beam_size=5, condition_on_previous_text=False,
    )
    out_segments, uncertain = [], []
    for s in segments:
        words = []
        for w in (s.words or []):
            words.append({"w": w.word.strip(), "start": round(float(w.start), 2), "end": round(float(w.end), 2),
                          "p": round(float(w.probability), 2)})
            if w.probability < UNCERTAIN_P:
                uncertain.append({"w": w.word.strip(), "t": round(float(w.start), 2)})
        out_segments.append({"start": round(float(s.start), 2), "end": round(float(s.end), 2),
                             "text": s.text.strip(), "words": words,
                             "avg_logprob": round(float(getattr(s, "avg_logprob", 0.0) or 0.0), 3),
                             "no_speech_prob": round(float(getattr(s, "no_speech_prob", 0.0) or 0.0), 3)})

    result = {"language": info.language, "model": model_size, "device": device,
              "segments": out_segments, "uncertain": uncertain}
    if out_json:
        Path(out_json).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def words_flat(transcript: dict) -> list[dict]:
    return [w for s in transcript["segments"] for w in s.get("words", [])]
