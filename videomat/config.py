"""Ustawienia projektu: klucze z .env, ścieżki, wybór enkodera."""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
OUT = ROOT / "out"
FONTS = ROOT / "fonts"
DEFAULT_FONT = "Rajdhani SemiBold"

load_dotenv(ROOT / ".env")


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def require_key(name: str) -> str:
    v = env(name)
    if not v:
        raise SystemExit(
            f"Brak {name}. Wpisz klucz do pliku .env (wzór: .env.example). "
            "Klucz nigdy nie trafia do kodu ani repozytorium."
        )
    return v


def ensure_dirs() -> None:
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "verify").mkdir(exist_ok=True)


@lru_cache(maxsize=1)
def encoder() -> str:
    """'nvenc' gdy h264_nvenc dostępny i działa, inaczej 'x264'. Nadpisz przez VIDEOMAT_ENCODER."""
    forced = env("VIDEOMAT_ENCODER")
    if forced in ("nvenc", "x264"):
        return forced
    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
        )
        return "nvenc" if r.returncode == 0 else "x264"
    except Exception:
        return "x264"


def next_version_path(directory: Path, stem: str, ext: str = ".mp4") -> Path:
    """Zawsze nowa nazwa pliku (stem_v1, stem_v2, ...) — klienci cache'ują po nazwie."""
    directory.mkdir(parents=True, exist_ok=True)
    n = 1
    while (directory / f"{stem}_v{n}{ext}").exists():
        n += 1
    return directory / f"{stem}_v{n}{ext}"
