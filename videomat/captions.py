"""Pipeline napisów: (transkrypcja | słowa z TTS | SRT) -> frazy -> spec.json -> .ass -> render -> klatki.

Użycie:
    result = run_captions("in.mp4", fit="pad", theme="hitech", animation="highlight")
    # -> {"video": out/in_v1.mp4, "spec": work/in_spec.json, "ass": ..., "frames": [...], "uncertain": [...]}

spec.json jest zapisywany PRZED renderem i można go ręcznie poprawić, po czym:
    render_spec("in.mp4", "work/in_spec.json", fit="pad")
"""
from __future__ import annotations

import json
from pathlib import Path

from . import chunker, config, ffmpeg, transcribe, verify
from .ass import write_ass

SUB_SIZE = 90          # px w przestrzeni 1920 — mniejsze czyta się źle na telefonie
SUB_Y = 1445           # baseline napisów verbatim (safe zone: y 250–1600)


def build_spec(chunks: list[dict], theme: str = "hitech", animation: str = "highlight",
               size: int = SUB_SIZE, y: int = SUB_Y, keywords: list[dict] | None = None,
               headlines: list[dict] | None = None, font: str | None = None) -> dict:
    caps = []
    for c in chunks:
        cap = {"text": c["text"], "start": c["start"], "end": c["end"], "animation": animation,
               "size": size, "y": y}
        if animation == "highlight":
            cap["drift"] = False
        caps.append(cap)
    spec = {"theme": theme, "captions": caps + (headlines or []), "keywords": keywords or []}
    if font:
        spec["font"] = font
    return spec


def chunks_from_source(src: Path, words_json: str | None = None, srt: str | None = None,
                       language: str = "pl", model: str | None = None, snap_scenes: bool = True) -> tuple[list[dict], list]:
    cuts = ffmpeg.scene_cuts(src) if snap_scenes else None
    if words_json:
        words = json.loads(Path(words_json).read_text(encoding="utf-8"))
        words = words["words"] if isinstance(words, dict) else words
        return chunker.chunk_words(words, cuts), []
    if srt:
        return chunker.chunks_from_segments(chunker.parse_srt(srt), scene_cuts=cuts), []
    tr = transcribe.transcribe(src, config.WORK / f"{src.stem}_transcript.json", language=language, model_size=model)
    words = transcribe.words_flat(tr)
    if not words:
        return [], tr.get("uncertain", [])
    return chunker.chunk_words(words, cuts), tr.get("uncertain", [])


def render_spec(src: str | Path, spec_path: str | Path, fit: str = "none", tag: str = "") -> dict:
    src, spec_path = Path(src), Path(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    info = ffmpeg.video_info(src)
    if fit == "none" and (info["width"], info["height"]) != (1080, 1920):
        spec.setdefault("resolution", [info["width"], info["height"]])
    ass_path = config.WORK / f"{spec_path.stem}.ass"
    write_ass(spec, ass_path)
    out = config.next_version_path(config.OUT, src.stem + (f"_{tag}" if tag else ""))
    ffmpeg.render_with_subs(src, ass_path, out, fit=fit)
    frames = verify.frames_for_spec(out, spec)
    return {"video": out, "ass": ass_path, "spec": spec_path, "frames": frames}


def run_captions(src: str | Path, fit: str = "none", theme: str = "hitech", animation: str = "highlight",
                 words_json: str | None = None, srt: str | None = None, language: str = "pl",
                 model: str | None = None, keywords: list[dict] | None = None, font: str | None = None,
                 render: bool = True) -> dict:
    src = Path(src)
    config.ensure_dirs()
    chunks, uncertain = chunks_from_source(src, words_json, srt, language, model)
    if not chunks:
        raise SystemExit("Brak rozpoznanej mowy. Jeśli to klip tylko z muzyką, użyj headline'ów w spec.json zamiast napisów verbatim.")
    spec = build_spec(chunks, theme, animation, keywords=keywords, font=font)
    spec_path = config.WORK / f"{src.stem}_spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    result = {"spec": spec_path, "chunks": len(chunks), "uncertain": uncertain}
    if render:
        result.update(render_spec(src, spec_path, fit=fit))
    return result
