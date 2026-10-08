"""Muzyka do filmu „Robot vs symulacja” — synteza pod plan cięć (assets/plan.json).

Tytuł: niski dron i puls serca. Akcja: uderzenie na KAŻDYM cięciu (coraz gęściej = rosnące napięcie), nad tym narastający
riser i filtr otwierający pad. Wejście porównania: cisza 0,3 s i duże uderzenie, potem równy puls i akordy.
Plansza: ciepły akord D-dur i wybrzmienie.

    python projects/chwytak/build_score.py   -> assets/score.wav
"""
import json
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

HERE = Path(__file__).resolve().parent
plan = json.loads((HERE / "assets" / "plan2.json").read_text(encoding="utf-8"))
SR = 48000
T = plan["total"]
N = int(SR * T)
rng = np.random.default_rng(3)
L = np.zeros(N)
R = np.zeros(N)


def lp(x, f):
    return sosfilt(butter(2, f, "low", fs=SR, output="sos"), x)


def hp(x, f):
    return sosfilt(butter(2, f, "high", fs=SR, output="sos"), x)


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def place(sig, t0, g=1.0, pan=0.5):
    i = int(t0 * SR)
    if i >= N:
        return
    j = min(N, i + len(sig))
    L[i:j] += sig[: j - i] * g * (1 - pan) * 2
    R[i:j] += sig[: j - i] * g * pan * 2


def tone(freqs, dur, cut, a=0.3, rel=0.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * t) + 0.5 * np.sin(4 * np.pi * f * t + 1) + 0.25 * np.sin(6 * np.pi * f * t + 2)
            for f in freqs)
    e = np.minimum(1, t / a) * np.minimum(1, (dur - t) / rel)
    return lp(s * e, cut)


def kick(level=1.0, f0=48):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = f0 + 90 * np.exp(-t * 24)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) * level


def impact(level=1.0):
    n = int(2.4 * SR)
    t = np.arange(n) / SR
    f = 30 + 120 * np.exp(-t * 8)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    crack = lp(rng.standard_normal(n), 4000) * np.exp(-t * 12) * 0.6
    return (body + crack) * level


def tick(level=1.0, f=2400):
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * f * t) * np.exp(-t * 70) * level


cuts = plan["cuts"]
s0, e0 = plan["split_start"], plan["end_start"]

# tytuł: dron + puls
place(tone([hz(38), hz(45)], cuts[0] + 0.3, 400, a=1.2, rel=0.3), 0.0, 0.35)
for k in range(3):
    place(kick(0.5, 40), 0.4 + k * 0.7, 1)

# akcja: uderzenie na każdym cięciu, wysokość rośnie
for i, c in enumerate(cuts):
    place(kick(0.8 + 0.01 * i, 46 + i * 1.2), c, 1)
    place(tick(0.25, 1800 + 40 * i), c, 1, pan=0.3 if i % 2 else 0.7)
n = int((s0 - cuts[0]) * SR)
t = np.arange(n) / SR
k = t / t[-1]
riser = lp(hp(rng.standard_normal(n), 300), 7000) * k ** 2.4 * 0.14 + np.sin(2 * np.pi * np.cumsum(120 + 700 * k ** 2) / SR) * k ** 2 * 0.07
place(riser, cuts[0], 1)
place(tone([hz(50), hz(57), hz(62), hz(65)], s0 - cuts[0], 1800, a=2.0, rel=0.2), cuts[0], 0.20)

# porównanie: cisza, uderzenie, puls 120 BPM i akordy
i, j = int((s0 - 0.3) * SR), int(s0 * SR)
L[i:j] *= np.linspace(1, 0, j - i)
R[i:j] *= np.linspace(1, 0, j - i)
place(impact(1.0), s0, 1)
beat = 0.5
tb = s0 + beat
while tb < e0 - 0.1:
    place(kick(0.55, 44), tb, 1)
    place(tick(0.12, 3000), tb + beat / 2, 1, pan=0.65)
    tb += beat
chords = [[50, 57, 62, 65], [46, 58, 62, 65], [48, 55, 60, 64], [45, 57, 61, 64]]
seg = (e0 - s0) / len(chords)
for q, ch in enumerate(chords):
    place(tone([hz(m) for m in ch], seg + 0.3, 2400, a=0.4, rel=0.5), s0 + q * seg, 0.17)

# plansza
place(impact(0.5), e0, 1)
place(tone([hz(m) for m in [50, 57, 62, 66, 69]], T - e0, 3000, a=0.3, rel=2.5), e0, 0.22)

# pogłos i mastering
ir_n = int(2.2 * SR)
ti = np.arange(ir_n) / SR
for ch in (L, R):
    ir = lp(rng.standard_normal(ir_n) * np.exp(-ti * 2.6), 5000)
    ch += fftconvolve(ch, ir)[:N] * 0.02
peak = max(np.abs(L).max(), np.abs(R).max())
st = np.stack([L, R], 1) / peak * 10 ** (-3 / 20)
out = HERE / "assets" / "score2.wav"
with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
print("OK", out, f"{T:.1f} s")
