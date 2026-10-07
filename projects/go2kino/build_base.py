"""Podstawa obrazu filmu Go2 z sekwencją budowy (61,8 s, 1080x1920, 30 kl./s, bez dźwięku).

Go2 (5) 0–38 s  →  ujęcie generowane (Seedance: wejście w robota + przemiana korytarza, zwolnione do 0,85)
→ 708.mp4 0,3–5,3 s (prawdziwe nagranie z hali)  →  Go2 (5) 51,4–60,73 s (plansza DCS, bez schodów).
Na wstawkach bez znaku nakładamy plakietkę DCS wyciętą z oryginału (`assets/badge.png`, 762,1702).

    python projects/go2kino/build_base.py
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / "GOTOWE FILMY" / "Go2 (5).mp4"
S = ROOT / "GOTOWE FILMY" / "seedance-2.5_One_continuous_smooth_cinematic_camera_move_starting_from_the_exact_supplied_ref-0.mp4"
H = ROOT / "GOTOWE FILMY" / "708.mp4"
A = Path(__file__).resolve().parent / "assets"

if not (A / "badge.png").exists():
    from PIL import Image, ImageDraw
    raw = A / "badge_raw.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "20", "-i", str(G), "-frames:v", "1",
                    "-vf", "crop=222:122:762:1702", str(raw)], check=True)
    im = Image.open(raw).convert("RGBA")
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], 16, fill=255)
    im.putalpha(m)
    im.save(A / "badge.png")

fit = "fps=30,scale=1080:1920:flags=lanczos,setsar=1"
graph = (f"[0:v]trim=0:38,setpts=PTS-STARTPTS,{fit}[a];"
         f"[1:v]crop=680:1210:20:20,scale=1080:1920:flags=lanczos,setpts=PTS/0.85,fps=30,setsar=1[b];"
         f"[2:v]trim=0.3:5.3,setpts=PTS-STARTPTS,{fit}[h];"
         f"[0:v]trim=51.4:60.73,setpts=PTS-STARTPTS,{fit}[c];"
         f"[a][b][h][c]concat=n=4:v=1:a=0[cat];"
         f"[cat][3:v]overlay=762:1702:enable='between(t,38.0,52.47)'[v]")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(G), "-i", str(S), "-i", str(H), "-i", str(A / "badge.png"),
                "-filter_complex", graph, "-map", "[v]", "-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr",
                "-cq", "16", "-b:v", "0", "-pix_fmt", "yuv420p", str(A / "base_budowa.mp4")], check=True)
print("OK", A / "base_budowa.mp4")
