#!/usr/bin/env python3
r"""
make_ass.py v2 — Motion-graphics style animated .ass generator for vertical
(9:16) videos: rapid word-by-word captions, karaoke color sweeps, HUD badges
with corner brackets, tooltips with pointer lines, RGB glitch intros.

Usage:
    python3 make_ass.py spec.json output.ass

JSON spec:
{
  "resolution": [1080, 1920],       // optional, default 1080x1920
  "font": "Poppins",
  "theme": "hitech",                // hitech | clean | bold
  "captions": [
    {"text": "TO *ZMIENIA* WSZYSTKO", "start": 0.3, "end": 1.8,
     "animation": "word_blast"}
     // word_blast  - each word shown alone, rapid pop (0.25-0.6s/word). MOST dynamic.
     // highlight   - full line visible, color sweeps word-by-word (karaoke \kf) + micro-drift
     // pop | fade | slide_up | typewriter | none
     // *word*      - accent color (+size bump in word_blast)
  ],
  "keywords": [
    {"text": "#AI", "start": 1.0, "end": 4.0,
     "animation": "badge",          // badge | tooltip | glitch | slide_left | slide_right | pop | glow | fade
     "position": "top",             // top | upper | center | [x,y]
     "target": [540, 1100],         // tooltip only: point the callout line at this pixel
     "size": 92}
  ]
}
Times in seconds. Layers: captions 0, badge boxes 3, brackets/lines 4, keyword text 5.
"""

import json
import re
import sys

THEMES = {
    "hitech": {
        "caption_color":  "&H00FFFFFF",
        "caption_border": "&H00201005",
        "accent":         "&H00FFE500",   # cyan #00E5FF (ASS is BGR)
        "accent2":        "&H00D62BFF",   # magenta #FF2BD6 (glitch)
        "accent_border":  "&H00332200",
        "box_fill":       "&H00160B03",   # near-black navy
        "caption_font_size": 74,
        "keyword_font_size": 92,
        "outline": 4, "shadow": 0,
    },
    "clean": {
        "caption_color":  "&H00FFFFFF",
        "caption_border": "&H00000000",
        "accent":         "&H0000D7FF",
        "accent2":        "&H00FF8800",
        "accent_border":  "&H00000000",
        "box_fill":       "&H00101010",
        "caption_font_size": 70,
        "keyword_font_size": 84,
        "outline": 3, "shadow": 1,
    },
    "bold": {
        "caption_color":  "&H0000FFFF",
        "caption_border": "&H00000000",
        "accent":         "&H00FFFFFF",
        "accent2":        "&H000045FF",
        "accent_border":  "&H00000000",
        "box_fill":       "&H00000000",
        "caption_font_size": 82,
        "keyword_font_size": 100,
        "outline": 5, "shadow": 0,
    },
}

CAPTION_Y_FRAC = 0.72
KEYWORD_POS_FRAC = {"top": (0.5, 0.18), "upper": (0.5, 0.30), "center": (0.5, 0.46)}


def ts(seconds):
    cs = max(0, int(round(seconds * 100)))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def esc(text):
    return text.replace("{", "(").replace("}", ")").replace("\n", "\\N")


def _mark(text):
    """*span of words* -> each word prefixed with \x01 sentinel."""
    return re.sub(r"\*([^*\n]+)\*",
                  lambda m: " ".join("\x01" + w for w in m.group(1).split()), text)


def parse_accents(text, accent, base):
    out, words = [], []
    for w in _mark(text).split():
        if w.startswith("\x01"):
            core = w[1:]
            out.append(f"{{\\c{accent}&}}{esc(core)}{{\\c{base}&}}")
            words.append((core, True))
        else:
            out.append(esc(w))
            words.append((w, False))
    return " ".join(out), words


def dlg(layer, start, end, style, text):
    return f"Dialogue: {layer},{ts(start)},{ts(end)},{style},,0,0,0,{text}"


