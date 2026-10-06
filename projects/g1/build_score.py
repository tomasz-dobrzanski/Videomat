"""Muzyka do zwiastuna G1 — synteza w numpy/scipy, zsynchronizowana z montażem (60 s, 100 BPM, d-moll -> D-dur).

Warstwy: pad akordowy (piłowe z rozstrojeniem, filtr dolnoprzepustowy), puls ósemkowy (pluck), bas, „serce”
(kick), riser, uderzenia w momentach chwytu, pogłos splotowy. Bez zewnętrznych sampli i bez licencji.

    python projects/g1/build_score.py      -> projects/g1/assets/score.wav
"""
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
TOTAL = 60.0
BPM = 100
BEAT = 60 / BPM
N = int(SR * TOTAL)
rng = np.random.default_rng(7)

# Chwile z montażu (sekundy filmu) — trzymać w zgodzie z projects/g1/film.json
HIT_SOFT = [2.03]                 # zacisk na piłce w zwolnionym otwarciu
HIT_BIG = [3.0, 18.2, 29.53, 42.4, 54.5]
RISERS = [(15.6, 18.2), (39.0, 42.0)]
SILENCE = [(42.0, 42.4)]         # oddech przed kulminacją


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def env(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def saw(f, n, harm=14, phase=0.0):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k in range(1, harm + 1):
        if f * k > 9000:
            break
        out += np.sin(2 * np.pi * f * k * t + phase * k) / k
    return out


def place(buf, sig, t0, gain=1.0):
    i = int(t0 * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


L = np.zeros(N)
R = np.zeros(N)

# ---------------------------------------------------------------- pad akordów
CHORDS = {"Dm": [50, 57, 62, 65], "Bb": [46, 58, 62, 65], "F": [41, 57, 60, 65], "C": [48, 55, 60, 64],
          "Gm": [43, 58, 62, 67], "A": [45, 57, 61, 64], "D": [50, 57, 62, 66]}
bar = 4 * BEAT
plan = [  # (start, chord, bars, gain, cutoff)
    (0.0, "Dm", 1.25, 0.10, 700), (3.0, "Dm", 1.0, 0.16, 900),
    (5.5, "Dm", 1, 0.16, 900), (5.5 + bar, "Bb", 1, 0.16, 1000), (5.5 + 2 * bar, "F", 1, 0.17, 1100),
    (5.5 + 3 * bar, "C", 1, 0.18, 1200), (5.5 + 4 * bar, "Dm", 1, 0.19, 1400), (5.5 + 5 * bar, "Bb", 1, 0.2, 1500),
    (5.5 + 6 * bar, "F", 1, 0.2, 1700), (5.5 + 7 * bar, "C", 1, 0.21, 1900), (5.5 + 8 * bar, "Gm", 0.75, 0.2, 2000),
    (30.5, "Dm", 1, 0.2, 2200), (30.5 + bar, "Bb", 1.5, 0.2, 2200),
    (36.5, "F", 1, 0.14, 900), (36.5 + bar, "C", 0.25, 0.16, 1100), (39.0, "A", 1.25, 0.18, 1600),
    (42.4, "Bb", 1, 0.26, 3000), (42.4 + bar, "C", 1, 0.27, 3200), (42.4 + 2 * bar, "Dm", 1, 0.28, 3400),
    (42.4 + 3 * bar, "Bb", 0.85, 0.28, 3400), (54.5, "D", 2.3, 0.26, 2600),
]
for t0, name, bars, g, cut in plan:
    dur = bars * bar
    n = int(dur * SR) + int(0.8 * SR)
    sigL, sigR = np.zeros(n), np.zeros(n)
    for m in CHORDS[name]:
        f = hz(m)
        sigL += saw(f * 1.003, n) + 0.6 * saw(f * 0.997, n, phase=0.7)
        sigR += saw(f * 0.998, n, phase=1.3) + 0.6 * saw(f * 1.004, n, phase=2.1)
    e = env(n, 0.5, 1.1)
    place(L, lp(sigL, cut) * e, t0, g * 0.18)
    place(R, lp(sigR, cut) * e, t0, g * 0.18)

# ---------------------------------------------------------------- puls ósemkowy
def pluck(f, dur=0.32):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t))
    return lp(s * np.exp(-t * 11), 2600)


