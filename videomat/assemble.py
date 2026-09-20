"""Montaż końcowy: wideo (lub sklejone klipy) + lektor + muzyka z duckingiem + napisy .ass -> nowy plik.

    assemble(video="a.mp4", vo="vo.mp3", music="m.mp3", subs="subs.ass", fit="pad")
    concat_clips(["c1.mp4","c2.mp4"], "work/joined.mp4")   # re-enkodowanie do wspólnego formatu
"""
from __future__ import annotations

from pathlib import Path

from . import config, ffmpeg

W, H = ffmpeg.W, ffmpeg.H


def concat_clips(clips: list[str | Path], out: str | Path, fit: str = "pad", fps: int = 30) -> Path:
    """Skleja klipy o dowolnych parametrach: każdy skalowany do 1080x1920, fps ujednolicony, audio 48k stereo."""
    n = len(clips)
    args: list[str] = []
    for c in clips:
        args += ["-i", str(c)]
    parts, maps = [], ""
    for i, c in enumerate(clips):
        info = ffmpeg.video_info(c)
        f = ffmpeg.fit_filter(fit) if fit != "none" else f"scale={W}:{H},setsar=1"
        f = f.replace("split[a][b]", f"[{i}:v]split[a{i}][b{i}]").replace("[a]scale", f"[a{i}]scale").replace("[b]scale", f"[b{i}]scale").replace("[bg][fg]", f"[bg{i}][fg{i}]").replace("[bg];", f"[bg{i}];").replace("[fg];", f"[fg{i}];")
        if not f.startswith("["):
            f = f"[{i}:v]" + f
        parts.append(f"{f},fps={fps},format=yuv420p[v{i}]")
        if info["has_audio"]:
            parts.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{i}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{info['duration']:.3f}[a{i}]")
        maps += f"[v{i}][a{i}]"
    parts.append(f"{maps}concat=n={n}:v=1:a=1[v][a]")
    ffmpeg.run(args + ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
               + ffmpeg.encoder_args() + ffmpeg.AUDIO_ARGS + ffmpeg.MUX_ARGS + [str(out)])
    return Path(out)


def assemble(video: str | Path, out: str | Path | None = None, vo: str | Path | None = None,
             music: str | Path | None = None, subs: str | Path | None = None, fit: str = "none",
             music_db: float = -14.0, duck_db: float = -12.0, keep_original_audio: bool = True,
             original_db: float = 0.0, vo_offset: float = 0.0, fade_out: float = 1.5, tag: str = "final") -> Path:
    video = Path(video)
    out = Path(out) if out else config.next_version_path(config.OUT, f"{video.stem}_{tag}")
    info = ffmpeg.video_info(video)
    dur = info["duration"]

    inputs = ["-i", str(video)]
    idx = 1
    a_parts, mix_inputs = [], []

    if keep_original_audio and info["has_audio"]:
        a_parts.append(f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={original_db}dB[orig]")
        mix_inputs.append("[orig]")
    vo_label = None
    if vo:
        inputs += ["-i", str(vo)]
        delay = int(max(0.0, vo_offset) * 1000)
        a_parts.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={delay}|{delay}[vo]")
        vo_label = "[vo]"
        idx += 1
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        mus = (f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{dur:.3f},"
               f"volume={music_db}dB,afade=t=out:st={max(0.0, dur - fade_out):.3f}:d={fade_out}")
        if vo_label:
            # ducking: muzyka ściszana gdy mówi lektor (sidechain), potem oba do miksu
            a_parts.append(mus + "[mus_raw]")
            a_parts.append(f"{vo_label}asplit[vo_mix][vo_sc]")
            a_parts.append(f"[mus_raw][vo_sc]sidechaincompress=threshold=0.02:ratio=8:attack=40:release=400:"
                           f"makeup=1[mus]")
            mix_inputs += ["[vo_mix]", "[mus]"]
            vo_label = None
        else:
            a_parts.append(mus + "[mus]")
            mix_inputs.append("[mus]")
        idx += 1
    if vo_label:
        mix_inputs.append(vo_label)

    if mix_inputs:
        if len(mix_inputs) == 1:
            a_parts.append(f"{mix_inputs[0]}anull[aout]")
        else:
            a_parts.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:normalize=0,"
                           f"alimiter=limit=0.95[aout]")
    v_parts = [p for p in (ffmpeg.fit_filter(fit), ffmpeg.ass_filter(subs) if subs else "") if p]
    v_chain = "[0:v]" + (",".join(v_parts) if v_parts else "null") + "[vout]"
    v_chain = v_chain.replace("[0:v]split[a][b]", "[0:v]split[a][b]")  # pad już zawiera labelki
    if v_parts and "split" in v_parts[0]:
        # pad-filter ma własne etykiety; doklej resztę łańcucha po overlay
        v_chain = "[0:v]" + ",".join(v_parts) + "[vout]"
    fc = ";".join([v_chain] + a_parts)
    args = inputs + ["-filter_complex", fc, "-map", "[vout]"]
    if mix_inputs:
        args += ["-map", "[aout]"]
    args += ["-t", f"{dur:.3f}"] + ffmpeg.encoder_args() + ffmpeg.AUDIO_ARGS + ffmpeg.MUX_ARGS + [str(out)]
    ffmpeg.run(args)
    return out
