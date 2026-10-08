"""Sora: przejście sim → real z efektem lidaru (8 s, 1024x1792, sora-2-pro).

Klucz WYŁĄCZNIE ze zmiennej środowiskowej SORA_API_KEY (albo OPENAI_API_KEY) — nie zapisujemy go w plikach.
Klatka startowa: render symulacji w chwili chwytu (`assets/sim_obrot180.mp4`, 15,0 s).

    SORA_API_KEY=... python projects/chwytak/sora_gen.py [--model sora-2] [--seconds 8]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
A = HERE / "assets"
PROMPT = (
    "Vertical 9:16, one continuous 8-second shot. Start exactly from the reference image: a white humanoid robot "
    "in a dark 3D physics simulation grips a black speaker basket on a wooden table with one gripper. "
    "A thin cyan LiDAR scan line sweeps slowly from top to bottom: everything it passes turns into a dense glowing "
    "cyan point cloud and wireframe, the points flow and re-assemble, and the same moment materialises as a real "
    "photographed lab: a silver humanoid robot with one gripper lifting the real black speaker basket from a grey "
    "fixture on a black base and rotating it. Clean, precise, premium high-tech look, smooth camera, "
    "no text, no logos, no people."
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sora-2-pro")
    ap.add_argument("--seconds", default="8")
    ap.add_argument("--size", default="1024x1792")
    ap.add_argument("--t", type=float, default=15.0, help="moment klatki startowej w symulacji [s]")
    a = ap.parse_args()
    key = os.environ.get("SORA_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("Brak SORA_API_KEY w środowisku.")
    w, h = (int(v) for v in a.size.split("x"))
    ref = A / f"sora_ref_{w}x{h}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.t), "-i", str(A / "sim_obrot180.mp4"), "-frames:v", "1",
                    "-vf", f"scale={w}:-2,crop={w}:{h}", str(ref)], check=True)
    client = OpenAI(api_key=key)
    with open(ref, "rb") as fh:
        job = client.videos.create(model=a.model, prompt=PROMPT, seconds=a.seconds, size=a.size,
                                   input_reference=(ref.name, fh, "image/png"))
    print("zadanie", job.id, job.status, flush=True)
    while job.status in ("queued", "in_progress"):
        time.sleep(15)
        job = client.videos.retrieve(job.id)
        print(job.status, getattr(job, "progress", ""), flush=True)
    if job.status != "completed":
        sys.exit(f"Nieudane: {job.status} {getattr(job, 'error', '')}")
    out = A / f"sora_sim2real_{job.id[-8:]}.mp4"
    client.videos.download_content(job.id, variant="video").write_to_file(str(out))
    print("OK", out)


if __name__ == "__main__":
    main()
