"""Muzyka „Jeden ruch” v4 — intro w stylu wielkich syntezatorowych czołówek lat 80. (własna kompozycja, high-tech).

Część 1 (tytuł + symulacja, 80 BPM): głęboki puls basu na każdą ćwierćnutę, dzwonkowy motyw FM w d-moll
(D–A–F–G, co dwa takty), jasny chórowany pad otwierany filtrem, w ostatnich dwóch taktach werbel narasta → STOP →
uderzenie na cięciu do robota.
Część 2 (robot, 120 BPM): napędowy rytm (kick 4/4, werbel 2 i 4, hi-hat), przesterowane syntezatorowe power-chordy
na 1 i 3, bas ósemkowy, lead w oktawach na zaciskach. Wstawka z symulacji = perkusja wypada, wraca motyw dzwonków.
STOP przed outro, impact, outro: akordy D-dur w półnutach + motyw dzwonków, wygaszenie.

    python projects/chwytak/build_score4.py  -> assets/score4.wav
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
rng = np.random.default_rng(5)
L = np.zeros(N)
R = np.zeros(N)
CUT = plan["split_start"]
END = plan["end_start"]
HITS = [h for h in plan["cuts"] if h > CUT]
SIM = (34.23, 37.83)
STOP1 = (CUT - 1.0, CUT)
STOP2 = (END - 0.8, END)


def lp(x, f, o=2):
    return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)


def hp(x, f, o=2):
    return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def place(sig, t0, g=1.0, pan=0.5):
    i = int(t0 * SR)
    if i < 0 or i >= N:
        return
    j = min(N, i + len(sig))
    L[i:j] += sig[: j - i] * g * (1 - pan) * 2
    R[i:j] += sig[: j - i] * g * pan * 2


def within(t, rngs):
    return any(a <= t < b for a, b in rngs)


# ---------------------------------------------------------------- brzmienia
def fm_bell(f, dur=2.2, level=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    idx = 3.0 * np.exp(-t * 3.5)
    s = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * 3.5 * t))
    return s * np.exp(-t * 1.9) * level


def sub_pulse(f, dur=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * f * t) * np.exp(-t * 4.5) * np.minimum(1, t / 0.008)


def chorus_pad(freqs, dur, cut, a=0.6, rel=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for f in freqs:
        for det, ph in ((1.0, 0.0), (1.004, 1.1), (0.996, 2.3)):
            s += np.sign(np.sin(2 * np.pi * f * det * t + ph)) * 0.25 + np.sin(2 * np.pi * f * det * t + ph) * 0.5
    e = np.minimum(1, t / a) * np.minimum(1, (dur - t) / rel)
    return lp(s * e, cut) / (3 * len(freqs))


def power_chord(f, dur=0.45):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = sum(np.sign(np.sin(2 * np.pi * f * m * t)) for m in (1.0, 1.5, 2.0))
    s = np.tanh(s * 1.8)
    return lp(s * np.exp(-t * 5), 3200)


def lead(f, dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + np.sign(np.sin(2 * np.pi * f * 2.0 * t)) * 0.5
    return lp(np.tanh(s * 1.4) * np.exp(-t * 4), 4500)


def bass8(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sign(np.sin(2 * np.pi * f * t)) * 0.6 + np.sin(2 * np.pi * f * t)
    return lp(s * np.minimum(1, t / 0.005) * np.minimum(1, (dur - t) / 0.04), 400)


def kick(level=1.0):
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    f = 48 + 120 * np.exp(-t * 28)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8) + lp(rng.standard_normal(n), 3000) * np.exp(-t * 70) * 0.35) * level


def snare(level=1.0, dur=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 185 * t) * np.exp(-t * 26) * 0.5 + hp(rng.standard_normal(n), 1600) * np.exp(-t * 16) * 0.7) * level


def hat(level=1.0, open_=False):
    n = int((0.2 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    return hp(rng.standard_normal(n), 7500) * np.exp(-t * (12 if open_ else 65)) * level * 0.5


def impact(level=1.0):
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    f = 32 + 130 * np.exp(-t * 9)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6) + lp(rng.standard_normal(n), 3500) * np.exp(-t * 14) * 0.6) * level


def rev_cymbal(dur, level=0.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = t / t[-1]
    return hp(rng.standard_normal(n), 2500) * (k ** 3) * level


# ---------------------------------------------------------------- część 1: intro (80 BPM)
B1 = 60 / 80
bells = [62, 69, 65, 67, 62, 69, 70, 69]           # D A F G D A Bb A
t, k = 0.0, 0
while t < STOP1[0]:
    place(sub_pulse(hz(38 if (k // 8) % 2 == 0 else 34)), t, 0.55)
    if k % 2 == 0:
        place(fm_bell(hz(bells[(k // 2) % len(bells)] + 12), 2.4), t, 0.26, pan=0.4 if (k // 2) % 2 else 0.6)
    t += B1
    k += 1
# pad otwierany filtrem (dwa akordy: Dm, Bb)
pad_len = STOP1[0]
for i, (chord, a, b) in enumerate([([50, 57, 62, 65], 0.0, pad_len / 2), ([46, 58, 62, 65], pad_len / 2, pad_len)]):
    seg = chorus_pad([hz(m) for m in chord], b - a + 0.3, 900 + 2200 * i, a=1.0, rel=0.4)
    place(seg, a, 0.11 + 0.05 * i)
# narastający werbel w ostatnich dwóch taktach
roll_start = STOP1[0] - 2 * 4 * B1
t = roll_start
i = 0
while t < STOP1[0]:
    div = 2 if t < roll_start + 4 * B1 else 4
    place(snare(0.15 + 0.6 * (t - roll_start) / (STOP1[0] - roll_start), 0.18), t, 1)
    t += B1 / div
    i += 1
place(impact(0.5), 0.3, 1)

# ---------------------------------------------------------------- część 2: robot (120 BPM)
B2 = 0.5
bar2 = 4 * B2
prog = [(50, [62, 65, 69]), (46, [58, 62, 65]), (41, [57, 60, 65]), (48, [60, 64, 67])]  # Dm Bb F C
t = CUT
step = 0
while t < END:
    bar_i = int((t - CUT) // bar2)
    root, chord = prog[bar_i % 4]
    beat = step % 8          # ósemki
    in_sim = within(t, [SIM])
    in_stop = within(t, [STOP2])
    if not in_stop:
        if not in_sim:
            if beat % 2 == 0:
                place(kick(0.9), t, 1)
            if beat in (2, 6):
                place(snare(0.65), t, 1)
            place(hat(0.3 if beat % 2 else 0.2, open_=(beat == 7)), t, 1, pan=0.6)
            place(bass8(hz(root - 12), B2 * 0.9), t, 0.3)
            if beat in (0, 4):
                place(power_chord(hz(root)), t, 0.22)
        else:
            if beat % 4 == 0:
                place(fm_bell(hz(chord[(step // 4) % 3] + 12), 1.6), t, 0.22)
            place(sub_pulse(hz(root - 12), 0.5), t, 0.3) if beat % 2 == 0 else None
    t += B2
    step += 1
# lead w oktawach na zaciskach
for h in HITS:
    for i, m in enumerate((74, 81, 86)):
        place(lead(hz(m), 0.6 - 0.1 * i), h + 0.0 + i * 0.0, 0.16 / (1 + i))
    place(snare(0.8), h, 1)
# STOP 1 → impact
place(impact(1.0), CUT, 1)
# wstawka sim: riser + impact przy powrocie
n = int((SIM[1] - SIM[0]) * SR)
kk = np.arange(n) / n
place(hp(rng.standard_normal(n), 600) * kk ** 2.5 * 0.12, SIM[0], 1)
place(impact(0.6), SIM[1], 1)
# STOP 2 → impact outro
place(impact(1.0), END, 1)
# outro: D-dur półnuty + dzwonki
t = END + 0.5
k = 0
while t < T - 0.8:
    place(chorus_pad([hz(m) for m in (50, 57, 62, 66)], 1.2, 2600, a=0.05, rel=0.6), t, 0.16 * (0.85 ** k))
    place(fm_bell(hz([74, 81, 78, 81][k % 4]), 2.0), t, 0.2 * (0.9 ** k), pan=0.4 if k % 2 else 0.6)
    place(kick(0.5 * (0.85 ** k)), t, 1)
    t += 1.0
    k += 1

# ---------------------------------------------------------------- stopy (cisza) + reverse cymbal
for a, b in (STOP1, STOP2):
    i, j = int(a * SR), int(b * SR)
    ramp = int(0.03 * SR)
    for ch in (L, R):
        ch[i - ramp:i] *= np.linspace(1, 0, ramp)
        ch[i:j] = 0
place(rev_cymbal(STOP1[1] - STOP1[0], 0.22), STOP1[0], 1)
place(rev_cymbal(STOP2[1] - STOP2[0], 0.16), STOP2[0], 1)

# krótki pogłos, mastering
ir_n = int(0.9 * SR)
ti = np.arange(ir_n) / SR
for ch in (L, R):
    ir = lp(rng.standard_normal(ir_n) * np.exp(-ti * 6), 6500)
    ch += fftconvolve(ch, ir)[:N] * 0.016
fade = int(0.8 * SR)
L[-fade:] *= np.linspace(1, 0, fade)
R[-fade:] *= np.linspace(1, 0, fade)
peak = max(np.abs(L).max(), np.abs(R).max())
st = np.stack([L, R], 1) / peak * 10 ** (-3 / 20)
out = HERE / "assets" / "score4.wav"
with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
print("OK", out, f"{T:.1f} s")
