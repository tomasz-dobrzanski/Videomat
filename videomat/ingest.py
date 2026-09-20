"""Pozyskiwanie materiału: YouTube i inne serwisy przez yt-dlp, pliki lokalne, strumienie.

    info = probe_url("https://www.youtube.com/watch?v=...")      # tytuł, długość, bez pobierania
    media = fetch(url, work_dir, audio_only=True)                # plik na dysku + metadane

Do stenogramu wystarcza sama ścieżka dźwiękowa (mniejszy plik, szybsze pobranie). Do montażu
pobieramy obraz. Długie nagrania nie są dzielone tutaj — dzieli je dopiero transkrypcja.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import config, ffmpeg

YOUTUBE = re.compile(r"(youtube\.com|youtu\.be)", re.I)


class IngestError(RuntimeError):
    pass


def is_url(text: str) -> bool:
    return str(text).startswith(("http://", "https://"))


# YouTube regularnie odrzuca żądania domyślnego klienta (HTTP 403). Klient `android` przechodzi —
# to samo obejście stosował pipeline NEXT100. Próbujemy po kolei, aż któryś zadziała.
CLIENTS = (None, "android", "tv", "web_safari")


def _ytdlp(args: list[str], timeout: int = 1800, retry_clients: bool = True) -> subprocess.CompletedProcess:
    problems = []
    for client in (CLIENTS if retry_clients else (None,)):
        extra = ["--extractor-args", f"youtube:player_client={client}"] if client else []
        result = subprocess.run(["yt-dlp"] + extra + args, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
        if result.returncode == 0:
            return result
        problems.append(f"{client or 'domyślny'}: {(result.stderr or result.stdout).strip()[-200:]}")
        if "is not available" in (result.stderr or "") or "Private video" in (result.stderr or ""):
            break
    raise IngestError("yt-dlp nie dał rady:\n" + "\n".join(problems[-3:]))


def probe_url(url: str) -> dict:
    """Metadane bez pobierania: tytuł, długość, autor, czy to transmisja na żywo."""
    result = _ytdlp(["--dump-single-json", "--no-warnings", "--skip-download", url], timeout=120)
    data = json.loads(result.stdout)
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "uploader": data.get("uploader") or data.get("channel"),
        "duration": data.get("duration"),
        "is_live": bool(data.get("is_live")),
        "was_live": bool(data.get("was_live")),
        "webpage_url": data.get("webpage_url", url),
        "upload_date": data.get("upload_date"),
    }


def fetch(url: str, out_dir: Path, audio_only: bool = True, quality: str = "best",
          section: tuple[float, float] | None = None) -> dict:
    """Pobiera materiał do out_dir. Zwraca ścieżkę i metadane.

    section: (od, do) w sekundach — pobiera tylko fragment. Przy wielogodzinnych transmisjach
    to różnica między minutą a godziną czekania.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe_url(url)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{info['id'] or 'material'}")[:60]
    if section:
        stem += f"_{int(section[0])}-{int(section[1])}"
    template = str(out_dir / f"{stem}.%(ext)s")

    args = ["--no-warnings", "--no-playlist", "-o", template]
    if section:
        args += ["--download-sections", f"*{section[0]:.0f}-{section[1]:.0f}"]
        if not audio_only:
            # Przycinanie obrazu wymaga klatek kluczowych w miejscach cięcia; przy samym
            # dźwięku ta opcja wywraca ffmpeg.
            args.append("--force-keyframes-at-cuts")
    if audio_only:
        args += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        args += ["-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
                 "--merge-output-format", "mp4"]
    args.append(url)
    try:
        _ytdlp(args)
    except IngestError:
        if not section:
            raise
        # Pobieranie fragmentu idzie przez ffmpeg po podpisanym adresie i bywa odrzucane.
        # Wtedy bierzemy całość i docinamy u siebie — wolniej, ale zawsze się udaje.
        full = fetch(url, out_dir, audio_only=audio_only, quality=quality, section=None)
        trimmed = out_dir / f"{stem}{Path(full['path']).suffix}"
        ffmpeg.run(["-ss", f"{section[0]:.3f}", "-to", f"{section[1]:.3f}",
                    "-i", full["path"], str(trimmed)])
        info["path"] = str(trimmed)
        info["size"] = trimmed.stat().st_size
        info["duration"] = round(ffmpeg.duration(trimmed), 2)
        return info

    matches = sorted(out_dir.glob(f"{stem}.*"))
    media = next((p for p in matches if p.suffix.lower() in
                  (".mp3", ".m4a", ".opus", ".wav", ".mp4", ".mkv", ".webm")), None)
    if not media:
        raise IngestError(f"Pobrano, ale nie znajduję pliku dla {stem}.")
    info["path"] = str(media)
    info["size"] = media.stat().st_size
    try:
        info["duration"] = round(ffmpeg.duration(media), 2)
    except Exception:
        pass
    (out_dir / f"{stem}.info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    return info


def source_to_audio(source: str | Path, out_dir: Path, audio_only: bool = True,
                    section: tuple[float, float] | None = None) -> dict:
    """Jedno wejście dla adresu i pliku lokalnego. Zwraca metadane z polem 'path'."""
    out_dir = Path(out_dir)
    if is_url(str(source)):
        return fetch(str(source), out_dir, audio_only=audio_only, section=section)
    path = Path(source)
    if not path.exists():
        raise IngestError(f"Nie ma pliku {path}")
    return {"id": path.stem, "title": path.stem, "uploader": None,
            "duration": round(ffmpeg.duration(path), 2), "is_live": False,
            "webpage_url": None, "path": str(path), "size": path.stat().st_size}


def to_wav16k(source: str | Path, out_wav: Path) -> Path:
    """Mono 16 kHz — format, którego oczekują i whisper, i diaryzacja."""
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if not out_wav.exists():
        ffmpeg.run(["-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(out_wav)])
    return out_wav