# ------------------------------------------------------------------ captions
def caption_events(c, cx, cy_def, th):
    anim = c.get("animation", "highlight")
    start, end = c["start"], c["end"]
    dur_ms = int((end - start) * 1000)
    accent, base = th["accent"], th["caption_color"]
    fs = int(c.get("size", th["caption_font_size"]) * th["scale"])
    cy = int(c.get("y", cy_def))
    ev = []

    if anim == "headline":
        # Big hero title: per-line left->right wipe reveal (+rise), accent underline bar.
        text_lines = c["text"].split("\n")
        maxlen = max(len(re.sub(r"\*", "", ln)) for ln in text_lines)
        fs = min(fs, int(920 / (maxlen * 0.62)))   # auto-fit to safe width
        lh = int(fs * 1.24)
        n = len(text_lines)
        if c.get("panel", True):
            pw = min(int(maxlen * fs * 0.62 + 90), 1000)
            ph = int(n * lh + fs * 0.9 + (40 if c.get("kicker") else 0))
            pcy = cy - (n - 1) * lh // 2 - int(fs * 0.32) - (18 if c.get("kicker") else 0)
            px1, px2 = cx - pw // 2, cx + pw // 2
            pclip0 = f"\\clip({px1},{pcy - ph},{px1},{pcy + ph})"
            pclipt = f"\\t(0,300,\\clip({px1},{pcy - ph},{px2},{pcy + ph}))"
            ev.append(dlg(0, start, end, "Caption",
                          f"{{\\an5\\pos({cx},{pcy})\\1c{th['box_fill']}&\\1a&H48&\\bord0"
                          f"\\shad0\\blur2\\fad(0,120){pclip0}{pclipt}\\p1}}"
                          f"{rrect_path(pw, ph)}{{\\p0}}"))
        if c.get("kicker"):
            ky = cy - (n - 1) * lh - lh - int(fs * 0.12)
            ev.append(dlg(2, start, end, "Caption",
                          f"{{\\an2\\pos({cx},{ky})\\fs{int(fs * 0.38)}\\fsp5\\bord0\\shad0"
                          f"\\c{accent}&\\fad(120,100)}}" + esc(c["kicker"].upper())))
        for i, ln in enumerate(text_lines):
            rendered, _ = parse_accents(ln, accent, base)
            ly = cy - (n - 1 - i) * lh
            t_off = i * 0.09
            ytop, ybot = ly - lh - 8, ly + 12
            clip0 = f"\\clip({cx - 520},{ytop},{cx - 520},{ybot})"
            clipt = f"\\t(0,260,\\clip({cx - 520},{ytop},{cx + 520},{ybot}))"
            mv = f"\\move({cx},{ly + 20},{cx},{ly},0,200)"
            ev.append(dlg(1, start + t_off, end, "Caption",
                          f"{{\\an2{mv}\\fs{fs}\\fsp4\\1a&HFF&\\bord12\\3c&H000000&\\3a&H80&"
                          f"\\blur14\\shad0\\fad(20,100){clip0}{clipt}}}" + esc(re.sub(r"\*", "", ln))))
            tags = (f"{{\\an2{mv}\\fs{fs}\\fsp4\\b1\\bord2"
                    f"\\fad(20,100){clip0}{clipt}}}")
            ev.append(dlg(2, start + t_off, end, "Caption", tags + rendered))
        last_plain = re.sub(r"\*", "", text_lines[-1])
        barw = max(int(len(last_plain) * fs * 0.30), 120)
        bar_y = cy + int(fs * 0.42)
        bx1, bx2 = cx - barw // 2, cx + barw // 2
        bclip0 = f"\\clip({bx1},{bar_y - 20},{bx1},{bar_y + 20})"
        bclipt = f"\\t(0,240,\\clip({bx1},{bar_y - 20},{bx2},{bar_y + 20}))"
        bar = (f"{{\\an5\\pos({cx},{bar_y})\\1c{accent}&\\bord0\\shad0"
               f"\\fad(0,110){bclip0}{bclipt}\\p1}}m 0 0 l {barw} 0 l {barw} 9 l 0 9{{\\p0}}")
        ev.append(dlg(2, start + n * 0.09 + 0.10, end, "Caption", bar))
        return ev

    if anim == "word_blast":
        words = [(w[1:], True) if w.startswith("\x01") else (w, False)
                 for w in _mark(c["text"]).split()]
        n = max(len(words), 1)
        wd = (end - start) / n
        for i, (w, acc) in enumerate(words):
            t0 = start + i * wd
            t1 = end if i == n - 1 else t0 + wd + 0.02
            extra = f"\\c{accent}&\\fs{int(fs * 1.16)}" if acc else f"\\fs{fs}"
            tags = (f"{{\\an2\\pos({cx},{cy})\\fad(30,30){extra}\\fscx35\\fscy35"
                    f"\\t(0,100,\\fscx114\\fscy114)\\t(100,160,\\fscx100\\fscy100)}}")
            ev.append(dlg(0, t0, t1, "Caption", tags + esc(w)))
        return ev

    if anim == "highlight":
        text_lines = c["text"].split("\n")
        all_plain = [w for ln in text_lines for w in re.sub(r"\*", "", ln).split()]
        sweep = max(min(dur_ms - 300, 1500), 200)
        total_chars = sum(len(w) for w in all_plain) or 1
        line_bodies = []
        for ln in text_lines:
            rendered, words = parse_accents(ln, accent, base)
            body = ""
            for (w, _), part in zip(words, rendered.split(" ")):
                k = max(int(sweep / 10 * len(w) / total_chars), 3)
                body += f"{{\\kf{k}}}{part} "
            line_bodies.append(body.rstrip())
        full_body = "\\N".join(line_bodies)
        if c.get("drift", True):
            posmove = f"\\move({cx},{cy + 5},{cx},{cy - 5},0,{dur_ms})"
        else:
            posmove = f"\\pos({cx},{cy})"
        plain_body = "\\N".join(esc(re.sub(r"\*", "", ln)) for ln in text_lines)
        if c.get("glow", True):
            ev.append(dlg(0, start, end, "Caption",
                          f"{{\\an2{posmove}\\fs{fs}\\fad(90,110)\\1a&HFF&\\bord14"
                          f"\\3c&H000000&\\3a&H70&\\blur18\\shad0}}" + plain_body))
        tags = (f"{{\\an2{posmove}\\fs{fs}\\fad(90,110)\\c{accent}&\\2c{base}&}}")
        ev.append(dlg(1, start, end, "Caption", tags + full_body))
        return ev

    if anim == "typewriter":
        words = c["text"].split()
        per = max(int(min(dur_ms - 200, 900) / 10 / max(len(words), 1)), 4)
        body = "".join(f"{{\\k{per}}}{esc(w)} " for w in words).rstrip()
        ev.append(dlg(0, start, end, "Caption",
                      f"{{\\an2\\pos({cx},{cy})\\fs{fs}\\2a&HFF&}}" + body))
        return ev

    rendered, _ = parse_accents(c["text"], accent, base)
    if anim == "fade":
        tags = f"{{\\an2\\pos({cx},{cy})\\fs{fs}\\fad(150,150)}}"
    elif anim == "slide_up":
        tags = f"{{\\an2\\move({cx},{cy + 70},{cx},{cy},0,180)\\fs{fs}\\fad(100,120)}}"
    elif anim == "pop":
        tags = (f"{{\\an2\\pos({cx},{cy})\\fs{fs}\\fad(60,80)\\fscx35\\fscy35"
                f"\\t(0,140,\\fscx108\\fscy108)\\t(140,220,\\fscx100\\fscy100)}}")
    else:
        tags = f"{{\\an2\\pos({cx},{cy})\\fs{fs}}}"
    return [dlg(0, start, end, "Caption", tags + rendered)]


