"""Renderowanie filmu z modelu film.json.

Każda scena renderowana jest osobno, do jednolitego formatu (rozdzielczość, fps, zawsze ścieżka
audio), dzięki czemu sklejenie całości to concat bez re-enkodowania, a miks dźwięku to jeden
przebieg z kopiowanym obrazem. Sceny trafiają do cache adresowanego treścią — zmiana napisu
odświeża jedną scenę, nie cały film.

    r = Renderer(film, project_dir)
    r.render_film(quality="final")          # out/<nazwa>_vN.mp4
    r.render_frame(12.5)                    # pojedyncza klatka PNG do podglądu
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import cache, chunker, config, ffmpeg, speech
from .timeline import Film, Layer, Resolved, Scene, hex_to_ass, parse_time, resolve

ENGINE = "r1"                 # zmiana tej wartości unieważnia cały cache
CAPTION_MAX_WORDS = 4         # duże napisy => krótsze frazy
POP_IN = r"\fscx60\fscy60\t(0,150,\fscx100\fscy100)"
HEADLINE_TAGS = (r"\fsp8\b1\bord4\3c&H000000&\shad0\fad(60,80)"
                 r"\fscx70\fscy70\t(0,120,\fscx108\fscy108)\t(120,190,\fscx100\fscy100)")

QUALITY = {
    "final": {"scale": 1.0, "q": 19, "nvenc": "p5", "x264": "fast"},
    "proxy": {"scale": 0.5, "q": 30, "nvenc": "p1", "x264": "ultrafast"},
}


class RenderError(RuntimeError):
    pass


# ------------------------------------------------------------------ ASS
def ts(seconds: float) -> str:
    cs = max(0, int(round(seconds * 100)))
    h, rest = divmod(cs, 360000)
    m, rest = divmod(rest, 6000)
    s, c = divmod(rest, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def dialogue(layer: int, start: float, end: float, style: str, text: str) -> str:
    return f"Dialogue: {layer},{ts(start)},{ts(end)},{style},,0,0,0,{text}"


def esc(text: str) -> str:
    """Tekst użytkownika nie może wstrzyknąć własnych tagów ASS."""
    return text.replace("{", "(").replace("}", ")").replace("\n", r"\N")


MARKUP = re.compile(r"\[(c:[#A-Za-z0-9_]+|fs:\d+|b:[01]|/)\]")


def _color(theme, name: str) -> str:
    named = {"white": theme.white, "grey": theme.grey, "gray": theme.grey,
             "accent": theme.accent, "accent2": theme.accent2}
    return hex_to_ass(named.get(name.lower(), name))


def markup(text: str, theme, base: dict) -> str:
    """Prosta składnia w tekście warstwy: [c:accent] [c:#FF0000] [fs:60] [b:0] [/] — bez surowego ASS."""
    def tag(token: str) -> str:
        if token == "/":
            out = f"\\c{base['color']}&"
            if base.get("size"):
                out += f"\\fs{base['size']}"
            out += f"\\b{1 if base.get('bold') else 0}"
            return out
        kind, _, value = token.partition(":")
        if kind == "c":
            return f"\\c{_color(theme, value)}&"
        if kind == "fs":
            return f"\\fs{value}"
        return f"\\b{value}"

    parts = MARKUP.split(text)
    out, pending = [], []
    for i, part in enumerate(parts):
        if i % 2:
            pending.append(tag(part))
            continue
        if pending:
            out.append("{" + "".join(pending) + "}")
            pending = []
        out.append(esc(part))
    if pending:
        out.append("{" + "".join(pending) + "}")
    return "".join(out)


def styles_block(film: Film) -> str:
    t = film.theme
    white, grey, gold, cyan = (hex_to_ass(t.white), hex_to_ass(t.grey),
                               hex_to_ass(t.accent), hex_to_ass(t.accent2))
    fmt = film.format
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {fmt.width}
PlayResY: {fmt.height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{t.serif},96,{white},{white},&H00000000,&H00000000,0,0,0,0,100,100,14,0,1,0,0,5,60,60,0,1
Style: Sub,{t.sans},58,{white},{white},&H00000000,&H00000000,0,0,0,0,100,100,6,0,1,3,0,5,60,60,0,1
Style: Quote,{t.sans},{t.caption_size},{gold},{white},&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,70,70,0,1
Style: Stamp,{t.sans},46,{gold},{gold},&H00101010,&H00000000,-1,0,0,0,100,100,8,0,1,3,0,5,40,40,0,1
Style: Board,{t.sans},60,{white},{white},&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,0,0,7,60,60,0,1
Style: Hud,{t.mono},40,{cyan},{cyan},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,60,60,0,1
Style: Narr,{t.sans},{t.narration_size},{gold},{white},&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Text
"""


def _rect(width: int, height: int) -> str:
    return f"m 0 0 l {width} 0 l {width} {height} l 0 {height}"


def local_time(value, local_times: dict[str, tuple[float, float]], fallback: float = 0.0) -> float:
    """Czas wewnątrz sceny: liczba albo odniesienie do lektora tej sceny ('vo7.end+0.15')."""
    if value is None:
        return fallback
    ref, anchor, delta = parse_time(value)
    if ref is None:
        return delta
    if ref not in local_times:
        raise RenderError(f"Warstwa odwołuje się do lektora {ref!r}, którego nie ma w tej scenie.")
    begin, finish = local_times[ref]
    return (finish if anchor == "end" else begin) + delta


def layer_events(layer: Layer, scene_end: float, theme, fmt,
                 local_times: dict[str, tuple[float, float]] | None = None) -> list[str]:
    """Jedna warstwa opisu -> linie Dialogue."""
    local_times = local_times or {}
    start = local_time(layer.start, local_times, 0.0)
    end = local_time(layer.end, local_times, scene_end) if layer.end is not None else scene_end
    if end <= start:
        return []
    cx = fmt.width // 2

    def head(align: int, x: int, y: int, size: int | None = None, style_color: str | None = None) -> str:
        tags = f"\\an{align}\\pos({x},{y})"
        if size:
            tags += f"\\fs{size}"
        if layer.spacing:
            tags += f"\\fsp{layer.spacing}"
        if layer.bold:
            tags += "\\b1"
        if layer.border is not None:
            tags += f"\\bord{layer.border}\\3c&H000000&"
        color = style_color or (_color(theme, layer.color) if layer.color else None)
        if color:
            tags += f"\\c{color}&"
        if layer.fade_in or layer.fade_out:
            tags += f"\\fad({layer.fade_in},{layer.fade_out})"
        if layer.pop:
            tags += POP_IN
        return tags

    base = {"color": _color(theme, layer.color) if layer.color else hex_to_ass(theme.white),
            "size": layer.size, "bold": layer.bold}
    body = markup(layer.text or "", theme, base)
    kind = layer.type

    if kind in ("title", "subtitle", "stamp", "board"):
        style = {"title": "Title", "subtitle": "Sub", "stamp": "Stamp", "board": "Board"}[kind]
        default_align = 7 if kind == "board" else 5
        align = layer.align or default_align
        x = layer.x if layer.x is not None else (80 if align in (1, 4, 7) else cx)
        y = layer.y if layer.y is not None else fmt.height // 2
        z = 0 if kind == "board" else 1
        return [dialogue(z, start, end, style, "{" + head(align, x, y, layer.size) + "}" + body)]

    if kind == "headline":
        y = layer.y if layer.y is not None else 900
        size = layer.size or 150
        return [dialogue(2, start, end, "Title",
                         f"{{\\an5\\pos({cx},{y})\\fs{size}{HEADLINE_TAGS}}}" + body)]

    if kind == "counter":
        align = layer.align or 9
        x = layer.x if layer.x is not None else fmt.width - 50
        y = layer.y if layer.y is not None else 150
        size = layer.size or 40
        second = int(size * 1.95)
        fade = f"\\fad({layer.fade_in},{layer.fade_out})" if (layer.fade_in or layer.fade_out) else ""
        text = (f"{{\\an{align}\\pos({x},{y})\\fs{size}{fade}}}{body} "
                f"\\N{{\\an{align}\\fs{second}\\b1}}x{layer.n or 1}")
        return [dialogue(1, start, end, "Stamp", text)]

    if kind in ("panel", "shape"):
        x = layer.x if layer.x is not None else 0
        y = layer.y if layer.y is not None else 0
        w = layer.width if layer.width is not None else fmt.width
        h = layer.height if layer.height is not None else fmt.height
        color = _color(theme, layer.color) if layer.color else hex_to_ass("#000000")
        tags = f"\\an{layer.align or 7}\\pos({x},{y})\\1c{color}&"
        if layer.opacity:
            tags += f"\\1a&H{layer.opacity:02X}&"
        tags += "\\bord0\\shad0"
        if layer.fade_in or layer.fade_out:
            tags += f"\\fad({layer.fade_in},{layer.fade_out})"
        return [dialogue(0, start, end, "Board", "{" + tags + "\\p1}" + _rect(w, h) + "{\\p0}")]

    if kind == "word_list":
        items = layer.items
        if not items:
            return []
        x = layer.x if layer.x is not None else cx
        y0 = layer.y if layer.y is not None else 760
        lh = layer.line_height or 190
        size = layer.size or 88
        step = layer.step if layer.step is not None else max(0.55, (end - start - 0.3) / max(len(items), 1))
        events = []
        for i, word in enumerate(items):
            tags = (f"\\an{layer.align or 5}\\pos({x},{y0 + i * lh})\\fs{size}")
            if layer.spacing:
                tags += f"\\fsp{layer.spacing}"
            if layer.fade_in or layer.fade_out:
                tags += f"\\fad({layer.fade_in},{layer.fade_out})"
            tags += r"\fscx90\fscy90\t(0,180,\fscx100\fscy100)"
            events.append(dialogue(0, start + i * step, end, "Title",
                                   "{" + tags + "}" + markup(word, theme, base)))
        return events

    if kind == "grid":
        count = layer.count or 0
        if count <= 0:
            return []
        cols = layer.columns or 14
        cell = layer.cell or 56
        gap = layer.gap or 70
        x0 = layer.x if layer.x is not None else 80
        y0 = layer.y if layer.y is not None else 660
        step = layer.step if layer.step is not None else 0.03
        color = _color(theme, layer.color) if layer.color else hex_to_ass(theme.accent)
        events = []
        for i in range(count):
            row, col = divmod(i, cols)
            tags = (f"\\an{layer.align or 7}\\pos({x0 + col * gap},{y0 + row * gap})\\1c{color}&"
                    r"\bord0\shad0\fscx40\fscy40\t(0,120,\fscx100\fscy100)")
            if layer.fade_in or layer.fade_out:
                tags += f"\\fad({layer.fade_in},{layer.fade_out})"
            events.append(dialogue(0, start + i * step, end, "Board",
                                   "{" + tags + "\\p1}" + _rect(cell, cell) + "{\\p0}"))
        return events

    raise RenderError(f"Nieznany typ warstwy: {kind}")


def karaoke(groups: list[list[dict]], y: int, style: str, cx: int,
            offset: float = 0.0, layer: int = 0) -> list[str]:
    """Frazy słowo po słowie: \\kf z realnych czasów, bez nachodzenia na następną frazę."""
    events = []
    for gi, words in enumerate(groups):
        if not words:
            continue
        body = ""
        for i, w in enumerate(words):
            nxt = words[i + 1]["start"] if i + 1 < len(words) else w["end"]
            centis = max(int(round((nxt - w["start"]) * 100)), 8)
            body += f"{{\\kf{centis}}}{esc(w['w'])} "
        text = re.sub(r"[.]+$", "", body.strip())
        end = words[-1]["end"] + 0.25
        if gi + 1 < len(groups) and groups[gi + 1]:
            end = min(end, groups[gi + 1][0]["start"] - 0.02)
        end = max(end, words[-1]["end"] - 0.02)
        events.append(dialogue(layer, offset + words[0]["start"], offset + end, style,
                               f"{{\\an2\\pos({cx},{y})\\fad(50,40)}}" + text))
    return events


def group_words(words: list[dict]) -> list[list[dict]]:
    """Podział na frazy z chunkera, ze ścisłym przypisaniem słów (bez powtórzeń)."""
    chunks = chunker.chunk_words([dict(w) for w in words], max_words=CAPTION_MAX_WORDS)
    groups, pos = [], 0
    for chunk in chunks:
        n = len(chunk["text"].split())
        groups.append(words[pos:pos + n])
        pos += n
    if pos < len(words) and groups:
        groups[-1] = groups[-1] + words[pos:]
    return groups


# ------------------------------------------------------------------ renderer
class Renderer:
    def __init__(self, film: Film, project_dir: Path, work_dir: Path | None = None,
                 log=None):
        self.film = film
        self.project_dir = Path(project_dir)
        self.work = Path(work_dir) if work_dir else config.WORK / self.project_dir.name
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / "ass").mkdir(exist_ok=True)
        (self.work / "frames").mkdir(exist_ok=True)
        self.cache = cache.SceneCache(self.work)
        self.log = log or (lambda msg: None)
        self._speech: dict[str, Path] | None = None
        self._resolved: Resolved | None = None

    # -------------------------------------------------- ścieżki i zasoby
    def asset_path(self, relative: str | None) -> Path | None:
        if not relative:
            return None
        candidate = Path(relative)
        if candidate.is_absolute():
            return candidate
        for base in (self.project_dir, config.ROOT):
            p = base / candidate
            if p.exists():
                return p
        return self.project_dir / candidate

    def speech_files(self) -> dict[str, Path]:
        if self._speech is None:
            self._speech = speech.audio_files(self.film, self.work)
        return self._speech

    def resolved(self, refresh: bool = False) -> Resolved:
        if self._resolved is None or refresh:
            durations = speech.durations(self.film, self.work)
            self._resolved = resolve(self.film, durations)
        return self._resolved

    # -------------------------------------------------- napisy
    def quote_events(self, scene: Scene) -> list[str]:
        clip = self.film.assets.clips[scene.clip]  # type: ignore[index]
        path = self.asset_path(clip.transcript)
        if not path or not path.exists():
            self.log(f"scena {scene.id}: brak transkryptu, napisy cytatu pominięte")
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        a, b = float(scene.start), float(scene.end)  # type: ignore[arg-type]
        words = []
        for segment in data.get("segments", []):
            for w in segment.get("words", []):
                if a - 0.05 <= w["start"] < b:
                    text = clip.fixes.get(w["w"], w["w"])
                    if not text:
                        continue
                    words.append({"w": text,
                                  "start": max(0.0, w["start"] - a),
                                  "end": min(b - a, w["end"] - a)})
        if not words:
            return []
        return karaoke(group_words(words), scene.caption_y, "Quote", self.film.format.width // 2)

    def narration_events(self, ref: str, local_start: float, y: int) -> list[str]:
        wav = self.speech_files().get(ref)
        if not wav:
            return []
        line = next(n for n in self.film.narration if n.id == ref)
        words = speech.align(ref, line.text, wav, self.work)
        return karaoke(group_words(words), y, "Narr", self.film.format.width // 2,
                       offset=local_start, layer=3)

    def scene_ass(self, scene: Scene, duration: float) -> str:
        events: list[str] = []
        if scene.type == "clip" and scene.captions:
            events += self.quote_events(scene)
        resolved = self.resolved()
        local_times = {n.id: (n.local_start, n.local_start + n.duration)
                       for n in resolved.narration if n.scene == scene.id}
        for layer in scene.layers:
            events += layer_events(layer, duration, self.film.theme, self.film.format, local_times)
        for placement in scene.narration:
            if not placement.captions:
                continue
            entry = next((n for n in resolved.narration if n.id == placement.ref and n.scene == scene.id), None)
            if entry:
                events += self.narration_events(placement.ref, entry.local_start, placement.y)
        return styles_block(self.film) + "\n".join(events) + "\n"

    # -------------------------------------------------- filtry
    def _size(self, quality: str) -> tuple[int, int]:
        scale = QUALITY[quality]["scale"]
        fmt = self.film.format
        w = int(fmt.width * scale) // 2 * 2
        h = int(fmt.height * scale) // 2 * 2
        return w, h

    def _encoder(self, quality: str) -> list[str]:
        cfg = QUALITY[quality]
        if config.encoder() == "nvenc":
            args = ["-c:v", "h264_nvenc", "-preset", cfg["nvenc"], "-rc", "vbr",
                    "-cq", str(cfg["q"]), "-b:v", "0", "-pix_fmt", "yuv420p"]
        else:
            args = ["-c:v", "libx264", "-preset", cfg["x264"], "-crf", str(cfg["q"]), "-pix_fmt", "yuv420p"]
        return args + ["-r", str(self.film.format.fps)] + ffmpeg.AUDIO_ARGS

    def _fit(self, quality: str) -> str:
        w, h = self._size(quality)
        grade = (",eq=contrast=1.10:saturation=0.85:gamma=0.97,noise=alls=7:allf=t,vignette=PI/4.5"
                 if self.film.theme.grade else "")
        return (f"split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                f"gblur=sigma=30,eq=brightness=-0.12:saturation=0.5[bg];"
                f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2{grade},setsar=1")

    def _grade_still(self) -> str:
        if not self.film.theme.grade:
            return "setsar=1"
        return "eq=contrast=1.10:saturation=0.85:gamma=0.97,noise=alls=7:allf=t,vignette=PI/4.5,setsar=1"

    def _clip_fit(self, scene: Scene, quality: str) -> str:
        clip = self.film.assets.clips[scene.clip]  # type: ignore[index]
        return (clip.crop + "," if clip.crop else "") + self._fit(quality)

    # -------------------------------------------------- render scen
    def scene_key(self, scene: Scene, duration: float, ass_text: str, quality: str) -> str:
        sources: list[Path] = []
        if scene.clip:
            src = self.asset_path(self.film.assets.clips[scene.clip].path)
            if src:
                sources.append(src)
        for placement in scene.narration:
            wav = self.speech_files().get(placement.ref)
            if wav:
                sources.append(wav)
        payload = {"scene": scene.model_dump(mode="json"), "duration": round(duration, 4),
                   "ass": ass_text, "format": self.film.format.model_dump(),
                   "theme": self.film.theme.model_dump()}
        return cache.key(payload, sources, quality, ENGINE)

    def render_scene(self, scene: Scene, duration: float, quality: str = "final") -> Path:
        ass_text = self.scene_ass(scene, duration)
        key = self.scene_key(scene, duration, ass_text, quality)
        out = self.cache.path(key)
        if self.cache.has(key):
            return out
        ass_file = self.work / "ass" / f"{key}.ass"
        ass_file.write_text(ass_text, encoding="utf-8")
        subs = ffmpeg.escape_filter_path(ass_file)
        w, h = self._size(quality)
        fps = self.film.format.fps
        enc = self._encoder(quality)
        self.log(f"render {scene.id} ({scene.type}, {duration:.2f}s, {quality})")

        if scene.type == "black":
            vf = f"ass='{subs}'"
            if self.film.theme.grade:
                vf += ",noise=alls=5:allf=t,vignette=PI/5"
            ffmpeg.run(["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={duration:.3f}",
                        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{duration:.3f}",
                        "-vf", vf, "-shortest"] + enc + [str(out)])
            return out

        src = self.asset_path(self.film.assets.clips[scene.clip].path)  # type: ignore[index]
        if not src or not src.exists():
            raise RenderError(f"Scena {scene.id}: brak pliku klipu {src}")

        if scene.type == "clip":
            ffmpeg.run(["-ss", f"{scene.start:.3f}", "-to", f"{scene.end:.3f}", "-i", str(src),
                        "-filter_complex", self._clip_fit(scene, quality) + f",ass='{subs}'",
                        "-af", "aformat=sample_rates=48000:channel_layouts=stereo"] + enc + [str(out)])
            return out

        png = self.work / "frames" / f"{key}.png"
        if not png.exists():
            ffmpeg.run(["-ss", f"{scene.at:.3f}", "-i", str(src), "-frames:v", "1",
                        "-filter_complex", self._clip_fit(scene, quality), str(png)])
        vf = self._grade_still()
        if scene.zoom:
            wide = int(8000 * QUALITY[quality]["scale"])
            vf = (f"scale={wide}:-1,zoompan=z='min(zoom+0.0009,1.25)':d={int(duration * fps)}:"
                  f"x='iw/2-(iw/zoom/2)':y='ih/2.6-(ih/zoom/2)':s={w}x{h}:fps={fps}," + vf)
        ffmpeg.run(["-loop", "1", "-t", f"{duration:.3f}", "-i", str(png),
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{duration:.3f}",
                    "-vf", f"{vf},ass='{subs}'", "-shortest"] + enc + [str(out)])
        return out

    # -------------------------------------------------- podgląd klatki
    def render_frame(self, t: float, quality: str = "final", out_png: Path | None = None) -> Path:
        resolved = self.resolved()
        target = next((s for s in resolved.scenes if s.start <= t < s.end), None)
        if target is None and resolved.scenes:
            target = resolved.scenes[-1]
        if target is None:
            raise RenderError("Film nie ma scen.")
        scene = self.film.scene(target.id)
        local = max(0.0, min(t - target.start, target.duration - 0.02))
        ass_text = self.scene_ass(scene, target.duration)
        key = self.scene_key(scene, target.duration, ass_text, quality)
        ass_file = self.work / "ass" / f"{key}.ass"
        if not ass_file.exists():
            ass_file.write_text(ass_text, encoding="utf-8")
        subs = ffmpeg.escape_filter_path(ass_file)
        out = Path(out_png) if out_png else self.work / "frames" / f"preview_{key}_{local:.2f}.png"
        w, h = self._size(quality)
        fps = self.film.format.fps

        if scene.type == "black":
            vf = f"ass='{subs}'"
            if self.film.theme.grade:
                vf += ",noise=alls=5:allf=t,vignette=PI/5"
            ffmpeg.run(["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={target.duration:.3f}",
                        "-vf", vf, "-ss", f"{local:.3f}", "-frames:v", "1", str(out)])
            return out

        src = self.asset_path(self.film.assets.clips[scene.clip].path)  # type: ignore[index]
        if scene.type == "clip":
            ffmpeg.run(["-ss", f"{scene.start:.3f}", "-i", str(src),
                        "-filter_complex", self._clip_fit(scene, quality) + f",ass='{subs}'",
                        "-ss", f"{local:.3f}", "-frames:v", "1", str(out)])
            return out

        png = self.work / "frames" / f"{key}.png"
        if not png.exists():
            ffmpeg.run(["-ss", f"{scene.at:.3f}", "-i", str(src), "-frames:v", "1",
                        "-filter_complex", self._clip_fit(scene, quality), str(png)])
        vf = self._grade_still()
        if scene.zoom:
            # Ta sama geometria co zoompan, ale policzona wprost: podgląd klatki nie może
            # przeliczać całej rampy najazdu na obrazie skalowanym do 8000 px.
            z = min(1.0 + 0.0009 * round(local * fps), 1.25)
            cw, ch = int(w / z) // 2 * 2, int(h / z) // 2 * 2
            cx, cy = int(w / 2 - cw / 2), int(h / 2.6 - ch / 2)
            vf = f"crop={cw}:{ch}:{max(cx, 0)}:{max(cy, 0)},scale={w}:{h}," + vf
        ffmpeg.run(["-loop", "1", "-t", f"{target.duration:.3f}", "-i", str(png),
                    "-vf", f"{vf},ass='{subs}'", "-ss", f"{local:.3f}", "-frames:v", "1", str(out)])
        return out

    # -------------------------------------------------- dźwięk
    def sfx_path(self, ref: str) -> Path | None:
        asset = self.film.assets.sfx[ref]
        if asset.path:
            p = self.asset_path(asset.path)
            if p and p.exists():
                return p
        generated = self.work / f"sfx_{ref}.mp3"
        if generated.exists():
            return generated
        if not asset.prompt or not config.env("ELEVENLABS_API_KEY"):
            return None
        try:
            from .music import sfx
            return sfx(asset.prompt, generated, duration_s=asset.duration,
                       loop=asset.loop, prompt_influence=0.45)
        except Exception as exc:
            self.log(f"efekt {ref} niedostępny: {str(exc)[:120]}")
            return None

    # -------------------------------------------------- cały film
    def render_film(self, out: Path | None = None, quality: str = "final",
                    on_progress=None) -> dict:
        resolved = self.resolved(refresh=True)
        segments: list[Path] = []
        for i, entry in enumerate(resolved.scenes):
            scene = self.film.scene(entry.id)
            segments.append(self.render_scene(scene, entry.duration, quality))
            if on_progress:
                on_progress((i + 1) / max(len(resolved.scenes), 1) * 0.8, f"scena {entry.id}")

        listing = self.work / f"concat_{quality}.txt"
        listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
        base = self.work / f"base_{quality}.mp4"
        ffmpeg.run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(base)])
        if on_progress:
            on_progress(0.85, "sklejone")

        inputs = ["-i", str(base)]
        chains = ["[0:a]volume=1.0[base]"]
        mix = ["[base]"]
        index = 1

        def add_audio(path: Path, at: float, gain_db: float, label: str,
                      loop: bool = False, trim: float | None = None, fades: str = "") -> None:
            nonlocal index
            inputs.extend((["-stream_loop", "-1"] if loop else []) + ["-i", str(path)])
            ms = max(0, int(at * 1000))
            chain = f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo"
            if trim:
                chain += f",atrim=0:{trim:.3f},asetpts=PTS-STARTPTS"
            chain += f",volume={gain_db}dB{fades},adelay={ms}|{ms}[{label}]"
            chains.append(chain)
            mix.append(f"[{label}]")
            index += 1

        speech_files = self.speech_files()
        for entry in resolved.narration:
            wav = speech_files.get(entry.id)
            if wav:
                add_audio(wav, entry.start, entry.gain_db, f"n{index}")
        for entry in resolved.sfx:
            path = self.sfx_path(entry.ref)
            if path:
                add_audio(path, entry.start, entry.gain_db, f"s{index}")
        if self.film.music and resolved.music:
            music_path = self.asset_path(self.film.assets.music[self.film.music.asset].path)
            if music_path and music_path.exists():
                for seg in resolved.music:
                    length = seg.end - seg.start
                    if length <= 0.05:
                        continue
                    fades = ""
                    if seg.duck_after:
                        fades += (f",volume='if(lt(t,{seg.duck_after:.2f}),1.0,{seg.duck_factor})'"
                                  f":eval=frame")
                    if seg.fade_in:
                        fades += f",afade=t=in:d={seg.fade_in}"
                    if seg.fade_out and length > seg.fade_out:
                        fades += f",afade=t=out:st={length - seg.fade_out:.3f}:d={seg.fade_out}"
                    add_audio(music_path, seg.start, seg.gain_db, f"m{index}",
                              loop=True, trim=length, fades=fades)
            else:
                self.log("podkład muzyczny pominięty — brak pliku")

        chains.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,"
                      f"alimiter=limit=0.95[aout]")
        if out is None:
            stem = self.film.name + ("" if quality == "final" else f"_{quality}")
            out = config.next_version_path(config.OUT, stem)
        ffmpeg.run(inputs + ["-filter_complex", ";".join(chains), "-map", "0:v", "-map", "[aout]",
                             "-c:v", "copy"] + ffmpeg.AUDIO_ARGS + ffmpeg.MUX_ARGS + [str(out)])
        if on_progress:
            on_progress(1.0, "gotowe")

        (self.work / "marks.json").write_text(
            json.dumps({"total": resolved.total, "marks": resolved.marks(),
                        "scenes": [s.model_dump() for s in resolved.scenes]},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        return {"video": Path(out), "total": resolved.total, "scenes": len(resolved.scenes),
                "cache_hits": self.cache.hits, "cache_misses": self.cache.misses}


def load_film(path: str | Path) -> Film:
    return Film.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_film(film: Film, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(film.model_dump_json(indent=1, exclude_defaults=False), encoding="utf-8")
    return target
