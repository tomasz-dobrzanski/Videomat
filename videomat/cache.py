"""Cache scen adresowany treścią.

Klucz sceny to skrót z: jej opisu po rozwiązaniu czasów, treści wygenerowanego pliku .ass,
rozmiaru i czasu modyfikacji użytych plików źródłowych, jakości renderu i wersji silnika.
Zmiana jednego napisu unieważnia jedną scenę, reszta montażu zostaje.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


SEP = chr(31)   # separator pól w skrócie


def fingerprint(path: Path) -> str:
    try:
        st = path.stat()
        return f"{path.name}:{st.st_size}:{int(st.st_mtime)}"
    except OSError:
        return f"{path.name}:missing"


def key(payload: dict, sources: list[Path], quality: str, engine: str) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    parts = [engine, quality, blob] + sorted(fingerprint(p) for p in sources)
    return hashlib.sha1(SEP.join(parts).encode("utf-8")).hexdigest()[:16]


class SceneCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.dir = self.root / "cache"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def path(self, key_: str, suffix: str = ".mp4") -> Path:
        return self.dir / f"{key_}{suffix}"

    def has(self, key_: str, suffix: str = ".mp4") -> bool:
        p = self.path(key_, suffix)
        ok = p.exists() and p.stat().st_size > 0
        if ok:
            self.hits += 1
            p.touch()
        else:
            self.misses += 1
        return ok

    def sweep(self, keep_days: float = 7.0) -> int:
        """Kasuje wpisy nietykane od kilku dni. Zwraca liczbę usuniętych plików."""
        cutoff = time.time() - keep_days * 86400
        removed = 0
        for p in self.dir.iterdir():
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)
                removed += 1
        return removed