# ------------------------------------------------------------------ keywords
def rrect_path(w, h, r=18):
    return (f"m {r} 0 l {w-r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h-r} b {w} {h} {w} {h} {w-r} {h} "
            f"l {r} {h} b 0 {h} 0 {h} 0 {h-r} l 0 {r} b 0 0 0 0 {r} 0")


def rect_path(w, h):
    return f"m 0 0 l {w} 0 l {w} {h} l 0 {h}"


def brackets_path(w, h, blen=28, t=7):
    W, H = w, h
    tl = f"m 0 0 l {blen} 0 l {blen} {t} l {t} {t} l {t} {blen} l 0 {blen}"
    tr = f"m {W - blen} 0 l {W} 0 l {W} {blen} l {W - t} {blen} l {W - t} {t} l {W - blen} {t}"
    br = (f"m {W} {H - blen} l {W} {H} l {W - blen} {H} l {W - blen} {H - t} "
          f"l {W - t} {H - t} l {W - t} {H - blen}")
    bl = f"m 0 {H - blen} l {t} {H - blen} l {t} {H - t} l {blen} {H - t} l {blen} {H} l 0 {H}"
    return f"{tl} {tr} {br} {bl}"


def line_quad(x1, y1, x2, y2, half=3):
    dx, dy = x2 - x1, y2 - y1
    L = max((dx * dx + dy * dy) ** 0.5, 1)
    ox, oy = -dy / L * half, dx / L * half
    pts = [(x1 + ox, y1 + oy), (x2 + ox, y2 + oy), (x2 - ox, y2 - oy), (x1 - ox, y1 - oy)]
    minx, miny = min(p[0] for p in pts), min(p[1] for p in pts)
    rel = [(p[0] - minx, p[1] - miny) for p in pts]
    path = "m " + " l ".join(f"{p[0]:.0f} {p[1]:.0f}" for p in rel)
    return path, int(minx), int(miny)


