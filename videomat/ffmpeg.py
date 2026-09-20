"""Cienka warstwa nad ffmpeg/ffprobe: uruchamianie, sondowanie, argumenty enkodera, filtry fit 9:16."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import config

W, H = 1080, 1920


class FFmpegError(RuntimeError):
    pass


# Podpięcia dla kolejki zadań: pozwalają zabić trwający proces i pokazać postęp.
# Gdy nie ustawione, run() zachowuje się dokładnie jak wcześniej (subprocess.run).
_process_hook = None
_progress_hook = None


def set_hooks(process=None, progress=None) -> None:
    """process(popen) — rejestracja procesu do anulowania; progress(sekundy) — postęp renderu."""
    global _process_hook, _progress_hook
    _process_hook, _progress_hook = process, progress


def run(args: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-y", "-hide_banner"] + (["-v", "error"] if quiet else [])
    if _process_hook or _progress_hook:
        cmd += ["-progress", "pipe:1", "-nostats"]
    cmd += args
    if not (_process_hook or _progress_hook):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise FFmpegError("ffmpeg failed:\n" + " ".join(cmd)[:600] + "\n" + r.stderr[-2000:])
        return r

    import threading
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    if _process_hook:
        _process_hook(proc)
    errors: list[str] = []

    def drain() -> None:
        for line in proc.stderr:  # type: ignore[union-attr]
            errors.append(line)
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    for line in proc.stdout:  # type: ignore[union-attr]
        if _progress_hook and line.startswith("out_time_ms="):
            value = line.strip().split("=", 1)[1]
            if value.isdigit():
                _progress_hook(int(value) / 1_000_000)
    proc.wait()
    reader.join(timeout=2)
    if proc.returncode != 0:
        tail = "".join(errors)[-2000:]
        raise FFmpegError("ffmpeg failed:\n" + " ".join(cmd)[:600] + "\n" + tail)
    return subprocess.CompletedProcess(cmd, 0, "", "".join(errors))


def probe(path: str | Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise FFmpegError(r.stderr)
    return json.loads(r.stdout)


def video_info(path: str | Path) -> dict:
    p = probe(path)
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in p["streams"] if s["codec_type"] == "audio"), None)
    fps = 30.0
    if v and v.get("r_frame_rate"):
        num, _, den = v["r_frame_rate"].partition("/")
        fps = float(num) / float(den or 1)
    return {
        "width": int(v["width"]) if v else 0,
        "height": int(v["height"]) if v else 0,
        "fps": fps,
        "duration": float(p["format"].get("duration", 0)),
        "has_audio": a is not None,
        "audio_codec": a.get("codec_name") if a else None,
    }


def duration(path: str | Path) -> float:
    return video_info(path)["duration"]


def escape_filter_path(p: str | Path) -> str:
    """Ścieżka Windows do użycia wewnątrz filtergraph: C\:/dir/file.ass, bez spacji-problemów w cudzysłowach."""
    s = str(Path(p).resolve()).replace("\\", "/")
    s = s.replace(":", "\:")
    s = s.replace("'", "\'")
    return s


def encoder_args(quality: int = 19) -> list[str]:
    if config.encoder() == "nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(quality),
                "-b:v", "0", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "fast", "-crf", str(quality), "-pix_fmt", "yuv420p"]


AUDIO_ARGS = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
MUX_ARGS = ["-movflags", "+faststart"]


def fit_filter(fit: str) -> str:
    """Filtr doprowadzający obraz do 1080x1920. none = brak; crop = center-crop; pad = rozmyte tło."""
    if fit == "none":
        return ""
    if fit == "crop":
        return f"crop=ih*9/16:ih,scale={W}:{H},setsar=1"
    if fit == "pad":
        return (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"gblur=sigma=25[bg];[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    raise ValueError(f"Nieznany fit: {fit} (none|crop|pad)")


def ass_filter(subs: str | Path) -> str:
    return f"ass='{escape_filter_path(subs)}':fontsdir='{escape_filter_path(config.FONTS)}'"


def render_with_subs(src: str | Path, subs: str | Path | None, out: str | Path, fit: str = "none",
                     extra_vf: str = "") -> Path:
    """Wypala .ass (opcjonalnie) i dopasowuje do 9:16. Zawsze nowy plik wyjściowy, źródło nietknięte."""
    parts = [p for p in (fit_filter(fit), extra_vf, ass_filter(subs) if subs else "") if p]
    vf = ",".join(parts)
    args = ["-i", str(src)]
    if vf:
        args += (["-filter_complex", vf] if "split" in vf else ["-vf", vf])
    args += encoder_args() + AUDIO_ARGS + MUX_ARGS + [str(out)]
    run(args)
    return Path(out)


def extract_frame(src: str | Path, t: float, out_png: str | Path) -> Path:
    run(["-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", str(out_png)])
    return Path(out_png)


def scene_cuts(src: str | Path, threshold: float = 0.28) -> list[float]:
    cmd = ["ffmpeg", "-hide_banner", "-i", str(src), "-vf", f"select='gt(scene,{threshold})',showinfo",
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    import re
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def to_wav16k(src: str | Path, out_wav: str | Path) -> Path:
    run(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(out_wav)])
    return Path(out_wav)