pulse_sections = [(5.5, 28.0, 0.5, 0.10, 0.22), (28.0, 36.5, 0.25, 0.20, 0.26), (44.5, 54.5, 0.5, 0.24, 0.30)]
seq = [62, 69, 65, 69, 62, 69, 67, 69]
for a, b, step, g0, g1 in pulse_sections:
    t, i = a, 0
    while t < b:
        k = (t - a) / max(b - a, 1e-6)
        g = g0 + (g1 - g0) * k
        p = pluck(hz(seq[i % len(seq)] + 12))
        pan = 0.5 + 0.35 * np.sin(i * 1.7)
        place(L, p, t, g * (1 - pan) * 1.2)
        place(R, p, t, g * pan * 1.2)
        t += step * BEAT * 2
        i += 1

# ---------------------------------------------------------------- bas i serce
def sub(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * f * t) * env(n, 0.02, 0.15)


def kick(level=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 45 + 85 * np.exp(-t * 22)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 7) * level


for t0, name, bars, g, cut in plan:
    if t0 < 15.0 and t0 != 3.0:
        continue
    root = hz(CHORDS[name][0] - 12)
    for b in range(int(bars * 4)):
        place(L, sub(root, BEAT * 0.95), t0 + b * BEAT, 0.20)
        place(R, sub(root, BEAT * 0.95), t0 + b * BEAT, 0.20)
t = 22.0
while t < 54.0:
    if not (36.5 <= t < 42.4):
        place(L, kick(0.5), t, 1)
        place(R, kick(0.5), t, 1)
    t += BEAT * 2 if t < 30.5 else BEAT

# ---------------------------------------------------------------- riser i uderzenia
for a, b in RISERS:
    n = int((b - a) * SR)
    t = np.arange(n) / SR
    k = t / t[-1]
    noise = hp(rng.standard_normal(n), 400) * (k ** 2.2)
    tone = np.sin(2 * np.pi * np.cumsum(180 + 620 * k ** 2) / SR) * (k ** 2)
    sig = lp(noise, 6000) * 0.12 + tone * 0.06
    place(L, sig, a, 1)
    place(R, np.roll(sig, 220), a, 1)


def impact(level=1.0):
    n = int(2.6 * SR)
    t = np.arange(n) / SR
    f = 32 + 110 * np.exp(-t * 9)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.4)
    crack = lp(rng.standard_normal(n), 3500) * np.exp(-t * 14) * 0.5
    return (body + crack) * level


for t0 in HIT_BIG:
    s = impact(0.9)
    place(L, s, t0, 1)
    place(R, s, t0, 1)
for t0 in HIT_SOFT:
    s = impact(0.35)
    place(L, s, t0, 1)
    place(R, s, t0, 1)

# ---------------------------------------------------------------- cisza przed kulminacją
for a, b in SILENCE:
    i, j = int(a * SR), int(b * SR)
    ramp = int(0.04 * SR)
    for ch in (L, R):
        ch[i - ramp:i] *= np.linspace(1, 0, ramp)
        ch[i:j] = 0

# ---------------------------------------------------------------- pogłos, mastering
ir_n = int(2.8 * SR)
ti = np.arange(ir_n) / SR
irL = rng.standard_normal(ir_n) * np.exp(-ti * 2.3)
irR = rng.standard_normal(ir_n) * np.exp(-ti * 2.3)
irL, irR = lp(irL, 5000), lp(irR, 5000)
wetL = fftconvolve(L, irL)[:N] * 0.022
wetR = fftconvolve(R, irR)[:N] * 0.022
outL, outR = L + wetL, R + wetR
fade = int(3.0 * SR)
for ch in (outL, outR):
    ch[-fade:] *= np.linspace(1, 0, fade) ** 1.5
    ch[: int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR))
peak = max(np.abs(outL).max(), np.abs(outR).max())
stereo = np.stack([outL, outR], 1) / peak * 10 ** (-3 / 20)
pcm = (stereo * 32767).astype(np.int16)

out = Path(__file__).resolve().parent / "assets" / "score.wav"
out.parent.mkdir(exist_ok=True)
import wave

with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("OK", out, f"{TOTAL:.0f} s")