def keyword_events(k, res_x, res_y, th, scale):
    anim = k.get("animation", "badge")
    start, end = k["start"], k["end"]
    pos = k.get("position", "top")
    if isinstance(pos, (list, tuple)):
        x, y = int(pos[0]), int(pos[1])
    else:
        fx, fy = KEYWORD_POS_FRAC.get(pos, KEYWORD_POS_FRAC["top"])
        x, y = int(res_x * fx), int(res_y * fy)
    fs = int(k.get("size", th["key_fs_base"]) * scale)
    text = esc(k["text"])
    accent, accent2 = th["accent"], th["accent2"]
    ev = []

    pop_in = ("\\fscx30\\fscy30\\t(0,140,\\fscx110\\fscy110)"
              "\\t(140,220,\\fscx100\\fscy100)\\fad(50,120)")

    if anim in ("badge", "tooltip"):
        w = int(len(k["text"]) * fs * 0.66 + 64)
        h = int(fs * 1.55)
        box = (f"{{\\an5\\pos({x},{y}){pop_in}\\1c{th['box_fill']}&\\1a&H30&"
               f"\\bord2\\3c{accent}&\\shad0\\p1}}{rect_path(w, h)}{{\\p0}}")
        ev.append(dlg(3, start, end, "Keyword", box))
        ow, oh = w + 22, h + 22
        br = (f"{{\\an5\\pos({x},{y}){pop_in}\\1c{accent}&\\bord0\\shad0\\p1}}"
              f"{brackets_path(ow, oh)}{{\\p0}}")
        ev.append(dlg(4, start, end, "Keyword", br))
        ev.append(dlg(5, start, end, "Keyword",
                      f"{{\\an5\\pos({x},{y}){pop_in}\\fs{fs}}}" + text))
        if anim == "tooltip" and "target" in k:
            tx, ty = int(k["target"][0]), int(k["target"][1])
            sy = y + oh // 2 if ty > y else y - oh // 2
            path, px, py = line_quad(x, sy, tx, ty, half=3)
            ev.append(dlg(4, start + 0.12, end, "Keyword",
                          f"{{\\an7\\pos({px},{py})\\fad(150,120)\\1c{accent}&\\1a&H20&"
                          f"\\bord0\\shad0\\p1}}{path}{{\\p0}}"))
            d = 11
            dot = f"m 0 0 l {2*d} 0 l {2*d} {2*d} l 0 {2*d}"
            ev.append(dlg(4, start + 0.2, end, "Keyword",
                          f"{{\\an5\\pos({tx},{ty})\\fad(120,120)\\frz45\\1c{accent}&"
                          f"\\bord0\\shad0\\blur1\\t(0,500,\\fscx140\\fscy140)\\p1}}{dot}{{\\p0}}"))
        return ev

    if anim == "glitch":
        g = 0.07
        for i, (col, off) in enumerate([(accent, -6), (accent2, 6), (accent2, -4), (accent, 4)]):
            t0 = start + i * g
            ev.append(dlg(5, t0, t0 + g, "Keyword",
                          f"{{\\an5\\pos({x + off},{y})\\fs{fs}\\c{col}&\\1a&H30&\\bord0}}" + text))
        ev.append(dlg(4, start + 4 * g, end, "Keyword",
                      f"{{\\an5\\pos({x + 4},{y + 4})\\fs{fs}\\c{accent2}&\\1a&H90&\\bord0}}" + text))
        ev.append(dlg(5, start + 4 * g, end, "Keyword",
                      f"{{\\an5\\pos({x},{y})\\fs{fs}\\fad(0,120)}}" + text))
        return ev

    base5 = f"\\an5\\pos({x},{y})\\fs{fs}"
    if anim == "fade":
        tags = f"{{{base5}\\fad(200,200)}}"
    elif anim == "pop":
        tags = f"{{{base5}{pop_in}}}"
    elif anim == "slide_left":
        tags = f"{{\\an5\\move({res_x + 300},{y},{x},{y},0,220)\\fs{fs}\\fad(0,150)}}"
    elif anim == "slide_right":
        tags = f"{{\\an5\\move(-300,{y},{x},{y},0,220)\\fs{fs}\\fad(0,150)}}"
    elif anim == "glow":
        tags = f"{{{base5}\\fad(120,150)\\blur6\\t(0,350,\\blur1)}}"
    else:
        tags = f"{{{base5}}}"
    return [dlg(5, start, end, "Keyword", tags + text)]


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: make_ass.py spec.json output.ass")
    with open(sys.argv[1], encoding="utf-8") as f:
        spec = json.load(f)

    res_x, res_y = spec.get("resolution", [1080, 1920])
    th = dict(THEMES[spec.get("theme", "hitech")])
    font = spec.get("font", "Poppins")
    scale = res_y / 1920.0
    th["cap_fs"] = int(th["caption_font_size"] * scale)
    th["scale"] = scale
    th["key_fs_base"] = th["keyword_font_size"]
    outline = max(1, int(th["outline"] * scale))

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {res_x}
PlayResY: {res_y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{th['cap_fs']},{th['caption_color']},{th['caption_color']},{th['caption_border']},&H96000000,-1,0,0,0,100,100,0,0,1,{outline},{th['shadow']},2,60,60,0,1
Style: Keyword,{font},{int(th['keyword_font_size'] * scale)},{th['accent']},{th['accent']},{th['accent_border']},&H96000000,-1,0,0,0,100,100,1,0,1,{outline},0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Text
"""
    cx, cy = res_x // 2, int(res_y * CAPTION_Y_FRAC)
    lines = []
    for c in spec.get("captions", []):
        lines += caption_events(c, cx, cy, th)
    for k in spec.get("keywords", []):
        lines += keyword_events(k, res_x, res_y, th, scale)

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")
    print(f"Wrote {sys.argv[2]}: {len(lines)} events from "
          f"{len(spec.get('captions', []))} captions + {len(spec.get('keywords', []))} keywords")


if __name__ == "__main__":
    main()
