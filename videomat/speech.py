"""Lektor: generowanie linii przez ElevenLabs, korekta tempa i czasy słów do napisów karaoke.

Pliki trzymane są w katalogu roboczym projektu:
    <work>/<id>.mp3          — surowy wynik TTS
    <work>/<id>_fast.wav     — po przycięciu ciszy i korekcie tempa (to jest plik używany w montażu)
    <work>/<id>_words.json   — czasy słów (whisper na pliku TTS), tekst z filmu, nie z ASR

Tekst na ekranie zawsze pochodzi ze skryptu filmu. Whisper służy wyłącznie do czasów; gdy liczba
rozpoznanych słów nie zgadza się ze skryptem, czasy rozkładane są proporcjonalnie do długości słów.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, ffmpeg
from .timeline import Film, NarrationLine

_WHISPER = None


class SpeechUnavailable(RuntimeError):
    """Brak klucza albo uprawnień do syntezy — film renderuje się z długościami zastępczymi."""


def _fast(src: Path, tempo: float) -> Path:
    """Przycięcie ciszy na końcach i korekta tempa bez zmiany wysokości głosu."""
    out = src.with_name(src.stem + "_fast.wav")
    if out.exists():
        return out
    chain = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
             "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse")
    if abs(tempo - 1.0) > 0.001:
        chain += f",atempo={tempo}"
    ffmpeg.run(["-i", str(src), "-af", chain, "-ar", "48000", "-ac", "2", str(out)])
    return out


def pick_voice(film: Film, work: Path, probe: NarrationLine) -> str:
    """Pierwszy głos z listy, który konto faktycznie obsłuży. Wynik zapamiętany w voice_used.txt."""
    used = work / "voice_used.txt"
    if used.exists() and (work / f"{probe.id}.mp3").exists():
        return used.read_text(encoding="utf-8").strip()
    voice = film.assets.voice
    if voice.voice_id:
        order = [voice.voice_id] + list(voice.voice_order)
    else:
        order = list(voice.voice_order) or [config.env("ELEVENLABS_VOICE_ID") or ""]

    from .elevenlabs_client import list_voices
    from .tts import tts

    available = list_voices()
    candidates: list[tuple[str, str]] = []
    for name in order:
        if not name:
            continue
        for v in available:
            same = name == v["voice_id"] or name.lower() in (v["name"] or "").lower()
            if same and v["voice_id"] not in [c[0] for c in candidates]:
                candidates.append((v["voice_id"], v["name"] or v["voice_id"]))
    if not candidates:
        raise SpeechUnavailable("Żaden z podanych głosów nie istnieje na koncie.")

    problems = []
    for vid, vname in candidates:
        target = work / f"{probe.id}.mp3"
        try:
            if target.exists():
                target.unlink()
            tts(probe.text, target, voice_id=vid, model_id=voice.model, timestamps=False,
                stability=voice.stability, similarity=voice.similarity, speed=voice.speed)
            used.write_text(vid, encoding="utf-8")
            return vid
        except Exception as exc:  # 402 = głos spoza planu; próbujemy następny
            problems.append(f"{vname}: {str(exc)[:90]}")
    raise SpeechUnavailable("Żaden głos nie zadziałał — " + "; ".join(problems))


def ensure_lines(film: Film, work: Path, only: list[str] | None = None,
                 regenerate: bool = False) -> dict[str, Path]:
    """Dogrywa brakujące linie lektora. Zwraca id -> gotowy plik audio (po korekcie tempa)."""
    work.mkdir(parents=True, exist_ok=True)
    lines = [n for n in film.narration if only is None or n.id in only]
    if not lines:
        return {}
    if not config.env("ELEVENLABS_API_KEY"):
        raise SpeechUnavailable("Brak ELEVENLABS_API_KEY w .env.")

    from .tts import tts

    voice = film.assets.voice
    missing = [n for n in lines if regenerate or not (work / f"{n.id}.mp3").exists()]
    vid = None
    if missing:
        vid = pick_voice(film, work, missing[0])
    out: dict[str, Path] = {}
    for line in lines:
        raw = work / f"{line.id}.mp3"
        if regenerate and raw.exists():
            raw.unlink()
            for stale in (raw.with_name(f"{line.id}_fast.wav"), raw.with_name(f"{line.id}_words.json")):
                stale.unlink(missing_ok=True)
        if not raw.exists():
            tts(line.text, raw, voice_id=vid or pick_voice(film, work, line), model_id=voice.model,
                timestamps=False, stability=voice.stability, similarity=voice.similarity, speed=voice.speed)
        out[line.id] = _fast(raw, voice.tempo)
    return out


def audio_files(film: Film, work: Path) -> dict[str, Path]:
    """Gotowe pliki lektora, bez sięgania do sieci."""
    found = {}
    for line in film.narration:
        fast = work / f"{line.id}_fast.wav"
        raw = work / f"{line.id}.mp3"
        if fast.exists():
            found[line.id] = fast
        elif raw.exists():
            found[line.id] = _fast(raw, film.assets.voice.tempo)
    return found


def durations(film: Film, work: Path) -> dict[str, float]:
    """Długości linii lektora: z plików, a gdzie ich nie ma — wartości zastępcze z filmu."""
    files = audio_files(film, work)
    return {n.id: (ffmpeg.duration(files[n.id]) if n.id in files else n.fallback) for n in film.narration}


def align(line_id: str, text: str, wav: Path, work: Path, model_size: str = "medium") -> list[dict]:
    """Czasy słów lektora. Tekst zawsze ze skryptu; whisper daje wyłącznie momenty."""
    global _WHISPER
    cache = work / f"{line_id}_words.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    script = text.split()
    heard: list[tuple[float, float]] = []
    try:
        from faster_whisper import WhisperModel
        if _WHISPER is None:
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"
            _WHISPER = WhisperModel(model_size, device=device,
                                    compute_type="float16" if device == "cuda" else "int8")
        segments, _ = _WHISPER.transcribe(str(wav), language="pl", word_timestamps=True,
                                          vad_filter=False, beam_size=5)
        heard = [(float(w.start), float(w.end)) for s in segments for w in (s.words or [])]
    except Exception:
        heard = []

    if heard and len(heard) == len(script):
        words = [{"w": script[i], "start": round(heard[i][0], 2), "end": round(heard[i][1], 2)}
                 for i in range(len(script))]
    else:
        t0 = heard[0][0] if heard else 0.0
        t1 = heard[-1][1] if heard else ffmpeg.duration(wav)
        total = sum(len(s) for s in script) or 1
        words, t = [], t0
        for s in script:
            d = (t1 - t0) * len(s) / total
            words.append({"w": s, "start": round(t, 2), "end": round(t + d, 2)})
            t += d
    cache.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words
