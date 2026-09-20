"""Stenogram na żywo: mikrofon albo transmisja, tekst pojawiający się w trakcie mówienia.

    session = LiveSession(on_update=print)
    session.start()          # ...mówisz...
    session.stop()           # zwraca komplet wypowiedzi

Materiał leci do bufora, a granice zdań wyznacza cisza. Fragment zamknięty ciszą jest
transkrybowany i publikowany jako gotowy; w trakcie mówienia co sekundę idzie wersja robocza,
wyraźnie oznaczona jako niepewna. Diaryzacja działa dopiero na całości — pyannote potrzebuje
szerszego kontekstu, niż mamy na żywo, a zgadywanie mówcy w locie prowadziłoby do podpisywania
wypowiedzi niewłaściwej osobie.

Źródła: `mic` (sounddevice) albo dowolny adres, który przyjmuje ffmpeg — w tym transmisja
z YouTube (adres strumienia wyciąga yt-dlp).
"""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import config

RATE = 16000
BLOCK = 1600                     # 0,1 s
SILENCE_RMS = 0.006              # próg ciszy dla znormalizowanego sygnału
SILENCE_HOLD = 0.7               # tyle ciszy zamyka wypowiedź
MAX_UTTERANCE = 14.0             # awaryjne domknięcie, gdy ktoś mówi bez przerwy
MIN_UTTERANCE = 0.45
DRAFT_EVERY = 1.2                # co ile sekund odświeżać wersję roboczą


class LiveError(RuntimeError):
    pass


def list_devices() -> list[dict]:
    """Dostępne wejścia dźwięku."""
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise LiveError("Brak sounddevice — zainstaluj: pip install sounddevice") from exc
    return [{"index": i, "name": d["name"], "channels": d["max_input_channels"],
             "default": i == sd.default.device[0]}
            for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]


def stream_url(url: str) -> str:
    """Adres strumienia dla ffmpeg — także dla transmisji na żywo z YouTube."""
    result = subprocess.run(["yt-dlp", "-g", "-f", "bestaudio/best", "--no-warnings", url],
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=120)
    if result.returncode != 0 or not result.stdout.strip():
        raise LiveError(f"Nie mogę pobrać adresu strumienia: {(result.stderr or '')[-200:]}")
    return result.stdout.strip().splitlines()[0]


@dataclass
class Utterance:
    index: int
    start: float
    end: float
    text: str
    draft: bool = False

    def as_dict(self) -> dict:
        return {"index": self.index, "start": round(self.start, 2), "end": round(self.end, 2),
                "text": self.text, "draft": self.draft}


