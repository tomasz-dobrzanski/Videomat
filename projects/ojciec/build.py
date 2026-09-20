"""OJCIEC CHRZESTNY SCHRÖDINGERA — cinematic cut 9:16 (v2: pełne nagrania, napisy karaoke, agent-analityk).

Uruchomienie (z katalogu Videomat):
    python projects/ojciec/build.py            # pełny build (lektor + agent + SFX z ElevenLabs, jeśli klucz w .env)
    python projects/ojciec/build.py --no-audio # tylko wizualia (podgląd)

Zasady: cytaty na ekranie = dosłowne słowa z transkrypcji (whisper medium) zsynchronizowane słowo po słowie
(karaoke \\kf z realnych czasów słów). Klipy studyjne kadrowane tak, by usunąć logo i numer telefonu stacji.
Fakt "41 z 41 posłów Rozwój Plus ZA Horałą / PRZECIW Ociepie, w tym Morawiecki" — ze zrzutu listy głosowań od użytkownika.
Wyniki 254/167 z 18.09.2026 potwierdzone w prasie. Daty poszczególnych nagrań nieznane -> brak dat na ekranie.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from videomat import chunker, config, ffmpeg  # noqa: E402
chunker.MAX_WORDS = 4   # duże napisy: krótsze frazy

MP4 = ROOT / "mp4"
C1 = MP4 / "signal-2026-09-18-13-01-35-138-1.mp4"     # konferencja plenerowa 332x640
C2 = MP4 / "signal-2026-09-18-13-01-35-138-2.mp4"     # studio, plan szeroki 640x360
C3 = MP4 / "signal-2026-09-18-13-01-35-138.mp4"       # studio, zbliżenie 540x640
TR = {C1: ROOT / "work" / "signal-2026-09-18-13-01-35-138-1_transcript.json",
      C2: ROOT / "work" / "signal-2026-09-18-13-01-35-138-2_transcript.json",
      C3: ROOT / "work" / "signal-2026-09-18-13-01-35-138_transcript.json"}
CROP = {C1: None, C2: "crop=250:150:180:40", C3: "crop=540:520:0:0"}
FIX = {"wicomarszałka,": "wicemarszałka,", "8": "8", "-9": "-9"}   # oczywiste błędy ASR

WORK = ROOT / "work" / "ojciec"
W, H, FPS = 1080, 1920, 30
SERIF, SANS = "Cambria", "Rajdhani SemiBold"
GOLD, GREY, WHITE, CYAN = "&H0000D9FF", "&H009F9F9F", "&H00FFFFFF", "&H00FFE500"
NO_AUDIO = "--no-audio" in sys.argv

# ---- lektor (Brian) i agent-analityk (Daniel)
VO = {
    "vo1": "U słynnego Ojca Chrzestnego, Vito Corleone, zdrada była zwrotem akcji.",
    "vo2": "Tutaj zwrot akcji zaczął się już w napisach początkowych.",
    "vo3": "Kilka tygodni później Rozwój Plus wystawia własnego kandydata.",
    "vo4": "I to on zostaje wicemarszałkiem.",
    "vo7": "Morawiecki i cały jego klub głosują przeciw Marcinowi Ociepie.",
    "vo8": "Obiecał głos. Zagłosował przeciw.",
    "vo5": "Fizycy mają kota Schrödingera.",
    "vo6": "Polityka dostała właśnie ojca chrzestnego Schrödingera.",
}
AGENT: dict = {}   # drugi głos usunięty — jeden lektor w całym filmie
FALLBACK = {"vo1": 4.4, "vo2": 2.9, "vo3": 3.8, "vo4": 1.9, "vo7": 3.6, "vo8": 2.2, "vo5": 1.9, "vo6": 2.9}
VOICE_ORDER = [config.env("ELEVENLABS_VOICE_ID"), "Jon", "Harrison", "Brian", "Daniel"]
TTS_KW = dict(model_id="eleven_v3", timestamps=False, stability=0.5, similarity=0.84, speed=1.15)
SPEED_UP = 1.18   # tempo mowy po TTS (atempo), bo v3 nie reaguje na speed

# ---- nagrania: lista zakresów (start, koniec) na nagranie + etykieta (skróty wg wskazań użytkownika)
RECORDINGS = [
    (C1, [(0.05, 5.70), (15.70, 18.60)], "NAGRANIE 1"),   # "...kandydatury na wicemarszałka" + "Marcin trzymaj się, będziemy głosować oczywiście za tobą"
    (C2, [(0.00, 8.42), (13.95, 18.55)], "NAGRANIE 2"),   # "...bezpośrednia odpowiedź" + "Także Marcin, trzymaj się, duża szansa, że zostaniesz wybrany"
    (C3, [(5.15, 5.95)], "NAGRANIE 3"),                   # zbliżenie: "masz mój głos"
]
USER_MUSIC = MP4 / "The Godfather - Main Title (The Godfather Waltz) - HQ - Nino Rota [PPskYVBqdNw].mp3"
USER_MUSIC_DB = -10.5   # ~30% głośności (plik ma -13,3 LUFS)

ENC = ffmpeg.encoder_args(19) + ["-r", str(FPS)] + ffmpeg.AUDIO_ARGS
FIT = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
       f"gblur=sigma=30,eq=brightness=-0.12:saturation=0.5[bg];"
       f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,"
       f"eq=contrast=1.10:saturation=0.85:gamma=0.97,noise=alls=7:allf=t,vignette=PI/4.5,setsar=1")
GRADE_STILL = "eq=contrast=1.10:saturation=0.85:gamma=0.97,noise=alls=7:allf=t,vignette=PI/4.5,setsar=1"


# ------------------------------------------------------------------ ASS helpers
def ts(s):
    cs = max(0, int(round(s * 100)))
    h, r = divmod(cs, 360000); m, r = divmod(r, 6000); sec, c = divmod(r, 100)
    return f"{h}:{m:02d}:{sec:02d}.{c:02d}"


def D(layer, a, b, style, text):
    return f"Dialogue: {layer},{ts(a)},{ts(b)},{style},,0,0,0,{text}"


def esc(t):
    return t.replace("{", "(").replace("}", ")")


def ass(path, events):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{SERIF},96,{WHITE},{WHITE},&H00000000,&H00000000,0,0,0,0,100,100,14,0,1,0,0,5,60,60,0,1
Style: Sub,{SANS},58,{WHITE},{WHITE},&H00000000,&H00000000,0,0,0,0,100,100,6,0,1,3,0,5,60,60,0,1
Style: Quote,{SANS},96,{GOLD},{WHITE},&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,70,70,0,1
Style: Stamp,{SANS},46,{GOLD},{GOLD},&H00101010,&H00000000,-1,0,0,0,100,100,8,0,1,3,0,5,40,40,0,1
Style: Board,{SANS},60,{WHITE},{WHITE},&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,0,0,7,60,60,0,1
Style: Hud,Consolas,40,{CYAN},{CYAN},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,60,60,0,1
Style: Narr,{SANS},72,{GOLD},{WHITE},&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Text
"""
    Path(path).write_text(head + "\n".join(events) + "\n", encoding="utf-8")
    return ffmpeg.escape_filter_path(path)


