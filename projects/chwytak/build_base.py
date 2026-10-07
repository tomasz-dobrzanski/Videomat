"""Obraz filmu „Robot vs symulacja” (9:16, 30 kl./s) + plan cięć dla muzyki i napisów.

Części:
  A. tytuł na czerni (2,5 s)
  B. AKCJA: robot (VID…, cykl 2, zwolnione ×0,5 z 60 kl./s — płynnie) na przemian z symulacją w tej samej fazie ruchu;
     cięcia przyspieszają od 1,0 s do 0,35 s
  C. PORÓWNANIE 1:1: robot u góry (cykl 1, ×0,6), symulacja na dole zsynchronizowana fazami (time-warp)
  D. plansza DCS Robotics (biała, oficjalne logo)

Fazy (sekundy źródła) odczytane z klatek co 0,5 s; symulacja z `assets/sim_obrot180.json` (fizyka MuJoCo).
Wynik: assets/base.mp4 + assets/plan.json (czasy cięć i etykiety).

    python projects/chwytak/build_base.py
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
A = HERE / "assets"
REAL = ROOT / "GOTOWE FILMY" / "RobotChwytak" / "VID20261007145256.mp4"
SIM = A / "sim_obrot180.mp4"
APPKI = Path(os.environ.get("DCS_APPKI", r"C:/AI TOMASZ PLIKI/Appki"))
FPS = 30

PHASES = ["dojazd", "przy koszu", "zacisk", "uniesienie", "obrót", "obrót", "odłożenie"]
K_REAL_C1 = [1.5, 3.0, 3.8, 4.3, 4.6, 5.6, 6.6]
K_REAL_C2 = [12.0, 13.2, 13.6, 14.0, 14.8, 15.6, 16.6]
K_SIM = [6.0, 12.1, 14.4, 16.0, 18.9, 24.0, 31.5]


def warp(t: float, src: list[float], dst: list[float]) -> float:
    """Czas w źródle `src` -> odpowiadający czas w `dst` (liniowo między punktami faz)."""
    if t <= src[0]:
        return dst[0] + (t - src[0])
    for i in range(len(src) - 1):
        if t <= src[i + 1]:
            u = (t - src[i]) / (src[i + 1] - src[i])
            return dst[i] + u * (dst[i + 1] - dst[i])
    return dst[-1] + (t - src[-1])


def seg(src: Path, a: float, b: float, dur: float, out: Path, vf_extra: str = "") -> None:
    speed = (b - a) / dur
    vf = (f"trim={a:.4f}:{b:.4f},setpts=(PTS-STARTPTS)/{speed:.5f},fps={FPS},"
          f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1{vf_extra}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", vf, "-t", f"{dur:.4f}", "-an",
                    "-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "16", "-b:v", "0", "-pix_fmt", "yuv420p",
                    str(out)], check=True)


def main() -> None:
    tmp = A / "seg"
    tmp.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    plan = {"cuts": [], "labels": [], "phases": []}
    t = 0.0

    # A. tytuł
    p = tmp / "a_title.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r={FPS}:d=2.5",
                    "-c:v", "h264_nvenc", "-pix_fmt", "yuv420p", str(p)], check=True)
    parts.append(p)
    t += 2.5

    # B. akcja: czas filmu prowadzi robot ×0,5 (cykl 2), symulacja dogania tę samą fazę
    r0, r1 = K_REAL_C2[0] - 0.3, K_REAL_C2[-1] + 0.5
    total = (r1 - r0) / 0.5
    durs, d = [], 1.0
    while sum(durs) + d < total:
        durs.append(round(d, 3))
        d = max(0.35, d * 0.86)
    durs[-1] += total - sum(durs)
    rt = r0
    for i, dd in enumerate(durs):
        ra, rb = rt, rt + dd * 0.5
        out = tmp / f"b_{i:02d}.mp4"
        if i % 2 == 0:
            seg(REAL, ra, rb, dd, out)
            plan["labels"].append([round(t, 3), round(t + dd, 3), "ROBOT"])
        else:
            sa, sb = warp(ra, K_REAL_C2, K_SIM), warp(rb, K_REAL_C2, K_SIM)
            seg(SIM, sa, sb, dd, out)
            plan["labels"].append([round(t, 3), round(t + dd, 3), "SYMULACJA"])
        plan["cuts"].append(round(t, 3))
        parts.append(out)
        t += dd
        rt = rb

    # C. porównanie 1:1 — góra robot (×0,6), dół symulacja w tej samej fazie
    plan["split_start"] = round(t, 3)
    ra, rb = K_REAL_C1[0] - 0.2, K_REAL_C1[-1] + 0.6
    dur = (rb - ra) / 0.6
    real_top = tmp / "c_real.mp4"
    sim_bot = tmp / "c_sim.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(REAL), "-vf",
                    f"trim={ra}:{rb},setpts=(PTS-STARTPTS)/0.6,fps={FPS},scale=1080:1920,crop=1080:960:0:860,setsar=1",
                    "-an", "-c:v", "h264_nvenc", "-cq", "16", "-pix_fmt", "yuv420p", str(real_top)], check=True)
    # symulacja: sklejamy kawałki między fazami z prędkością dopasowaną do robota
    knots = [ra] + K_REAL_C1 + [rb]
    pieces = []
    for i in range(len(knots) - 1):
        a, b = knots[i], knots[i + 1]
        if b - a < 1e-3:
            continue
        sa, sb = warp(a, K_REAL_C1, K_SIM), warp(b, K_REAL_C1, K_SIM)
        o = tmp / f"c_sim_{i}.mp4"
        dd = (b - a) / 0.6
        vf = (f"trim={sa:.4f}:{sb:.4f},setpts=(PTS-STARTPTS)/{(sb - sa) / dd:.5f},fps={FPS},"
              f"scale=1080:1920,crop=1080:960:0:880,setsar=1")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SIM), "-vf", vf, "-t", f"{dd:.4f}", "-an",
                        "-c:v", "h264_nvenc", "-cq", "16", "-pix_fmt", "yuv420p", str(o)], check=True)
        pieces.append(o)
        plan["phases"].append([round(t + (a - ra) / 0.6, 3), PHASES[min(i, len(PHASES) - 1)] if i else "start"])
    lst = tmp / "c_sim.txt"
    lst.write_text("".join(f"file '{x.as_posix()}'\n" for x in pieces), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    str(sim_bot)], check=True)
    split = tmp / "c_split.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(real_top), "-i", str(sim_bot), "-filter_complex",
                    f"[0:v]trim=0:{dur:.3f},setpts=PTS-STARTPTS[t];[1:v]trim=0:{dur:.3f},setpts=PTS-STARTPTS[b];"
                    f"[t][b]vstack=inputs=2,drawbox=x=0:y=957:w=1080:h=6:color=0x05070C@1:t=fill[v]",
                    "-map", "[v]", "-c:v", "h264_nvenc", "-cq", "16", "-pix_fmt", "yuv420p", str(split)], check=True)
    parts.append(split)
    t += dur

    # D. plansza
    logo = Image.open(APPKI / "Websitomat/stronki/robot-ai/public/brand/dcs-robotics-logo.png").convert("RGB")
    g = logo.convert("L").point(lambda v: 255 if v < 245 else 0)
    logo = logo.crop(g.getbbox())
    card = Image.new("RGB", (1080, 1920), (255, 255, 255))
    lg = logo.resize((680, round(logo.height * 680 / logo.width)), Image.LANCZOS)
    card.paste(lg, ((1080 - 680) // 2, 760))
    card.save(A / "endcard.png")
    plan["end_start"] = round(t, 3)
    p = tmp / "d_end.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", "4.0", "-i", str(A / "endcard.png"), "-vf",
                    f"fps={FPS},format=yuv420p,fade=t=in:st=0:d=0.4", "-c:v", "h264_nvenc", "-cq", "16", str(p)],
                   check=True)
    parts.append(p)
    t += 4.0
    plan["total"] = round(t, 3)

    lst = tmp / "all.txt"
    lst.write_text("".join(f"file '{x.as_posix()}'\n" for x in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "h264_nvenc",
                    "-cq", "16", "-pix_fmt", "yuv420p", "-r", str(FPS), str(A / "base.mp4")], check=True)
    (A / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("OK", A / "base.mp4", plan["total"], "s;", len(plan["cuts"]), "cięć")


if __name__ == "__main__":
    main()