@dataclass
class LiveSession:
    """Sesja nasłuchu. `on_update` dostaje każdą wersję roboczą i każdą wypowiedź gotową."""

    on_update: object = None
    source: str = "mic"
    device: int | None = None
    language: str = "pl"
    model: str = "small"
    save_audio: bool = True
    work: Path | None = None

    _queue: queue.Queue = field(default_factory=queue.Queue, init=False, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _threads: list = field(default_factory=list, init=False, repr=False)
    utterances: list[Utterance] = field(default_factory=list, init=False)
    started_at: float = field(default=0.0, init=False)
    error: str | None = field(default=None, init=False)

    # -------------------------------------------------- start i stop
    def start(self) -> "LiveSession":
        self.work = Path(self.work) if self.work else config.WORK / "live" / time.strftime("%Y%m%d-%H%M%S")
        self.work.mkdir(parents=True, exist_ok=True)
        self.started_at = time.time()
        self._stop.clear()
        reader = (self._read_microphone if self.source == "mic" else self._read_stream)
        for target in (reader, self._process):
            thread = threading.Thread(target=self._guard(target), daemon=True)
            thread.start()
            self._threads.append(thread)
        return self

    def stop(self, timeout: float = 30.0) -> list[dict]:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=timeout / max(len(self._threads), 1))
        self._threads.clear()
        self.save()
        return [u.as_dict() for u in self.utterances if not u.draft]

    def _guard(self, target):
        def wrapped():
            try:
                target()
            except Exception as exc:
                self.error = str(exc)
                self._emit({"type": "error", "message": str(exc)[:300]})
                self._stop.set()
        return wrapped

    def _emit(self, payload: dict) -> None:
        if callable(self.on_update):
            try:
                self.on_update(payload)
            except Exception:
                pass

    # -------------------------------------------------- źródła dźwięku
    def _read_microphone(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise LiveError("Brak sounddevice — zainstaluj: pip install sounddevice") from exc

        def callback(indata, frames, time_info, status):
            if status:
                pass
            self._queue.put(indata[:, 0].copy())

        with sd.InputStream(samplerate=RATE, blocksize=BLOCK, channels=1, dtype="float32",
                            device=self.device, callback=callback):
            self._emit({"type": "status", "message": "nasłuch z mikrofonu"})
            while not self._stop.is_set():
                time.sleep(0.1)

    def _read_stream(self) -> None:
        import numpy as np

        live = self.source.startswith("http")
        url = stream_url(self.source) if live else self.source
        # Plik z dysku czytamy w tempie odtwarzania (-re), żeby zachowywał się jak transmisja.
        pace = [] if live else ["-re"]
        process = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error"] + pace + ["-i", url,
             "-vn", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._emit({"type": "status", "message": "nasłuch ze strumienia"})
        try:
            while not self._stop.is_set():
                raw = process.stdout.read(BLOCK * 4)
                if not raw:
                    break
                self._queue.put(np.frombuffer(raw, dtype="float32").copy())
        finally:
            process.kill()

    # -------------------------------------------------- rozpoznawanie
    def _model(self):
        from faster_whisper import WhisperModel
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
        return WhisperModel(self.model, device=device,
                            compute_type="float16" if device == "cuda" else "int8")

    def _transcribe(self, model, audio) -> str:
        segments, _ = model.transcribe(audio, language=self.language, beam_size=1,
                                       vad_filter=False, condition_on_previous_text=False)
        return " ".join(s.text.strip() for s in segments).strip()

    def _process(self) -> None:
        import numpy as np

        model = self._model()
        self._emit({"type": "status", "message": "model gotowy"})
        buffer: list = []
        captured: list = []
        silence = 0.0
        speaking = False
        utterance_start = 0.0
        last_draft = 0.0
        last_draft_text = ""
        index = 0

        while not self._stop.is_set() or not self._queue.empty():
            try:
                block = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if self.save_audio:
                captured.append(block)
            now = time.time() - self.started_at
            level = float(np.sqrt(np.mean(block ** 2)))

            if level >= SILENCE_RMS:
                if not speaking:
                    speaking = True
                    utterance_start = max(0.0, now - len(block) / RATE)
                silence = 0.0
                buffer.append(block)
            elif speaking:
                silence += len(block) / RATE
                buffer.append(block)

            if not speaking:
                continue

            length = sum(len(b) for b in buffer) / RATE
            closing = silence >= SILENCE_HOLD or length >= MAX_UTTERANCE
            if closing:
                if length >= MIN_UTTERANCE:
                    audio = np.concatenate(buffer)
                    text = self._transcribe(model, audio)
                    if text:
                        index += 1
                        entry = Utterance(index=index, start=utterance_start, end=now, text=text)
                        self.utterances = [u for u in self.utterances if not u.draft] + [entry]
                        self._emit({"type": "utterance", **entry.as_dict()})
                buffer, speaking, silence, last_draft_text = [], False, 0.0, ""
            elif length >= 1.0 and time.time() - last_draft >= DRAFT_EVERY:
                last_draft = time.time()
                audio = np.concatenate(buffer)
                text = self._transcribe(model, audio)
                if text and text != last_draft_text:
                    last_draft_text = text
                    draft = Utterance(index=index + 1, start=utterance_start, end=now,
                                      text=text, draft=True)
                    self.utterances = [u for u in self.utterances if not u.draft] + [draft]
                    self._emit({"type": "draft", **draft.as_dict()})

        # Koniec materiału albo zatrzymanie sesji: to, co zostało w buforze, też jest wypowiedzią.
        if speaking and buffer:
            length = sum(len(b) for b in buffer) / RATE
            if length >= MIN_UTTERANCE:
                text = self._transcribe(model, np.concatenate(buffer))
                if text:
                    index += 1
                    entry = Utterance(index=index, start=utterance_start,
                                      end=utterance_start + length, text=text)
                    self.utterances = [u for u in self.utterances if not u.draft] + [entry]
                    self._emit({"type": "utterance", **entry.as_dict()})

        if self.save_audio and captured:
            try:
                import soundfile as sf
                sf.write(str(self.work / "nagranie.wav"), np.concatenate(captured), RATE)
            except Exception:
                pass
        self._emit({"type": "finished", "utterances": len(self.utterances)})

    # -------------------------------------------------- wynik
    def save(self) -> dict:
        final = [u.as_dict() for u in self.utterances if not u.draft]
        target = self.work / "stenogram_live.json"
        target.write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")
        text = self.work / "stenogram_live.txt"
        lines = []
        for entry in final:
            stamp = time.strftime("%H:%M:%S", time.gmtime(entry["start"]))
            lines.append(f'[{stamp}] {entry["text"]}')
        text.write_text("\n".join(lines), encoding="utf-8")
        return {"json": str(target), "txt": str(text), "audio": str(self.work / "nagranie.wav")}

    def finalize(self, title: str = "Stenogram na żywo", diarize: bool = True) -> dict:
        """Po zakończeniu: pełny przebieg na zapisanym dźwięku — z mówcami i dokumentami."""
        from .stenogram import Options, run

        audio = self.work / "nagranie.wav"
        if not audio.exists():
            raise LiveError("Nie ma zapisanego dźwięku — uruchom sesję z save_audio=True.")
        return run(audio, Options(title=title, language=self.language, diarize=diarize,
                                  model="medium"), work_dir=self.work / "final")
