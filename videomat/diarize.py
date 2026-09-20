"""Kto mówi: diaryzacja pyannote + scalenie z transkrypcją słowo po słowie.

    turns = diarize("audio16k.wav")                    # [{"start","end","speaker"}]
    segments = attach(transcript, turns)               # segmenty z polem "speaker"
    names = {"SPEAKER_00": "Jan Kowalski"}             # mapowanie ręczne albo z odcisków głosu

Model `pyannote/speaker-diarization-3.1` wymaga tokena HuggingFace (HF_TOKEN w środowisku albo
zapisany przez `huggingface-cli login`). Modele są w lokalnym cache, więc po pierwszym pobraniu
diaryzacja działa bez sieci.

Identyfikacja nazwisk nie zgaduje: albo podajesz mapowanie, albo wskazujesz próbki głosu znanych
osób i porównujemy odciski (speechbrain). Bez jednego z tych dwóch mówcy zostają anonimowi.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config

MODEL = "pyannote/speaker-diarization-3.1"
_PIPELINE = None


class DiarizationUnavailable(RuntimeError):
    pass


def _token() -> str | None:
    return config.env("HF_TOKEN") or config.env("HUGGINGFACE_TOKEN") or config.env("HUGGING_FACE_HUB_TOKEN")


def _allow_pyannote_checkpoints() -> None:
    """PyTorch 2.6 wczytuje wagi w trybie ograniczonym; checkpointy pyannote tego nie przechodzą.

    Dopuszczamy dokładnie te typy, które siedzą w oficjalnych checkpointach pyannote pobranych
    z HuggingFace. Zakres jest wąski i dotyczy tylko modeli, które sami ściągnęliśmy.
    """
    import torch.serialization as serialization
    allow: list = []
    try:
        from torch.torch_version import TorchVersion
        allow.append(TorchVersion)
    except Exception:
        pass
    for module, names in (
        ("omegaconf.base", ("ContainerMetadata", "Metadata")),
        ("omegaconf.dictconfig", ("DictConfig",)),
        ("omegaconf.listconfig", ("ListConfig",)),
        ("omegaconf.nodes", ("AnyNode",)),
        ("collections", ("defaultdict", "OrderedDict")),
        ("pyannote.audio.core.task", ("Specifications", "Problem", "Resolution")),
    ):
        try:
            loaded = __import__(module, fromlist=list(names))
            allow += [getattr(loaded, name) for name in names if hasattr(loaded, name)]
        except Exception:
            continue
    allow.append(list)
    try:
        serialization.add_safe_globals(allow)
    except Exception:
        pass


def _calm_lazy_imports() -> None:
    """speechbrain 1.1 trzyma w sys.modules moduły-przekierowania do opcjonalnych zależności
    (k2, spacy, transformers). pytorch-lightning woła `inspect.stack()`, a `inspect.getmodule`
    sprawdza `__file__` każdego modułu — na przekierowaniu uruchamia to prawdziwy import
    nieistniejącego pakietu i wywala diaryzację.

    Wpisujemy im `__file__` prosto do słownika modułu, więc sprawdzenie trafia na zwykły atrybut
    i nie schodzi do `__getattr__`. Nic nie wyłączamy — moduł nadal zaimportuje się normalnie,
    gdy ktoś faktycznie sięgnie po jego zawartość.
    """
    import sys
    import types

    try:
        import speechbrain  # noqa: F401  — musi być załadowany, żeby przekierowania istniały
    except Exception:
        return
    for module in list(sys.modules.values()):
        if not isinstance(module, types.ModuleType) or type(module) is types.ModuleType:
            continue
        if type(module).__module__ != "speechbrain.utils.importutils":
            continue
        if "__file__" not in module.__dict__:
            module.__dict__["__file__"] = "<opcjonalna zależność speechbrain>"


def pipeline():
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE
    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise DiarizationUnavailable("Brak pyannote.audio — zainstaluj: pip install pyannote.audio") from exc
    _allow_pyannote_checkpoints()
    _calm_lazy_imports()
    try:
        _PIPELINE = Pipeline.from_pretrained(MODEL, use_auth_token=_token())
    except Exception as exc:
        raise DiarizationUnavailable(
            f"Nie mogę wczytać modelu {MODEL}: {str(exc)[:200]}. "
            "Potrzebny token HF_TOKEN i zaakceptowane warunki modelu na huggingface.co."
        ) from exc
    if _PIPELINE is None:
        raise DiarizationUnavailable(f"Model {MODEL} nie został udostępniony temu kontu.")
    try:
        import torch
        if torch.cuda.is_available():
            _PIPELINE.to(torch.device("cuda"))
    except Exception as exc:
        # Karta bywa zajęta przez inną bibliotekę (konflikt cuDNN z faster-whisper) —
        # wtedy liczymy na procesorze: wolniej, ale wynik ten sam.
        print(f"diaryzacja na procesorze ({str(exc)[:80]})")
    return _PIPELINE


def diarize(wav: str | Path, num_speakers: int | None = None,
            min_speakers: int | None = None, max_speakers: int | None = None,
            cache: Path | None = None, on_progress=None) -> list[dict]:
    """Zwraca listę wypowiedzi: [{"start", "end", "speaker"}] posortowaną po czasie."""
    if cache and Path(cache).exists():
        return json.loads(Path(cache).read_text(encoding="utf-8"))
    params: dict = {}
    if num_speakers:
        params["num_speakers"] = num_speakers
    if min_speakers:
        params["min_speakers"] = min_speakers
    if max_speakers:
        params["max_speakers"] = max_speakers
    if on_progress:
        on_progress(0.05, "wczytuję model diaryzacji")
    annotation = pipeline()(str(wav), **params)
    turns = [{"start": round(float(segment.start), 2), "end": round(float(segment.end), 2),
              "speaker": str(label)}
             for segment, _, label in annotation.itertracks(yield_label=True)]
    turns.sort(key=lambda t: t["start"])
    if cache:
        Path(cache).write_text(json.dumps(turns, ensure_ascii=False, indent=1), encoding="utf-8")
    return turns


def speaker_at(turns: list[dict], start: float, end: float) -> str | None:
    """Mówca z największym pokryciem czasowym danego fragmentu."""
    best, best_overlap = None, 0.0
    for turn in turns:
        overlap = min(end, turn["end"]) - max(start, turn["start"])
        if overlap > best_overlap:
            best, best_overlap = turn["speaker"], overlap
    return best


def attach(transcript: dict, turns: list[dict], split_on_change: bool = True) -> list[dict]:
    """Dopina mówców do transkrypcji. Segment z kilkoma mówcami jest dzielony na granicy słów."""
    out: list[dict] = []
    for segment in transcript.get("segments", []):
        words = segment.get("words") or []
        if not words:
            out.append({**segment, "speaker": speaker_at(turns, segment["start"], segment["end"])})
            continue
        current: list[dict] = []
        current_speaker = None
        for word in words:
            who = speaker_at(turns, word["start"], word["end"])
            if current and split_on_change and who != current_speaker:
                out.append(_pack(current, current_speaker))
                current = []
            if not current:
                current_speaker = who
            current.append(word)
        if current:
            out.append(_pack(current, current_speaker))
    return _merge_neighbours(out)


def _pack(words: list[dict], speaker: str | None) -> dict:
    return {"start": round(words[0]["start"], 2), "end": round(words[-1]["end"], 2),
            "text": " ".join(w["w"] for w in words).strip(),
            "words": words, "speaker": speaker}


def _merge_neighbours(segments: list[dict], gap: float = 0.8) -> list[dict]:
    """Skleja sąsiadujące fragmenty tego samego mówcy — inaczej stenogram sypie się na okruchy."""
    merged: list[dict] = []
    for segment in segments:
        if (merged and merged[-1]["speaker"] == segment["speaker"]
                and segment["start"] - merged[-1]["end"] <= gap):
            previous = merged[-1]
            previous["end"] = segment["end"]
            previous["text"] = f'{previous["text"]} {segment["text"]}'.strip()
            previous["words"] = previous.get("words", []) + segment.get("words", [])
        else:
            merged.append(dict(segment))
    return merged


def speaker_stats(segments: list[dict]) -> list[dict]:
    """Ile każdy mówił — do podsumowania w dokumencie."""
    totals: dict[str, dict] = {}
    for segment in segments:
        key = segment.get("speaker") or "?"
        row = totals.setdefault(key, {"speaker": key, "seconds": 0.0, "turns": 0, "words": 0})
        row["seconds"] += segment["end"] - segment["start"]
        row["turns"] += 1
        row["words"] += len(segment.get("text", "").split())
    rows = sorted(totals.values(), key=lambda r: r["seconds"], reverse=True)
    for row in rows:
        row["seconds"] = round(row["seconds"], 1)
    return rows


# ------------------------------------------------------------------ rozpoznawanie osób po głosie
def embed(wav: str | Path, start: float | None = None, end: float | None = None):
    """Odcisk głosu fragmentu (speechbrain ECAPA). Do porównywania z próbkami znanych osób."""
    try:
        import torch
        import torchaudio
        from speechbrain.inference.speaker import EncoderClassifier
    except ImportError as exc:
        raise DiarizationUnavailable("Brak speechbrain/torchaudio do rozpoznawania głosu.") from exc
    global _ENCODER
    try:
        encoder = _ENCODER
    except NameError:
        encoder = None
    if encoder is None:
        device = "cuda" if __import__("torch").cuda.is_available() else "cpu"
        encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(config.WORK / "models" / "ecapa"),
            run_opts={"device": device})
        globals()["_ENCODER"] = encoder
    signal, rate = torchaudio.load(str(wav))
    if start is not None and end is not None:
        signal = signal[:, int(start * rate):int(end * rate)]
    if rate != 16000:
        signal = torchaudio.functional.resample(signal, rate, 16000)
    return encoder.encode_batch(signal).squeeze().detach().cpu()


def identify(wav: str | Path, turns: list[dict], samples: dict[str, str],
             threshold: float = 0.55) -> dict[str, str]:
    """Mapuje etykiety pyannote na nazwiska, porównując odciski głosu z próbkami.

    samples: {"Jan Kowalski": "probki/jan.wav", ...}. Dopasowania poniżej progu zostają anonimowe —
    lepszy pusty podpis niż podpisanie wypowiedzi niewłaściwej osobie.
    """
    import torch

    references = {name: embed(path) for name, path in samples.items()}
    mapping: dict[str, str] = {}
    by_speaker: dict[str, list[dict]] = {}
    for turn in turns:
        by_speaker.setdefault(turn["speaker"], []).append(turn)
    for speaker, speaker_turns in by_speaker.items():
        longest = max(speaker_turns, key=lambda t: t["end"] - t["start"])
        if longest["end"] - longest["start"] < 1.0:
            continue
        vector = embed(wav, longest["start"], longest["end"])
        scores = {name: float(torch.nn.functional.cosine_similarity(vector, ref, dim=0))
                  for name, ref in references.items()}
        best = max(scores, key=scores.get)
        if scores[best] >= threshold:
            mapping[speaker] = best
    return mapping