def karaoke_events(src: Path, a: float, b: float) -> list[str]:
    """Napisy słowo-po-słowie: frazy z chunkera, \\kf z realnych czasów słów (Primary=złoto po wypowiedzeniu)."""
    tr = json.loads(TR[src].read_text(encoding="utf-8"))
    words = [dict(w, w=FIX.get(w["w"], w["w"])) for s in tr["segments"] for w in s["words"]
             if a - 0.05 <= w["start"] < b]
    for w in words:
        w["start"], w["end"] = max(0.0, w["start"] - a), min(b - a, w["end"] - a)
    words = [w for w in words if w["w"]]
    chunks = chunker.chunk_words(words)
    # przypisanie słów do fraz sekwencyjnie (po liczbie słów w tekście frazy) — bez podwójnych przypisań
    groups, pos = [], 0
    for ch in chunks:
        n = len(ch["text"].split())
        groups.append(words[pos:pos + n]); pos += n
    if pos < len(words) and groups:
        groups[-1] += words[pos:]
    return kara_from_groups(groups, 1560, "Quote")


def kara_from_groups(groups, y, style, offset=0.0, layer=0):
    ev = []
    for gi, cw in enumerate(groups):
        if not cw:
            continue
        body = ""
        for i, w in enumerate(cw):
            nxt = cw[i + 1]["start"] if i + 1 < len(cw) else w["end"]
            dur_cs = max(int(round((nxt - w["start"]) * 100)), 8)
            body += f"{{\\kf{dur_cs}}}{esc(w['w'])} "
        text = re.sub(r"[.]+$", "", body.strip())
        end = cw[-1]["end"] + 0.25
        if gi + 1 < len(groups) and groups[gi + 1]:
            end = min(end, groups[gi + 1][0]["start"] - 0.02)   # nigdy nie nachodzi na następną frazę
        end = max(end, cw[-1]["end"] - 0.02)
        ev.append(D(layer, offset + cw[0]["start"], offset + end, style, rf"{{\an2\pos(540,{y})\fad(50,40)}}" + text))
    return ev


