"""Wizualia filmu DCS-PPE: nieskończona matryca danych i pokaz detekcji.

Wejście: obrazy syntetyczne z dcs-vision-ai (datasets/ppe-gen*) oraz wynik modelu z run_ppe.py
(work/dcs-ppe/ppe_detections.json). Ramki detekcji to rzeczywisty wynik modelu, nic nie jest rysowane
"z głowy". Wyjście: assets/matrix.mp4 i assets/detect.mp4 (pliki ignorowane przez git — odtwarzalne).

    python projects/dcs-ppe/build_visuals.py
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from videomat import ffmpeg  # noqa: E402

APPKI = Path(os.environ.get("DCS_APPKI", r"C:/AI TOMASZ PLIKI/Appki"))
DATASETS = APPKI / "dcs-vision-ai" / "datasets"
DET = json.loads((ROOT / "work/dcs-ppe/ppe_detections.json").read_text(encoding="utf-8"))


def make_pick() -> dict:
    """Obrazy z jedną osobą, wyraźnym kaskiem i kamizelką (pewność >= 0,7) i bez alarmów braku."""
    good = []
    for key, dets in DET.items():
        persons = [d for d in dets if d["cls"] == "person"]
        if len(persons) != 1 or persons[0]["box"][3] - persons[0]["box"][1] < 0.4:
            continue
        has = lambda c: any(d["cls"] == c and d["p"] >= 0.7 for d in dets)  # noqa: E731
        if has("helmet") and has("vest") and not any(d["cls"] in ("no_helmet", "no_vest") for d in dets):
            good.append(key)
    return {"good": good}


PICK = make_pick()
FONT = ImageFont.truetype(str(ROOT / "fonts/Rajdhani-SemiBold.ttf"), 46)
FONT_S = ImageFont.truetype(str(ROOT / "fonts/Rajdhani-SemiBold.ttf"), 42)

W, H, FPS = 1080, 1920, 30
LEVEL_SECONDS = 4.2          # czas jednego trzykrotnego zbliżenia
BOXES_FROM, BOXES_SPREAD = 5.0, 4.0   # kiedy w matrycy zaczynają pojawiać się ramki modelu
MATRIX_SECONDS = 15.9
DETECT_CUTS = [("good", 12, 1.25), ("good", 20, 1.25), ("good", 7, 1.25), ("good", 8, 5.1)]

# BGR
COLORS = {"person": (255, 255, 255), "helmet": (138, 224, 60), "vest": (255, 194, 0),
          "no_helmet": (28, 159, 255), "no_vest": (28, 159, 255)}
RGB = {k: (v[2], v[1], v[0]) for k, v in COLORS.items()}
LABEL = {"person": "OSOBA", "helmet": "KASK", "vest": "KAMIZELKA",
         "no_helmet": "BRAK KASKA", "no_vest": "BRAK KAMIZELKI"}


def load_subject(key: str):
    """Obraz → kadr 9:16 wycentrowany na osobie + ramki modelu w pikselach kadru."""
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
        x1, y1, x2, y2 = d["box"]
        b = [x1 * img.shape[1] - x0, y1 * H, x2 * img.shape[1] - x0, y2 * H]
        if (b[0] + b[2]) / 2 < 0 or (b[0] + b[2]) / 2 > W:
            continue
        boxes.append((d["cls"], d["p"], [max(b[0], 2), max(b[1], 2), min(b[2], W - 2), min(b[3], H - 2)]))
    return crop, boxes


# ------------------------------------------------------------------ matryca
def vertical_shade() -> np.ndarray:
    """Przyciemnienie góry i dołu — pod napisy i nagłówki."""
    y = np.linspace(0, 1, H, dtype=np.float32)
    g = 0.88 - 0.45 * np.clip((0.16 - y) / 0.16, 0, 1) ** 1.5 - 0.62 * np.clip((y - 0.58) / 0.30, 0, 1) ** 1.0
    return g[:, None, None]


def build_matrix(path: Path) -> None:
    pool_keys = PICK["good"]
    pool = [load_subject(k) for k in pool_keys]
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
            th = max(1, round(iw / 150))
            for cls, _, b in boxes:
                if cls == "person":
                    continue
                p1 = (round(b[0] * iw / W), round(b[1] * ih / H))
                p2 = (round(b[2] * iw / W), round(b[3] * ih / H))
                cv2.rectangle(small, p1, p2, COLORS[cls], th)
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
                    x = round(W / 2 + (col - 1.5) * cw)
                    y = round(H / 2 + (row - 1.5) * ch)
                    draw_cell(canvas, n, slot, x, y, round(cw), round(ch), t)
            frame = np.clip(canvas.astype(np.float32) * shade, 0, 255).astype(np.uint8)
            pipe.stdin.write(frame.tobytes())


# ------------------------------------------------------------------ detekcje
def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def build_detect(path: Path) -> None:
    segments = []
    for kind, idx, secs in DETECT_CUTS:
        key = PICK[kind][idx]
        img, boxes = load_subject(key)
        segments.append((img, boxes, secs))
    n_total = sum(round(s * FPS) for _, _, s in segments)
    shade = vertical_shade()
    with encoder(path, n_total) as pipe:
        for img, boxes, secs in segments:
            n = round(secs * FPS)
            order = {"person": 0.10, "helmet": 0.45, "no_helmet": 0.45, "vest": 0.80, "no_vest": 0.80}
            for f in range(n):
                t = f / FPS
                z = 1.0 + 0.07 * (t / secs)
                M = np.float32([[z, 0, W / 2 * (1 - z)], [0, z, H / 2 * (1 - z)]])
                frame = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR)
                frame = np.clip(frame.astype(np.float32) * shade, 0, 255).astype(np.uint8)
                pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                dr = ImageDraw.Draw(pil, "RGBA")
                sweep = ease(t / 0.7)
                if 0 < t < 0.7:
                    yy = int(H * sweep)
                    dr.rectangle([0, yy - 3, W, yy + 3], fill=(0, 194, 255, 150))
                for cls, p, b in sorted(boxes, key=lambda d: order.get(d[0], 0.5)):
                    a = ease((t - order.get(cls, 0.5)) / 0.28)
                    if a <= 0:
                        continue
                    x1, y1, x2, y2 = [(v - c) * z + c for v, c in zip(b, (W / 2, H / 2, W / 2, H / 2))]
                    grow = 1 + 0.10 * (1 - a)
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    x1, x2 = mx + (x1 - mx) * grow, mx + (x2 - mx) * grow
                    y1, y2 = my + (y1 - my) * grow, my + (y2 - my) * grow
                    col = RGB[cls]
                    al = int(255 * a)
                    dr.rectangle([x1, y1, x2, y2], outline=col + (al,), width=6 if cls != "person" else 4)
                    if cls != "person":
                        text = LABEL[cls]
                        tw = dr.textlength(text, font=FONT_S)
                        ty = y1 - 54 if y1 > 60 else y2 + 8
                        dr.rectangle([x1, ty, x1 + tw + 22, ty + 50], fill=(8, 12, 20, int(210 * a)))
                        dr.text((x1 + 11, ty + 2), text, font=FONT_S, fill=col + (al,))
                pipe.stdin.write(cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR).tobytes())


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
    which = sys.argv[1:] or ["matrix", "detect"]
    if "matrix" in which:
        build_matrix(assets / "matrix.mp4")
    if "detect" in which:
        build_detect(assets / "detect.mp4")
