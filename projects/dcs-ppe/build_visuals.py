"""Wizualia filmu DCS-PPE: nieskończona matryca danych i szybki pokaz detekcji. Bez żadnych napisów.

Wejście: obrazy syntetyczne z dcs-vision-ai (datasets/ppe-gen*) oraz wynik modelu z run_ppe.py
(work/dcs-ppe/ppe_detections.json). Ramki to rzeczywisty wynik modelu:
zielona = kask lub kamizelka wykryte, czerwona = brak kasku lub brak kamizelki.
Wyjście: assets/matrix.mp4 i assets/detect.mp4 (ignorowane przez git — odtwarzalne).

    python projects/dcs-ppe/run_ppe.py
    python projects/dcs-ppe/build_visuals.py
"""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from videomat import ffmpeg  # noqa: E402

APPKI = Path(os.environ.get("DCS_APPKI", r"C:/AI TOMASZ PLIKI/Appki"))
DATASETS = APPKI / "dcs-vision-ai" / "datasets"
DET = json.loads((ROOT / "work/dcs-ppe/ppe_detections.json").read_text(encoding="utf-8"))

W, H, FPS = 1080, 1920, 30
LEVEL_SECONDS = 3.6          # czas jednego trzykrotnego zbliżenia matrycy
BOXES_FROM, BOXES_SPREAD = 3.0, 3.0
MATRIX_SECONDS = 19.8
DETECT_SECONDS = 8.85
CUTS = 30

GREEN = (90, 220, 0)         # BGR
RED = (60, 50, 255)
COLOR = {"helmet": GREEN, "vest": GREEN, "no_helmet": RED, "no_vest": RED}

# Indeksy ręcznie obejrzanych przykładów braku (kandydaci z make_absence, kolejność deterministyczna).
# Odrzucone: białe/szare kamizelki, które model błędnie oznacza jako brak.
ABSENT_IDX = [1, 2, 3, 4, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20]


def make_good() -> list[str]:
    """Jedna osoba, wyraźny kask i kamizelka (pewność >= 0,7), bez alarmów braku."""
    out = []
    for key, dets in DET.items():
        persons = [d for d in dets if d["cls"] == "person"]
        if len(persons) != 1 or persons[0]["box"][3] - persons[0]["box"][1] < 0.4:
            continue
        has = lambda c: any(d["cls"] == c and d["p"] >= 0.7 for d in dets)  # noqa: E731
        if has("helmet") and has("vest") and not any(d["cls"] in ("no_helmet", "no_vest") for d in dets):
            out.append(key)
    return out


def make_absence() -> list[str]:
    out = []
    for key, dets in DET.items():
        persons = [d for d in dets if d["cls"] == "person"]
        if len(persons) == 1 and persons[0]["box"][3] - persons[0]["box"][1] >= 0.35 and \
                any(d["cls"] in ("no_helmet", "no_vest") and d["p"] >= 0.4 for d in dets):
            out.append(key)
    return out


GOOD = make_good()
_ABS = make_absence()
ABSENT = [_ABS[i] for i in ABSENT_IDX if i < len(_ABS)]


