"""Veo 3.1: przejście symulacja → prawdziwy robot z efektem lidaru (9:16, 8 s), klatka startowa z symulacji.

Klucz WYŁĄCZNIE ze zmiennej środowiskowej VEO_API_KEY — nie zapisujemy go w plikach.

    VEO_API_KEY=... python projects/chwytak/veo_gen.py [--model veo-3.1-generate-preview] [--t 15.0]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent
A = HERE / "assets"
PROMPT = (
    "Vertical 9:16, one continuous shot. Start exactly from the reference image: a white humanoid robot in a dark 3D "
    "physics simulation holds a black speaker basket above a wooden table with one gripper. A thin cyan LiDAR scan line "
    "sweeps slowly from the top of the frame to the bottom; everything it passes dissolves into a dense glowing cyan "
    "point cloud and wireframe, the points drift and re-assemble, and the same moment materialises as a real "
    "photographed laboratory: a silver humanoid robot with one gripper lifting the real black speaker basket from a "
    "grey fixture on a black base, then rotating it. Clean, precise, premium high-tech look, slow smooth camera, "
    "no text, no logos, no people."
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="veo-3.1-generate-preview")
    ap.add_argument("--t", type=float, default=15.0)
    ap.add_argument("--seconds", type=int, default=8)
    a = ap.parse_args()
    key = os.environ.get("VEO_API_KEY")
    if not key:
        sys.exit("Brak VEO_API_KEY w środowisku.")
    ref = A / "veo_ref.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.t), "-i", str(A / "sim_obrot180.mp4"), "-frames:v", "1",
                    str(ref)], check=True)
    client = genai.Client(api_key=key)
    op = client.models.generate_videos(
        model=a.model, prompt=PROMPT,
        image=types.Image(image_bytes=ref.read_bytes(), mime_type="image/png"),
        config=types.GenerateVideosConfig(aspect_ratio="9:16", duration_seconds=a.seconds, number_of_videos=1),
    )
    print("zadanie", op.name, flush=True)
    while not op.done:
        time.sleep(12)
        op = client.operations.get(op)
        print(".", end="", flush=True)
    print()
    if op.error:
        sys.exit(f"Nieudane: {op.error}")
    vids = op.response.generated_videos
    if not vids:
        sys.exit(f"Brak wideo w odpowiedzi: {op.response}")
    out = A / f"veo_sim2real_{int(time.time())}.mp4"
    client.files.download(file=vids[0].video)
    vids[0].video.save(str(out))
    print("OK", out)


if __name__ == "__main__":
    main()
