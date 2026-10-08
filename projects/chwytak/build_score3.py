"""Muzyka „Jeden ruch” v3 — rytmiczna, elektroniczna, bez „kościelnego” pogłosu. 110 BPM, d-moll.

Sekcje (czasy filmu z assets/plan2.json):
  tytuł        : samo arpeggio z filtrem + jeden czysty hit
  symulacja    : kick 4/4, hi-hat ósemki, bas, arpeggio 16-tek; budowanie przez otwieranie filtra
  STOP 0,9 s   : cisza + reverse-riser, uderzenie na cięciu sim → robot
  robot        : pełny groove (kick, snare 2 i 4, hat, bas, arpeggio), stab na każdym zacisku
  wstawka sim  : przerwa — drums out, tylko filtrowane arpeggio, krótki riser
  robot 2      : groove wraca mocniej
  STOP 0,8 s   : cisza przed outro, impact na planszy
  outro        : krótkie stabs akordu D-dur + puls wygaszany, hit końcowy

    python projects/chwytak/build_score3.py  -> assets/score3.wav
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
BPM = 110
B = 60 / BPM
rng = np.random.default_rng(11)
L = np.zeros(N)
R = np.zeros(N)

cut_real = plan["split_start"]        # cięcie sim -> robot
end_start = plan["end_start"]         # outro
hits = plan["cuts"]                   # zaciski
SIM_INSERT = (34.23, 37.83)
STOP1 = (cut_real - 0.9, cut_real)
STOP2 = (end_start - 0.8, end_start)


def lp(x, f, o=2):
    return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)


def hp(x, f, o=2):
    return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def place(sig, t0, g=1.0, pan=0.5):
    i = int(t0 * SR)
    if i >= N or i < 0:
        return
    j = min(N, i + len(sig))
    L[i:j] += sig[: j - i] * g * (1 - pan) * 2
    R[i:j] += sig[: j - i] * g * pan * 2


def in_ranges(t, ranges):
    return any(a <= t < b for a, b in ranges)


# ---------------------------------------------------------------- instrumenty
def kick(level=1.0):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 30)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) + lp(rng.standard_normal(n), 2500) * np.exp(-t * 60) * 0.3) * level


def snare(level=1.0):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28)
    noise = hp(rng.standard_normal(n), 1800) * np.exp(-t * 18)
    return (body * 0.5 + noise * 0.6) * level


def hat(level=1.0, open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    return hp(rng.standard_normal(n), 7000) * np.exp(-t * (14 if open_ else 60)) * level * 0.5


def pluck(f, dur=0.22, cut=3000):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sign(np.sin(2 * np.pi * f * t)) * 0.4 + np.sin(2 * np.pi * f * t) * 0.6
    return lp(s * np.exp(-t * 14), cut)


def bass(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + np.sin(2 * np.pi * f * t)
    e = np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.05)
    return lp(s * e, 320)


def stab(freqs, dur=0.5, cut=2800):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = sum(np.sign(np.sin(2 * np.pi * f * t)) * 0.3 + np.sin(2 * np.pi * f * t) for f in freqs)
    return lp(s * np.exp(-t * 6), cut) / len(freqs)


def impact(level=1.0):
    n = int(1.8 * SR)
    t = np.arange(n) / SR
    f = 34 + 120 * np.exp(-t * 10)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.8) + lp(rng.standard_normal(n), 3000) * np.exp(-t * 16) * 0.6) * level


def riser(dur, level=0.14):
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = t / t[-1]
    return hp(rng.standard_normal(n), 500) * (k ** 2.5) * level + np.sin(2 * np.pi * np.cumsum(200 + 900 * k ** 2) / SR) * k ** 2 * level * 0.5


def rev_cymbal(dur, level=0.18):
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = t / t[-1]
    return hp(rng.standard_normal(n), 3000) * (k ** 3) * level


# ---------------------------------------------------------------- harmonia
CH = {"Dm": [62, 65, 69], "Bb": [58, 62, 65], "F": [57, 60, 65], "C": [60, 64, 67], "A": [57, 61, 64], "D": [62, 66, 69]}
ROOT = {"Dm": 38, "Bb": 34, "F": 41, "C": 36, "A": 33, "D": 38}
prog = ["Dm", "Bb", "F", "C"]
bar = 4 * B

silent = [STOP1, STOP2]
no_drums = [(0, cut_real - 4 * B), SIM_INSERT, (end_start, T)]

# siatka 16-tek przez cały film
t = 0.0
step = 0
while t < T:
    if not in_ranges(t, silent) and t < end_start:
        bar_i = int(t // bar)
        chord = prog[bar_i % 4]
        beat_in_bar = (t % bar) / B
        sixteenth = step % 4
        # arpeggio
        notes = CH[chord] + [CH[chord][0] + 12]
        note = notes[step % 4] + (12 if (step // 8) % 2 else 0)
        pre_real = t < cut_real
        if pre_real:
            cut = 600 + 2800 * (t / cut_real) ** 1.6
            g = 0.10 + 0.08 * (t / cut_real)
        elif in_ranges(t, [SIM_INSERT]):
            cut, g = 1200, 0.12
        else:
            cut, g = 3800, 0.17
        place(pluck(hz(note), 0.2, cut), t, g, pan=0.35 if step % 2 else 0.65)
        # bas na ósemkach
        if sixteenth in (0, 2):
            place(bass(hz(ROOT[chord]), B / 2 * 0.9), t, 0.22 if not pre_real else 0.14)
        # perkusja
        if not in_ranges(t, no_drums):
            if sixteenth == 0:
                place(kick(0.85), t, 1)
            if sixteenth == 0 and int(beat_in_bar) in (1, 3):
                place(snare(0.55), t, 1)
            if sixteenth in (0, 2):
                place(hat(0.35 if sixteenth else 0.22, open_=(sixteenth == 2 and int(beat_in_bar) == 3)), t, 1, pan=0.6)
        elif pre_real and t >= 3.0:
            # symulacja: tylko kick co ćwierćnutę od 3 s, hat od połowy
            if sixteenth == 0:
                place(kick(0.6), t, 1)
            if t > cut_real / 2 and sixteenth == 2:
                place(hat(0.2), t, 1, pan=0.6)
    t += B / 4
    step += 1

# stabs akordowe na „jedynkę” taktu w sekcjach robota
t = cut_real
while t < end_start:
    if not in_ranges(t, silent + [SIM_INSERT]):
        chord = prog[int(t // bar) % 4]
        place(stab([hz(m) for m in CH[chord]], 0.5), t, 0.16, pan=0.5)
    t += bar

# zaciski: stab akcentowy + snare
for h in hits:
    if h > 3.5:
        place(stab([hz(74), hz(77), hz(81)], 0.35, 4000), h, 0.22)
        place(snare(0.7), h, 1)

# tytuł: czysty hit
place(impact(0.45), 0.3, 1)
# STOP 1 → reverse cymbal → impact na cięciu
place(rev_cymbal(STOP1[1] - STOP1[0]), STOP1[0], 1)
place(impact(1.0), cut_real, 1)
# wstawka sim: riser do powrotu groove'u
place(riser(SIM_INSERT[1] - SIM_INSERT[0], 0.12), SIM_INSERT[0], 1)
place(impact(0.6), SIM_INSERT[1], 1)
# STOP 2 → impact outro
place(rev_cymbal(STOP2[1] - STOP2[0], 0.14), STOP2[0], 1)
place(impact(1.0), end_start, 1)
# outro: stabs D-dur co pół taktu, coraz ciszej + puls kick
t = end_start + 0.4
k = 0
while t < T - 0.6:
    place(stab([hz(m) for m in CH["D"]], 0.6, 2600), t, 0.2 * (0.85 ** k))
    place(kick(0.4 * (0.85 ** k)), t, 1)
    t += bar / 2
    k += 1
place(impact(0.5), T - 1.4, 1)

# twarda cisza w stopach (poza wybrzmieniem uderzeń z poprzedniej sekcji wygaszamy)
for a, b in silent:
    i, j = int(a * SR), int(b * SR)
    ramp = int(0.03 * SR)
    for ch in (L, R):
        ch[i - ramp:i] *= np.linspace(1, 0, ramp)
        ch[i:j] *= 0.0
# reverse cymbal ma zostać w stopie — dokładamy po wyciszeniu
place(rev_cymbal(STOP1[1] - STOP1[0]), STOP1[0], 1)
place(rev_cymbal(STOP2[1] - STOP2[0], 0.14), STOP2[0], 1)

# krótki pogłos (0,6 s), mastering
ir_n = int(0.6 * SR)
ti = np.arange(ir_n) / SR
for ch in (L, R):
    ir = lp(rng.standard_normal(ir_n) * np.exp(-ti * 9), 6000)
    ch += fftconvolve(ch, ir)[:N] * 0.012
fade = int(0.6 * SR)
L[-fade:] *= np.linspace(1, 0, fade)
R[-fade:] *= np.linspace(1, 0, fade)
peak = max(np.abs(L).max(), np.abs(R).max())
st = np.stack([L, R], 1) / peak * 10 ** (-3 / 20)
out = HERE / "assets" / "score3.wav"
with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
print("OK", out, f"{T:.1f} s")