def load_subject(key: str):
    """Obraz → kadr 9:16 wycentrowany na osobie + ramki modelu (bez osoby) w pikselach kadru."""
    ds, name = key.split("/")
    img = cv2.imread(str(DATASETS / ds / "img" / name))
    h0, w0 = img.shape[:2]
    s = H / h0
    img = cv2.resize(img, (round(w0 * s), H), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    dets = DET[key]
    persons = [d for d in dets if d["cls"] == "person"]
    cx = (np.mean([persons[0]["box"][0], persons[0]["box"][2]]) if persons else 0.5) * img.shape[1]
    x0 = int(min(max(cx - W / 2, 0), img.shape[1] - W))
    crop = img[:, x0:x0 + W].copy()
    boxes = []
    for d in dets:
        if d["cls"] not in COLOR:
            continue
        x1, y1, x2, y2 = d["box"]
        b = [x1 * img.shape[1] - x0, y1 * H, x2 * img.shape[1] - x0, y2 * H]
        if (b[0] + b[2]) / 2 < 0 or (b[0] + b[2]) / 2 > W:
            continue
        boxes.append((d["cls"], [max(b[0], 2), max(b[1], 2), min(b[2], W - 2), min(b[3], H - 2)]))
    return crop, boxes


def vertical_shade() -> np.ndarray:
    y = np.linspace(0, 1, H, dtype=np.float32)
    g = 0.92 - 0.30 * np.clip((0.12 - y) / 0.12, 0, 1) ** 1.5 - 0.45 * np.clip((y - 0.70) / 0.30, 0, 1)
    return g[:, None, None]


# ------------------------------------------------------------------ matryca
def build_matrix(path: Path) -> None:
    keys = GOOD[:] + ABSENT[:]
    random.Random(7).shuffle(keys)
    pool = [load_subject(k) for k in keys]
    n_pool = len(pool)
    shade = vertical_shade()
    levels = 7

    def cell_index(n: int, slot: int) -> int:
        return (n * 29 + slot * 13 + (n * slot) % 11) % n_pool

    def jitter(n: int, slot: int) -> float:
        return ((n * 73 + slot * 31 + 7) % 100) / 100.0

    def draw_cell(canvas, n, slot, x, y, cw, ch, t):
        if cw < 2 or ch < 2 or x >= W or y >= H or x + cw <= 0 or y + ch <= 0:
            return
        img, boxes = pool[cell_index(n, slot)]
        gap = max(1, round(cw / 120))
        iw, ih = max(1, cw - 2 * gap), max(1, ch - 2 * gap)
        small = cv2.resize(img, (iw, ih), interpolation=cv2.INTER_AREA if iw < W else cv2.INTER_LINEAR)
        if t >= BOXES_FROM + BOXES_SPREAD * jitter(n, slot) and iw > 14:
            th = max(1, round(iw / 120))
            for cls, b in boxes:
                cv2.rectangle(small, (round(b[0] * iw / W), round(b[1] * ih / H)),
                              (round(b[2] * iw / W), round(b[3] * ih / H)), COLOR[cls], th)
        ox, oy = x + gap, y + gap
        sx0, sy0 = max(0, -ox), max(0, -oy)
        sx1, sy1 = min(iw, W - ox), min(ih, H - oy)
        if sx1 > sx0 and sy1 > sy0:
            canvas[oy + sy0:oy + sy1, ox + sx0:ox + sx1] = small[sy0:sy1, sx0:sx1]

    n_frames = round(MATRIX_SECONDS * FPS)
    with encoder(path, n_frames) as pipe:
        for f in range(n_frames):
            t = f / FPS
            e = t / LEVEL_SECONDS
            i0 = int(math.floor(e))
            u = e - i0
            canvas = np.full((H, W, 3), (18, 14, 10), np.uint8)
            for i in range(levels):
                s = 3.0 ** (u - i)
                cw, ch = W * s / 3.0, H * s / 3.0
                if cw < 2:
                    break
                n = i0 + i
                for slot in range(9):
                    if slot == 4:
                        continue
                    col, row = slot % 3, slot // 3
                    draw_cell(canvas, n, slot, round(W / 2 + (col - 1.5) * cw), round(H / 2 + (row - 1.5) * ch),
                              round(cw), round(ch), t)
            frame = np.clip(canvas.astype(np.float32) * shade, 0, 255).astype(np.uint8)
            pipe.stdin.write(frame.tobytes())


# ------------------------------------------------------------------ szybkie detekcje
def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def cut_durations(total: float, n: int) -> list[int]:
    """Cięcia przyspieszają: od około pół sekundy do około 0,2 s, suma dokładnie `total` (w klatkach)."""
    raw = np.linspace(0.5, 0.2, n)
    frames = np.maximum(3, np.round(raw / raw.sum() * total * FPS)).astype(int)
    frames[-1] += round(total * FPS) - frames.sum()
    return [int(x) for x in frames]


def build_detect(path: Path) -> None:
    rng = random.Random(11)
    good = GOOD[:]
    rng.shuffle(good)
    absent = ABSENT[:]
    rng.shuffle(absent)
    order: list[str] = []
    gi = ai = 0
    for i in range(CUTS):
        if i % 3 == 2 and ai < len(absent):
            order.append(absent[ai]); ai += 1
        else:
            order.append(good[gi % len(good)]); gi += 1
    lengths = cut_durations(DETECT_SECONDS, CUTS)
    shade = vertical_shade()
    with encoder(path, sum(lengths)) as pipe:
        for key, n in zip(order, lengths):
            img, boxes = load_subject(key)
            dx = rng.choice([-1, 1]) * rng.uniform(30, 70)
            dy = rng.uniform(-40, 40)
            zoom_to = rng.uniform(1.07, 1.13)
            for f in range(n):
                p = ease_out(f / max(n - 1, 1))
                z = 1.0 + (zoom_to - 1.0) * p
                bob = 16 * math.sin(2 * math.pi * 2.2 * (f / FPS)) * min(1.0, f / 3)   # krok robota
                sway = 9 * math.sin(2 * math.pi * 1.1 * (f / FPS))
                tx = dx * p + sway + W / 2 * (1 - z)
                ty = dy * p + bob + H / 2 * (1 - z)
                M = np.float32([[z, 0, tx], [0, z, ty]])
                frame = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                frame = np.clip(frame.astype(np.float32) * shade, 0, 255).astype(np.uint8)
                if f == 0:      # błysk cięcia
                    frame = cv2.addWeighted(frame, 0.7, np.full_like(frame, 255), 0.3, 0)
                lock = 1.0 + 0.10 * max(0.0, 1 - f / 2)       # ramka zatrzaskuje się w 2 klatkach
                for cls, b in boxes:
                    x1, y1, x2, y2 = b[0] * z + tx, b[1] * z + ty, b[2] * z + tx, b[3] * z + ty
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    x1, x2 = mx + (x1 - mx) * lock, mx + (x2 - mx) * lock
                    y1, y2 = my + (y1 - my) * lock, my + (y2 - my) * lock
                    cv2.rectangle(frame, (round(x1), round(y1)), (round(x2), round(y2)), COLOR[cls], 8)
                pipe.stdin.write(frame.tobytes())


# ------------------------------------------------------------------ enkoder
class encoder:
    def __init__(self, path: Path, frames: int):
        self.path, self.frames = path, frames

    def __enter__(self):
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
               "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
               "-map", "0:v", "-map", "1:a", "-shortest", *ffmpeg.encoder_args(18),
               *ffmpeg.AUDIO_ARGS, *ffmpeg.MUX_ARGS, "-r", str(FPS), str(self.path)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        return self.proc

    def __exit__(self, *exc):
        self.proc.stdin.close()
        self.proc.wait()
        print("OK" if self.proc.returncode == 0 else "BŁĄD", self.path.name, f"{self.frames} klatek")


if __name__ == "__main__":
    assets = HERE / "assets"
    assets.mkdir(exist_ok=True)
    print(len(GOOD), "obrazów z poprawną detekcją,", len(ABSENT), "z wykrytym brakiem")
    which = sys.argv[1:] or ["matrix", "detect"]
    if "matrix" in which:
        build_matrix(assets / "matrix.mp4")
    if "detect" in which:
        build_detect(assets / "detect.mp4")