_WM = None


def align_vo(k: str, wav: Path, text: str) -> list[dict]:
    """Czasy słów lektora: whisper (word_timestamps) na pliku TTS; tekst na ekranie = tekst skryptu."""
    global _WM
    cache = WORK / f"{k}_words.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    from faster_whisper import WhisperModel
    if _WM is None:
        _WM = WhisperModel("medium", device="cuda", compute_type="float16")
    segs, _ = _WM.transcribe(str(wav), language="pl", word_timestamps=True, vad_filter=False, beam_size=5)
    ww = [(w.word.strip(), float(w.start), float(w.end)) for s in segs for w in (s.words or [])]
    script = text.split()
    if ww and len(ww) == len(script):
        words = [{"w": script[i], "start": round(ww[i][1], 2), "end": round(ww[i][2], 2)} for i in range(len(ww))]
    else:  # liczba słów się nie zgadza -> rozkład proporcjonalny do długości słów w przedziale mowy
        t0 = ww[0][1] if ww else 0.0
        t1 = ww[-1][2] if ww else ffmpeg.duration(wav)
        total = sum(len(s) for s in script) or 1
        words, t = [], t0
        for s in script:
            dur = (t1 - t0) * len(s) / total
            words.append({"w": s, "start": round(t, 2), "end": round(t + dur, 2)}); t += dur
    cache.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words


def narr_events(k: str, sp: dict, t0: float, y: int = 1500) -> list[str]:
    """Napisy karaoke pod lektorem (styl Narr), start w t0 wewnątrz segmentu."""
    path = sp[k][0]
    if not path:
        return []
    words = align_vo(k, path, VO[k])
    chunks = chunker.chunk_words([dict(w) for w in words])
    groups, pos = [], 0
    for ch in chunks:
        n = len(ch["text"].split()); groups.append(words[pos:pos + n]); pos += n
    if pos < len(words) and groups:
        groups[-1] += words[pos:]
    return kara_from_groups(groups, y, "Narr", offset=t0, layer=3)


HEADLINES = ["OBIETNICA.", "ZAPEWNIENIE.", "SŁOWO."]


def HEADLINE(word, a, b, y, size=150):
    """Wielki nagłówek serif z szybkim pop-in i cieniem, czytelny na kadrze."""
    return D(2, a, b, "Title",
             rf"{{\an5\pos(540,{y})\fs{size}\fsp8\b1\bord4\3c&H000000&\shad0\fad(60,80)"
             rf"\fscx70\fscy70\t(0,120,\fscx108\fscy108)\t(120,190,\fscx100\fscy100)}}" + word)


# ------------------------------------------------------------------ render helpers
def black(dur, subs, out):
    ffmpeg.run(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={dur:.3f}",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{dur:.3f}",
                "-vf", f"ass='{subs}',noise=alls=5:allf=t,vignette=PI/5", "-shortest"] + ENC + [str(out)])


def clipseg(src, a, b, subs, out):
    fit = (CROP[src] + "," if CROP[src] else "") + FIT
    ffmpeg.run(["-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src), "-filter_complex", fit + f",ass='{subs}'",
                "-af", "aformat=sample_rates=48000:channel_layouts=stereo"] + ENC + [str(out)])


