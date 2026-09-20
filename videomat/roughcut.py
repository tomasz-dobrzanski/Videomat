"""Rough cut: wykrywanie cisz -> lista ujęć -> render skróconej wersji + EDL (CMX 3600) + FCPXML 1.9.

    r = roughcut("in.mp4", silence_db=-30, min_silence=0.4, pad=0.08, export=("edl","fcpxml"))
    -> {"video": Path, "cuts": Path, "edl": Path, "fcpxml": Path, "kept_s": float, "removed_s": float}

Powtórzone ujęcia (bad takes): gdy podany transcript, kolejne segmenty o podobnym tekście (>0.85)
są oznaczane "review"; usuwane tylko z drop_repeats=True (zostaje ostatnie powtórzenie).
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from . import config, ffmpeg


def detect_silences(src: str | Path, noise_db: float = -30, min_silence: float = 0.4) -> list[tuple[float, float]]:
    cmd = ["ffmpeg", "-hide_banner", "-i", str(src), "-af",
           f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    if len(ends) < len(starts):
        ends.append(ffmpeg.duration(src))
    return list(zip(starts, ends))


def speech_segments(duration: float, silences: list[tuple[float, float]], pad: float = 0.08,
                    min_len: float = 0.3) -> list[dict]:
    segs, cur = [], 0.0
    for s, e in silences:
        a, b = cur, s + pad
        if b - a >= min_len:
            segs.append({"start": round(max(0.0, a), 3), "end": round(min(b, duration), 3)})
        cur = max(e - pad, 0.0)
    if duration - cur >= min_len:
        segs.append({"start": round(cur, 3), "end": round(duration, 3)})
    for s in segs:
        s["keep"] = True
    return segs


def flag_repeats(segs: list[dict], transcript: dict, threshold: float = 0.85) -> None:
    """Dopisz tekst z transkryptu do ujęć i oznacz powtórzenia (poprzednie z pary -> 'review')."""
    words = [w for s in transcript["segments"] for w in s.get("words", [])]
    for s in segs:
        s["text"] = " ".join(w["w"] for w in words if s["start"] <= w["start"] < s["end"])
    for i in range(1, len(segs)):
        a, b = segs[i - 1].get("text", ""), segs[i].get("text", "")
        if a and b and difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold:
            segs[i - 1]["review"] = "repeat_of_next"


def render_cut(src: str | Path, segs: list[dict], out: str | Path) -> Path:
    kept = [s for s in segs if s["keep"]]
    if not kept:
        raise SystemExit("Brak ujęć do zachowania.")
    info = ffmpeg.video_info(src)
    parts, maps = [], ""
    for i, s in enumerate(kept):
        parts.append(f"[0:v]trim=start={s['start']}:end={s['end']},setpts=PTS-STARTPTS[v{i}]")
        if info["has_audio"]:
            parts.append(f"[0:a]atrim=start={s['start']}:end={s['end']},asetpts=PTS-STARTPTS[a{i}]")
        maps += f"[v{i}]" + (f"[a{i}]" if info["has_audio"] else "")
    n = len(kept)
    if info["has_audio"]:
        parts.append(f"{maps}concat=n={n}:v=1:a=1[v][a]")
        args = ["-i", str(src), "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
        args += ffmpeg.encoder_args() + ffmpeg.AUDIO_ARGS
    else:
        parts.append(f"{maps}concat=n={n}:v=1:a=0[v]")
        args = ["-i", str(src), "-filter_complex", ";".join(parts), "-map", "[v]"] + ffmpeg.encoder_args()
    ffmpeg.run(args + ffmpeg.MUX_ARGS + [str(out)])
    return Path(out)


# ------------------------------------------------------------------ NLE export
def _tc(t: float, fps: float) -> str:
    fr = int(round(t * fps))
    f = fr % int(round(fps)); s = fr // int(round(fps))
    return f"{s // 3600:02d}:{(s // 60) % 60:02d}:{s % 60:02d}:{f:02d}"


def write_edl(segs: list[dict], fps: float, src_name: str, out: Path, title: str = "Videomat rough cut") -> Path:
    lines = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]
    rec = 0.0
    for i, s in enumerate((x for x in segs if x["keep"]), 1):
        d = s["end"] - s["start"]
        lines.append(f"{i:03d}  AX       AA/V  C        "
                     f"{_tc(s['start'], fps)} {_tc(s['end'], fps)} {_tc(rec, fps)} {_tc(rec + d, fps)}")
        lines.append(f"* FROM CLIP NAME: {src_name}")
        lines.append("")
        rec += d
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_fcpxml(segs: list[dict], info: dict, src_path: Path, out: Path, title: str = "Videomat rough cut") -> Path:
    fps = info["fps"]
    fr_num = 1001 if abs(fps - round(fps)) > 0.01 else 1000
    fr_den = int(round(fps)) * 1000
    tb = f"{fr_num}/{fr_den}s"                     # np. 1000/30000s = 1/30
    frame = fr_num / fr_den

    def q(t: float) -> str:                        # rational time, wyrównany do klatki
        n = int(round(t / frame))
        return f"{n * fr_num}/{fr_den}s"

    total = sum(s["end"] - s["start"] for s in segs if s["keep"])
    uri = src_path.resolve().as_uri()
    w, h = info["width"], info["height"]
    x = [f'<?xml version="1.0" encoding="UTF-8"?>',
         '<!DOCTYPE fcpxml>',
         '<fcpxml version="1.9">',
         '  <resources>',
         f'    <format id="r1" name="FFVideoFormat{h}p{int(round(fps))}" frameDuration="{tb}" width="{w}" height="{h}"/>',
         f'    <asset id="r2" name="{escape(src_path.name)}" start="0s" duration="{q(info["duration"])}" '
         f'hasVideo="1" hasAudio="{1 if info["has_audio"] else 0}" format="r1">',
         f'      <media-rep kind="original-media" src="{escape(uri)}"/>',
         '    </asset>',
         '  </resources>',
         '  <library>',
         f'    <event name="{escape(title)}">',
         f'      <project name="{escape(title)}">',
         f'        <sequence format="r1" duration="{q(total)}" tcStart="0s" tcFormat="NDF">',
         '          <spine>']
    off = 0.0
    for s in (x for x in segs if x["keep"]):
        d = s["end"] - s["start"]
        x.append(f'            <asset-clip ref="r2" name="{escape(src_path.stem)}" offset="{q(off)}" '
                 f'start="{q(s["start"])}" duration="{q(d)}" format="r1"/>')
        off += d
    x += ['          </spine>', '        </sequence>', '      </project>', '    </event>', '  </library>', '</fcpxml>']
    out.write_text("\n".join(x), encoding="utf-8")
    return out


def roughcut(src: str | Path, silence_db: float = -30, min_silence: float = 0.4, pad: float = 0.08,
             export: tuple[str, ...] = ("edl", "fcpxml"), transcript: dict | None = None,
             drop_repeats: bool = False, render: bool = True) -> dict:
    src = Path(src)
    config.ensure_dirs()
    info = ffmpeg.video_info(src)
    sil = detect_silences(src, silence_db, min_silence)
    segs = speech_segments(info["duration"], sil, pad)
    if transcript:
        flag_repeats(segs, transcript)
        if drop_repeats:
            for s in segs:
                if s.get("review"):
                    s["keep"] = False
    kept = sum(s["end"] - s["start"] for s in segs if s["keep"])
    result = {"segments": len(segs), "kept_s": round(kept, 2), "removed_s": round(info["duration"] - kept, 2)}
    cuts = config.WORK / f"{src.stem}_cuts.json"
    cuts.write_text(json.dumps({"source": str(src), "fps": info["fps"], "segments": segs}, ensure_ascii=False, indent=1), encoding="utf-8")
    result["cuts"] = cuts
    if "edl" in export:
        result["edl"] = write_edl(segs, info["fps"], src.name, config.OUT / f"{src.stem}_cut.edl")
    if "fcpxml" in export:
        result["fcpxml"] = write_fcpxml(segs, info, src, config.OUT / f"{src.stem}_cut.fcpxml")
    if render:
        out = config.next_version_path(config.OUT, src.stem + "_cut")
        result["video"] = render_cut(src, segs, out)
    return result
