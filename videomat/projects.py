"""Projekty studia: katalogi, wgrywanie materiału, zapis filmu z historią zmian.

Projekt to katalog `projects/<id>/` z plikiem `film.json`, podkatalogiem `assets/` na wgrany
materiał i `history/` z poprzednimi wersjami montażu. Pliki robocze (transkrypty, lektor, cache
scen) mieszkają w `work/<id>/`, żeby nie zaśmiecać projektu.
"""
from __future__ import annotations

import json
import re
import shutil
import time
import unicodedata
from pathlib import Path

from . import config, ffmpeg
from .timeline import ClipAsset, Film, MusicAsset

PROJECTS = config.ROOT / "projects"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD = 2 * 1024 * 1024 * 1024      # 2 GB


class ProjectError(RuntimeError):
    pass


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    plain = re.sub(r"[^a-zA-Z0-9]+", "-", plain).strip("-").lower()
    return plain or "projekt"


def project_dir(pid: str) -> Path:
    safe = slug(pid)
    path = PROJECTS / safe
    if not path.exists():
        raise ProjectError(f"Nie ma projektu {pid!r}.")
    return path


def work_dir(pid: str) -> Path:
    path = config.WORK / slug(pid)
    path.mkdir(parents=True, exist_ok=True)
    return path


def film_path(pid: str) -> Path:
    return project_dir(pid) / "film.json"