def freeze(src, t, dur, subs, out, zoom=False):
    png = WORK / (Path(out).stem + ".png")
    fit = (CROP[src] + "," if CROP[src] else "") + FIT
    ffmpeg.run(["-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", "-filter_complex", fit, str(png)])
    vf = GRADE_STILL
    if zoom:
        vf = (f"scale=8000:-1,zoompan=z='min(zoom+0.0009,1.25)':d={int(dur * FPS)}:x='iw/2-(iw/zoom/2)':"
              f"y='ih/2.6-(ih/zoom/2)':s={W}x{H}:fps={FPS}," + GRADE_STILL)
    ffmpeg.run(["-loop", "1", "-t", f"{dur:.3f}", "-i", str(png), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-t", f"{dur:.3f}", "-vf", f"{vf},ass='{subs}'", "-shortest"] + ENC + [str(out)])


# ------------------------------------------------------------------ audio (ElevenLabs)
def pick_voice(order, probe_key, lines):
    from videomat.elevenlabs_client import list_voices
    from videomat.tts import tts
    voices = list_voices()
    cands = []
    for name in order:
        if not name:
            continue
        for v in voices:
            if (name.lower() in (v["name"] or "").lower() or name == v["voice_id"]) and v["voice_id"] not in [c[0] for c in cands]:
                cands.append((v["voice_id"], v["name"]))
    for cid, cname in cands:
        p = WORK / f"{probe_key}.mp3"
        try:
            if p.exists():
                p.unlink()
            tts(lines[probe_key], p, voice_id=cid, **TTS_KW)
            print("voice:", cname)
            return cid
        except Exception as e:
            print(f"! '{cname}' odrzucony: {str(e)[:100]}")
    raise SystemExit("Żaden głos nie zadziałał.")


def make_speech() -> dict[str, tuple[Path | None, float]]:
    res = {k: (None, FALLBACK[k]) for k in list(VO) + list(AGENT)}
    if NO_AUDIO or not config.env("ELEVENLABS_API_KEY"):
        print("! Bez audio API: czasy z fallbacku.")
        return res
    from videomat.tts import tts
    def fast(p: Path) -> Path:
        # eleven_v3 ignoruje `speed` -> przyspieszenie tempa bez zmiany wysokości (atempo), + przycięcie ciszy na końcach
        out = p.with_name(p.stem + "_fast.wav")
        if not out.exists():
            ffmpeg.run(["-i", str(p), "-af", f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
                        f"areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,"
                        f"atempo={SPEED_UP}", "-ar", "48000", "-ac", "2", str(out)])
        return out

    done = (WORK / "speech_done.json")
    if not (done.exists() and all((WORK / f"{k}.mp3").exists() for k in res)):
        used = WORK / "voice_used.txt"
        vid = used.read_text().strip() if used.exists() and (WORK / "vo1.mp3").exists() else pick_voice(VOICE_ORDER, "vo1", VO)
        used.write_text(vid)
        for k, line in VO.items():
            p = WORK / f"{k}.mp3"
            if not p.exists():
                tts(line, p, voice_id=vid, **TTS_KW)
        done.write_text("{}", encoding="utf-8")
    for k in res:
        f = fast(WORK / f"{k}.mp3")
        res[k] = (f, ffmpeg.duration(f))
    for k, v in res.items():
        print(f"{k}: {v[1]:.2f}s")
    return res


def sfx_file(name, prompt, dur, loop=False):
    p = WORK / f"{name}.mp3"
    if p.exists():
        return p
    if NO_AUDIO or not config.env("ELEVENLABS_API_KEY"):
        return None
    try:
        from videomat.music import sfx
        return sfx(prompt, p, duration_s=dur, loop=loop, prompt_influence=0.45)
    except Exception as e:
        print(f"! SFX {name}: {str(e)[:100]}")
        return None


# ------------------------------------------------------------------ build
def main():
    config.ensure_dirs()
    WORK.mkdir(parents=True, exist_ok=True)
    sp = make_speech()
    d = {k: v[1] for k, v in sp.items()}
    segs, t, marks = [], 0.0, {}

    def add(path, dur):
        nonlocal t
        segs.append(path); t += dur

    # S1 cold open
    s1 = max(2.6, d["vo1"] + 0.3)
    e = [D(0, 0.35, s1, "Title", r"{\an5\pos(540,880)\fs104\fsp18\fad(600,300)}OJCIEC CHRZESTNY"),
         D(0, 0.85, s1, "Sub", r"{\an5\pos(540,1040)\fs54\fsp14\fad(300,250)\c&H9F9F9F&}POLSKA. 2026.")]
    marks["vo1"] = 0.45; marks["hit"] = 0.0
    e += narr_events("vo1", sp, 0.45, 1500)
    p = WORK / "s1.mp4"; black(s1, ass(WORK / "s1.ass", e), p); add(p, s1)

    # S2 trzy nagrania w całości, napisy karaoke
    FRZ = 0.55
    for i, (src, ranges, label) in enumerate(RECORDINGS, 1):
        for j, (a, b) in enumerate(ranges):
            dur = b - a
            e = karaoke_events(src, a, b)
            e.append(D(1, 0.0 if j else 0.2, dur, "Stamp", r"{\an9\pos(1030,150)\fs40}OJCIEC CHRZESTNY \N{\an9\fs78\b1}x" + str(i)))
            p = WORK / f"s2_q{i}_{j}.mp4"; clipseg(src, a, b, ass(WORK / f"s2_q{i}_{j}.ass", e), p); add(p, dur)
        b = ranges[-1][1]
        if i < 3:
            # freeze: wielki nagłówek serif + stempel nagrania
            f = [HEADLINE(HEADLINES[i - 1], 0.0, FRZ, 900),
                 D(1, 0.0, FRZ, "Stamp", r"{\an5\pos(540,1700)\fs44\fsp10\fad(80,0)}" + label + "  ·  ZAREJESTROWANO")]
            p = WORK / f"s2_f{i}.mp4"; freeze(src, b - 0.05, FRZ, ass(WORK / f"s2_f{i}.ass", f), p); add(p, FRZ)
    marks["music_cut"] = t; marks["stinger"] = t - 0.15
    # freeze na "masz mój głos" + cisza na czerni
    f = [HEADLINE(HEADLINES[2], 0.0, 0.9, 900),
         D(1, 0.0, 0.9, "Stamp", r"{\an5\pos(540,1700)\fs44\fsp10\fad(80,0)}NAGRANIE 3  ·  ZAREJESTROWANO")]
    p = WORK / "s2_f3.mp4"; freeze(C3, 5.9, 0.9, ass(WORK / "s2_f3.ass", f), p); add(p, 0.9)
    p = WORK / "s2_silence.mp4"; black(0.6, ass(WORK / "s2_silence.ass", []), p); add(p, 0.6)

    # S3 zwrot
    s3 = max(3.4, d["vo2"] + 0.4)
    w0, step = 0.5, max(0.55, (s3 - 0.5 - 0.3) / 3)
    e = [D(0, w0 + i * step, s3, "Title", rf"{{\an5\pos(540,{760 + i * 190})\fs88\fsp12\fad(120,200)\fscx90\fscy90\t(0,180,\fscx100\fscy100)}}" + wd)
         for i, wd in enumerate(["POPARCIE.", "KONTRKANDYDAT.", "GŁOSOWANIE."])]
    marks["vo2"] = t + 0.3; marks["music_resume"] = t
    e += narr_events("vo2", sp, 0.3, 1500)
    p = WORK / "s3.mp4"; black(s3, ass(WORK / "s3.ass", e), p); add(p, s3)

    # S4 fakty: 41 z 41
    s4 = max(4.5, d["vo3"] + 0.25 + d["vo4"] + 0.4)
    e = [D(0, 0.2, s4, "Stamp", r"{\an7\pos(80,570)\fs36\fsp4\fad(150,200)}18.09.2026  ·  WYBÓR WICEMARSZAŁKA SEJMU")]
    for i in range(41):
        r_, c_ = divmod(i, 14); x, y = 80 + c_ * 70, 660 + r_ * 70
        e.append(D(0, 0.4 + i * 0.03, s4, "Board",
                   rf"{{\an7\pos({x},{y})\1c{GOLD}&\bord0\shad0\fscx40\fscy40\t(0,120,\fscx100\fscy100)\fad(60,200)\p1}}m 0 0 l 56 0 l 56 56 l 0 56{{\p0}}"))
    tt = 0.4 + 41 * 0.03 + 0.15
    e += [D(0, tt, s4, "Board", rf"{{\an7\pos(80,920)\fs110\b1\c{GOLD}&\fad(150,200)}}41 {{\fs60\b0\c&HFFFFFF&}}z 41"),
          D(0, tt + 0.3, s4, "Board", r"{\an7\pos(80,1060)\fs58\fad(150,200)}posłów Rozwój Plus\N{\c&H00D9FF&}ZA{\c&HFFFFFF&} Horałą · {\c&H9F9F9F&}PRZECIW{\c&HFFFFFF&} Ociepie")]
    marks["vo3"] = t + 0.35; marks["vo4"] = t + 0.35 + d["vo3"] + 0.25
    e += narr_events("vo3", sp, 0.35, 1500) + narr_events("vo4", sp, 0.35 + d["vo3"] + 0.25, 1500)
    p = WORK / "s4.mp4"; black(s4, ass(WORK / "s4.ass", e), p); add(p, s4)

    # S5 TWIST — jeden punkt: wiersz Morawieckiego z listy głosowań + ZDRADA + lektor
    t_vo7 = 0.3
    t_zdr = t_vo7 + d["vo7"] + 0.15
    t_vo8 = t_zdr + 0.5
    s5 = t_vo8 + d["vo8"] + 0.8
    e = [D(0, 0.0, s5, "Board", r"{\an7\pos(0,0)\1c&H0A0A0A&\bord0\shad0\p1}m 0 0 l 1080 0 l 1080 1920 l 0 1920{\p0}"),
         D(1, 0.1, s5, "Stamp", r"{\an7\pos(80,600)\fs36\fsp4\fad(100,0)}18.09.2026  ·  LISTA GŁOSOWAŃ  ·  ROZWÓJ PLUS"),
         # wiersz z listy głosowań (jak na sejm.gov.pl)
         D(1, 0.5, s5, "Board", r"{\an7\pos(80,700)\fs32\c&H9F9F9F&\fad(150,0)}Lp."),
         D(1, 0.5, s5, "Board", r"{\an7\pos(160,700)\fs32\c&H9F9F9F&\fad(150,0)}Nazwisko i imię"),
         D(1, 0.5, s5, "Board", r"{\an8\pos(700,700)\fs32\c&H9F9F9F&\fad(150,0)}HORAŁA"),
         D(1, 0.5, s5, "Board", r"{\an8\pos(920,700)\fs32\c&H9F9F9F&\fad(150,0)}OCIEPA"),
         D(1, 0.5, s5, "Board", rf"{{\an7\pos(80,745)\1c{GOLD}&\bord0\shad0\fad(150,0)\p1}}m 0 0 l 920 0 l 920 3 l 0 3{{\p0}}"),
         D(1, 0.8, s5, "Board", r"{\an7\pos(80,770)\fs44\fad(150,0)}25."),
         D(1, 0.8, s5, "Board", r"{\an7\pos(160,770)\fs44\fad(150,0)}Morawiecki Mateusz"),
         D(1, 1.5, s5, "Board", rf"{{\an8\pos(700,765)\fs50\b1\c{GOLD}&\fad(150,0)\fscx60\fscy60\t(0,150,\fscx100\fscy100)}}Za"),
         D(1, 2.2, s5, "Board", r"{\an8\pos(920,765)\fs50\b1\c&H9F9F9F&\fad(150,0)\fscx60\fscy60\t(0,150,\fscx100\fscy100)}Przeciw"),
         D(1, 2.9, s5, "Board", r"{\an7\pos(80,850)\fs40\c&H9F9F9F&\fad(150,0)}+ 40 pozostałych posłów klubu: identycznie"),
         HEADLINE("ZDRADA.", t_zdr, s5, 1150, size=170)]
    e += narr_events("vo7", sp, t_vo7, 1560) + narr_events("vo8", sp, t_vo8, 1560)
    marks["vo7"], marks["vo8"], marks["stinger2"] = t + t_vo7, t + t_vo8, t + t_zdr
    p = WORK / "s5.mp4"; black(s5, ass(WORK / "s5.ass", e), p); add(p, s5)

    # S6 puenta — zoom na zatrzymaną klatkę zbliżenia
    s6 = max(4.2, d["vo5"] + 0.3 + d["vo6"] + 1.1)
    t_title = d["vo5"] + 0.3 + max(0.5, d["vo6"] * 0.5)
    panel = r"{\an7\pos(0,1100)\1c&H000000&\1a&H40&\bord0\shad0\fad(250,300)\p1}m 0 0 l 1080 0 l 1080 820 l 0 820{\p0}"
    e = [D(0, t_title, s6, "Title", panel),
         D(1, t_title, s6, "Title", r"{\an5\pos(540,1290)\fs84\fsp10\fad(250,300)\bord2\3c&H000000&}OJCIEC CHRZESTNY\NSCHRÖDINGERA"),
         D(1, t_title + 0.5, s6, "Sub", r"{\an5\pos(540,1560)\fs52\fsp4\fad(250,300)\bord2\c&HD0D0D0&}Poparcie istnieje.\NDopóki nie otworzysz urny.")]
    marks["vo5"] = t + 0.3; marks["vo6"] = t + 0.3 + d["vo5"] + 0.3; marks["music_end"] = t + s6
    e += narr_events("vo5", sp, 0.3, 360) + narr_events("vo6", sp, 0.3 + d["vo5"] + 0.3, 360)
    p = WORK / "s6.mp4"; freeze(C3, 5.9, s6, ass(WORK / "s6.ass", e), p, zoom=True); add(p, s6)

    # S7 wyjście: czerń, "masz mój głos" jeszcze raz, cięcie do czerni. Bez dat.
    p = WORK / "s7_black.mp4"; black(0.4, ass(WORK / "s7_black.ass", []), p); add(p, 0.4)
    e = karaoke_events(C3, 5.15, 5.95)
    p = WORK / "s7_clip.mp4"; clipseg(C3, 5.15, 5.95, ass(WORK / "s7_clip.ass", e), p); add(p, 0.8)
    p = WORK / "s7_end.mp4"; black(1.2, ass(WORK / "s7_end.ass", []), p); add(p, 1.2)
    total = t

    # --- concat wideo
    lst = WORK / "list.txt"
    lst.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    base = WORK / "base.mp4"
    ffmpeg.run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)])

    # --- audio: oryginał + SFX + mowa + podkład (SFX loop) z cięciem
    hit = sfx_file("sfx_hit", "single deep cinematic bass drum hit with long dark reverb tail", 2.0)
    stinger = sfx_file("stinger", "sudden abrupt dark orchestral stinger hit with tape stop, short", 1.5)
    if USER_MUSIC.exists():
        under, under_db = USER_MUSIC, USER_MUSIC_DB      # podkład od użytkownika, ~30%
    else:
        under, under_db = sfx_file("underscore_loop", "slow dark cinematic underscore, low string drone, distant sparse piano notes, "
                                   "tense 1970s mafia film atmosphere, seamless loop, instrumental, no drums", 22.0, loop=True), -6.0
    inputs, fc, mix, idx = ["-i", str(base)], ["[0:a]volume=1.0[base]"], ["[base]"], 1

    def add_audio(path, at, vol_db, label, loop=False, trim=None, fades=""):
        nonlocal idx
        if not path:
            return
        pre = ["-stream_loop", "-1"] if loop else []
        inputs.extend(pre + ["-i", str(path)])
        ms = int(at * 1000)
        chain = f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo"
        if trim:
            chain += f",atrim=0:{trim:.3f},asetpts=PTS-STARTPTS"
        chain += f",volume={vol_db}dB{fades},adelay={ms}|{ms}[{label}]"
        fc.append(chain); mix.append(f"[{label}]"); idx += 1

    add_audio(hit, marks["hit"], 3.0, "hit")
    add_audio(stinger, marks["stinger"], 0.0, "st1")
    add_audio(stinger, marks["stinger2"], -2.0, "st2")
    for k in list(VO) + list(AGENT):
        path = sp[k][0]
        if path:
            add_audio(path, marks[k], 3.5 if k in VO else 1.5, k)
    if under:
        mc, mr, me = marks["music_cut"], marks["music_resume"], marks["music_end"]
        add_audio(under, 0.0, under_db, "m1", loop=True, trim=mc,
                  fades=f",volume='if(lt(t,{s1:.2f}),1.0,0.6)':eval=frame,afade=t=in:d=0.4")
        add_audio(under, mr, under_db - 3.0, "m2", loop=True, trim=me - mr,
                  fades=f",afade=t=in:d=0.8,afade=t=out:st={me - mr - 1.8:.3f}:d=1.8")
    fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,alimiter=limit=0.95[aout]")
    out = config.next_version_path(config.OUT, "ojciec_chrzestny" + ("_noVO" if not sp["vo1"][0] else ""))
    ffmpeg.run(inputs + ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[aout]", "-c:v", "copy"]
               + ffmpeg.AUDIO_ARGS + ffmpeg.MUX_ARGS + [str(out)])
    (WORK / "marks.json").write_text(json.dumps({"total": total, "marks": marks, "speech": d}, indent=1), encoding="utf-8")
    print(f"OK {out}  ({total:.1f} s)")


if __name__ == "__main__":
    main()