def listing() -> list[dict]:
    PROJECTS.mkdir(exist_ok=True)
    rows = []
    for path in sorted(PROJECTS.iterdir()):
        film_file = path / "film.json"
        if not path.is_dir() or not film_file.exists():
            continue
        try:
            data = json.loads(film_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        rows.append({
            "id": path.name,
            "name": data.get("name", path.name),
            "scenes": len(data.get("scenes", [])),
            "narration": len(data.get("narration", [])),
            "updated": film_file.stat().st_mtime,
        })
    return sorted(rows, key=lambda r: r["updated"], reverse=True)


def create(name: str) -> dict:
    pid = slug(name)
    path = PROJECTS / pid
    if path.exists():
        raise ProjectError(f"Projekt {pid!r} już istnieje.")
    (path / "assets").mkdir(parents=True)
    (path / "history").mkdir()
    film = Film(name=pid)
    (path / "film.json").write_text(film.model_dump_json(indent=1), encoding="utf-8")
    work_dir(pid)
    return {"id": pid, "name": pid, "scenes": 0, "narration": 0,
            "updated": (path / "film.json").stat().st_mtime}


def load(pid: str) -> Film:
    return Film.model_validate_json(film_path(pid).read_text(encoding="utf-8"))


def save(pid: str, film: Film, note: str = "") -> dict:
    target = film_path(pid)
    history = target.parent / "history"
    history.mkdir(exist_ok=True)
    if target.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(target, history / f"film-{stamp}.json")
        snapshots = sorted(history.glob("film-*.json"))
        for old in snapshots[:-50]:
            old.unlink(missing_ok=True)
    target.write_text(film.model_dump_json(indent=1), encoding="utf-8")
    return {"saved": target.name, "note": note, "updated": target.stat().st_mtime}


def history(pid: str, limit: int = 30) -> list[dict]:
    folder = project_dir(pid) / "history"
    if not folder.exists():
        return []
    rows = sorted(folder.glob("film-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [{"file": p.name, "updated": p.stat().st_mtime, "size": p.stat().st_size} for p in rows]


def restore(pid: str, filename: str) -> Film:
    source = project_dir(pid) / "history" / Path(filename).name
    if not source.exists():
        raise ProjectError(f"Nie ma zapisu {filename!r}.")
    film = Film.model_validate_json(source.read_text(encoding="utf-8"))
    save(pid, film, note=f"przywrócono {filename}")
    return film


# ------------------------------------------------------------------ materiał
def asset_kind(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in VIDEO_EXT:
        return "clip"
    if ext in AUDIO_EXT:
        return "music"
    if ext in IMAGE_EXT:
        return "image"
    raise ProjectError(f"Nieobsługiwany typ pliku: {ext or filename}")


def free_key(existing: dict, prefix: str) -> str:
    n = 1
    while f"{prefix}{n}" in existing:
        n += 1
    return f"{prefix}{n}"


def add_asset(pid: str, filename: str, data: bytes) -> dict:
    """Zapisuje wgrany plik w projekcie i dopisuje go do film.json."""
    if len(data) > MAX_UPLOAD:
        raise ProjectError("Plik jest za duży (limit 2 GB).")
    kind = asset_kind(filename)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)
    folder = project_dir(pid) / "assets"
    folder.mkdir(exist_ok=True)
    target = folder / safe
    stem, suffix = target.stem, target.suffix
    n = 1
    while target.exists():
        target = folder / f"{stem}-{n}{suffix}"
        n += 1
    target.write_bytes(data)

    film = load(pid)
    relative = f"assets/{target.name}"
    if kind == "clip":
        key = free_key(film.assets.clips, "c")
        film.assets.clips[key] = ClipAsset(path=relative)
    elif kind == "music":
        key = free_key(film.assets.music, "m")
        film.assets.music[key] = MusicAsset(path=relative)
    else:
        key = target.stem
    save(pid, film, note=f"dodano {target.name}")
    info = {"key": key, "kind": kind, "path": relative, "name": target.name,
            "size": target.stat().st_size}
    if kind in ("clip", "music"):
        try:
            info["duration"] = round(ffmpeg.duration(target), 2)
        except Exception:
            info["duration"] = None
    return info


def transcribe_asset(pid: str, key: str, language: str = "pl", model: str | None = None) -> dict:
    """Transkrybuje klip i podpina transcript.json do filmu."""
    from . import transcribe as transcriber

    film = load(pid)
    clip = film.assets.clips.get(key)
    if not clip:
        raise ProjectError(f"Nie ma klipu {key!r}.")
    source = project_dir(pid) / clip.path
    if not source.exists():
        source = config.ROOT / clip.path
    out = work_dir(pid) / f"{key}_transcript.json"
    result = transcriber.transcribe(source, out, language=language, model_size=model)
    film = load(pid)
    film.assets.clips[key].transcript = f"work/{slug(pid)}/{out.name}"
    save(pid, film, note=f"transkrypcja {key}")
    return {"key": key, "file": str(out), "segments": len(result["segments"]),
            "uncertain": result["uncertain"]}


def assets_overview(pid: str) -> dict:
    """Spis materiału z długościami i transkryptami — zasila panel Assety i warstwę promptu."""
    film = load(pid)
    base = project_dir(pid)
    clips = []
    for key, clip in film.assets.clips.items():
        path = base / clip.path
        if not path.exists():
            path = config.ROOT / clip.path
        transcript_path = base / clip.transcript if clip.transcript else None
        if transcript_path and not transcript_path.exists():
            transcript_path = config.ROOT / clip.transcript  # type: ignore[arg-type]
        segments = []
        if transcript_path and transcript_path.exists():
            try:
                data = json.loads(transcript_path.read_text(encoding="utf-8"))
                segments = [{"start": s["start"], "end": s["end"], "text": s["text"],
                             "words": s.get("words", [])} for s in data.get("segments", [])]
            except Exception:
                segments = []
        clips.append({
            "key": key, "path": clip.path, "exists": path.exists(), "crop": clip.crop,
            "duration": round(ffmpeg.duration(path), 2) if path.exists() else None,
            "transcript": clip.transcript, "segments": segments, "fixes": clip.fixes,
        })
    music = []
    for key, item in film.assets.music.items():
        path = base / item.path
        if not path.exists():
            path = config.ROOT / item.path
        music.append({"key": key, "path": item.path, "exists": path.exists(),
                      "gain_db": item.gain_db,
                      "duration": round(ffmpeg.duration(path), 2) if path.exists() else None})
    work = work_dir(pid)
    narration = []
    for line in film.narration:
        audio = work / f"{line.id}_fast.wav"
        narration.append({"id": line.id, "text": line.text,
                          "audio": audio.exists(),
                          "duration": round(ffmpeg.duration(audio), 2) if audio.exists() else line.fallback})
    return {"clips": clips, "music": music, "narration": narration,
            "sfx": [{"key": k, "prompt": v.prompt, "path": v.path} for k, v in film.assets.sfx.items()]}
