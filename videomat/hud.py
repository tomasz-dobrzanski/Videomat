"""Grafiki w stylu pierwszego ekranu SOC Factory: karta, HUD, ikonki, karaoke „pro”.

Paleta z `Websitomat/stronki/soc/src/components/Hero.tsx`: granat #001a3d, lazur #0089ff, lód #9fd0ff,
akcent tytułu #4dabff, tekst pigułki blue-200 #bfdbfe. Ikony to kontury w stylu lucide (wypełnienie
przezroczyste, kreska = obrys ASS), animowane oszczędnie: puls, obrót, wsunięcie.

Zasada treści: grafiki nie pokazują danych, których nie ma (bateria, status łącza, numer piętra).
Ramki detekcji pochodzą tylko z prawdziwego wyniku modelu, nie stąd.
"""
from __future__ import annotations

import math
import re

NAVY = "&H3D1A00&"
AZURE = "&HFF8900&"
ICE = "&HFFD09F&"
LIGHT = "&HFFAB4D&"
BLUE200 = "&HFEDBBF&"
WHITE = "&HFFFFFF&"
GREEN = "&H5ADC3C&"      # #3CDC5A


def _ts(seconds: float) -> str:
    cs = max(0, int(round(seconds * 100)))
    h, rest = divmod(cs, 360000)
    m, rest = divmod(rest, 6000)
    s, c = divmod(rest, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _d(layer: int, start: float, end: float, style: str, text: str) -> str:
    return f"Dialogue: {layer},{_ts(start)},{_ts(end)},{style},,0,0,0,{text}"


def _esc(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", r"\N")


# ------------------------------------------------------------------ kształty
def circle(cx: float, cy: float, r: float) -> str:
    k = 0.5523 * r
    f = lambda v: f"{v:.1f}"  # noqa: E731
    return (f"m {f(cx - r)} {f(cy)} b {f(cx - r)} {f(cy - k)} {f(cx - k)} {f(cy - r)} {f(cx)} {f(cy - r)} "
            f"b {f(cx + k)} {f(cy - r)} {f(cx + r)} {f(cy - k)} {f(cx + r)} {f(cy)} "
            f"b {f(cx + r)} {f(cy + k)} {f(cx + k)} {f(cy + r)} {f(cx)} {f(cy + r)} "
            f"b {f(cx - k)} {f(cy + r)} {f(cx - r)} {f(cy + k)} {f(cx - r)} {f(cy)}")


def rrect(x: float, y: float, w: float, h: float, r: float) -> str:
    r = min(r, w / 2, h / 2)
    k = r * 0.4477
    f = lambda v: f"{v:.1f}"  # noqa: E731
    return (f"m {f(x + r)} {f(y)} l {f(x + w - r)} {f(y)} b {f(x + w - k)} {f(y)} {f(x + w)} {f(y + k)} {f(x + w)} {f(y + r)} "
            f"l {f(x + w)} {f(y + h - r)} b {f(x + w)} {f(y + h - k)} {f(x + w - k)} {f(y + h)} {f(x + w - r)} {f(y + h)} "
            f"l {f(x + r)} {f(y + h)} b {f(x + k)} {f(y + h)} {f(x)} {f(y + h - k)} {f(x)} {f(y + h - r)} "
            f"l {f(x)} {f(y + r)} b {f(x)} {f(y + k)} {f(x + k)} {f(y)} {f(x + r)} {f(y)}")


# Ikony w polu 100x100, rysowane konturem.
ICONS: dict[str, list[str]] = {
    "shield": ["m 50 4 b 66 14 80 16 92 16 l 92 46 b 92 72 72 88 50 96 b 28 88 8 72 8 46 l 8 16 b 20 16 34 14 50 4",
               "m 32 50 l 45 63 l 70 36"],
    "eye": ["m 4 50 b 22 18 78 18 96 50 b 78 82 22 82 4 50", circle(50, 50, 15)],
    "pin": ["m 50 96 b 30 70 14 54 14 36 b 14 16 30 4 50 4 b 70 4 86 16 86 36 b 86 54 70 70 50 96",
            circle(50, 36, 12)],
    "radar": [circle(50, 50, 44), circle(50, 50, 26), circle(50, 50, 6)],
    "route": ["m 8 86 b 34 86 26 46 50 46 b 74 46 66 14 90 14", "m 76 6 l 92 14 l 78 26"],
    "chip": [rrect(20, 20, 60, 60, 8), rrect(36, 36, 28, 28, 4),
             "m 36 20 l 36 6 m 50 20 l 50 6 m 64 20 l 64 6 m 36 80 l 36 94 m 50 80 l 50 94 m 64 80 l 64 94",
             "m 20 36 l 6 36 m 20 50 l 6 50 m 20 64 l 6 64 m 80 36 l 94 36 m 80 50 l 94 50 m 80 64 l 94 64"],
    "helmet": ["m 10 70 b 10 38 28 20 50 20 b 72 20 90 38 90 70 l 96 70 l 96 80 l 4 80 l 4 70 l 10 70",
               "m 50 20 l 50 46 m 34 26 l 38 50 m 66 26 l 62 50"],
    "vest": ["m 30 8 l 42 8 l 50 34 l 58 8 l 70 8 l 88 26 l 88 94 l 12 94 l 12 26 l 30 8",
             "m 12 62 l 42 62 m 58 62 l 88 62 m 50 34 l 50 94"],
    "bell": ["m 50 10 b 32 10 24 26 24 44 l 24 64 l 14 76 l 86 76 l 76 64 l 76 44 b 76 26 68 10 50 10",
             "m 40 86 b 42 94 58 94 60 86"],
    "stairs": ["m 6 92 l 6 74 l 28 74 l 28 54 l 50 54 l 50 34 l 72 34 l 72 14 l 94 14"],
    "bolt": ["m 56 4 l 18 56 l 46 56 l 38 96 l 82 40 l 54 40 l 56 4"],
    "camera": [rrect(6, 26, 88, 56, 10), circle(50, 54, 17), "m 32 26 l 38 14 l 62 14 l 68 26"],
}


def icon_events(name: str, x: float, y: float, size: float, start: float, end: float,
                layer: int = 6, color: str = AZURE, motion: str = "pulse", fade=(180, 200),
                bord: float = 2.6) -> list[str]:
    """Ikona konturowa (\\an7 w lewym górnym rogu x,y). motion: pulse | spin | none."""
    if name not in ICONS:
        return []
    scale = size / 100.0
    dur = int((end - start) * 1000)
    cx, cy = x + size / 2, y + size / 2
    anim = ""
    if motion == "pulse":
        t = 0
        while t + 1400 < dur and len(anim) < 1800:
            anim += (f"\\t({t + 700},{t + 1050},\\fscx{scale * 112:.0f}\\fscy{scale * 112:.0f})"
                     f"\\t({t + 1050},{t + 1400},\\fscx{scale * 100:.0f}\\fscy{scale * 100:.0f})")
            t += 1400
    # wejście: z małej skali i z rozmyciem (jak karta SOC)
    enter = (f"\\fscx{scale * 70:.0f}\\fscy{scale * 70:.0f}\\blur3"
             f"\\t(0,240,\\fscx{scale * 100:.0f}\\fscy{scale * 100:.0f}\\blur0.6)")
    base = (f"{{\\an7\\pos({x:.0f},{y:.0f})\\org({cx:.0f},{cy:.0f})\\p1\\1a&HFF&\\3c{color}\\bord{bord / scale * scale:.1f}"
            f"\\shad0\\fad({fade[0]},{fade[1]}){enter}{anim}}}")
    out = []
    for part in ICONS[name]:
        out.append(_d(layer, start, end, "Hud", base + part + "{\\p0}"))
    if name == "radar":          # wiązka radaru obraca się wokół środka
        beam = (f"{{\\an7\\pos({x:.0f},{y:.0f})\\org({cx:.0f},{cy:.0f})\\p1\\1c{color}\\1a&H50&\\bord0\\shad0"
                f"\\fscx{scale * 100:.0f}\\fscy{scale * 100:.0f}\\fad({fade[0]},{fade[1]})"
                f"\\t(0,{dur},\\frz{-360 * max(1, dur // 1600)})}}"
                f"m 50 50 l 50 6 b 66 6 80 14 88 28 l 50 50{{\\p0}}")
        out.append(_d(layer + 1, start, end, "Hud", beam))
    return out


# ------------------------------------------------------------------ karta SOC
def _wipe(x0: float, y0: float, w: float, h: float, a: int, b: int) -> str:
    return f"\\clip({x0:.0f},{y0:.0f},{x0 + 1:.0f},{y0 + h:.0f})\\t({a},{b},\\clip({x0:.0f},{y0:.0f},{x0 + w:.0f},{y0 + h:.0f}))"


def _accent_split(text: str) -> tuple[str, bool]:
    m = re.fullmatch(r"\*(.+)\*(.*)", text.strip())
    if m:
        return m.group(1) + m.group(2), True
    return text.replace("*", ""), False


def card_events(title: str, start: float, end: float, y0: int, kicker: str | None = None,
                icon: str | None = None, items: list[str] | None = None, size: int = 84,
                x0: int = 60, width: int = 960, sans: str = "Rajdhani SemiBold", mono: str = "Consolas") -> list[str]:
    """Szklana karta: pigułka z ikoną, dwie linie tytułu (druga w akcencie), wiersze kanału, pasek postępu."""
    items = items or []
    lines = [ln for ln in title.split("\n") if ln.strip()]
    pad = 36
    pill_h = 58
    lh = round(size * 1.06)
    row_h = 50
    y_pill = y0 + 30
    y_title = y_pill + pill_h + 22
    y_rows = y_title + len(lines) * lh + (16 if items else 0)
    y_bar = y_rows + len(items) * row_h + 22
    h = y_bar - y0 + 30
    dur = int((end - start) * 1000)
    out: list[str] = []
    fade = "\\fad(160,220)"

    # tło karty: wjazd od dołu + wyostrzenie
    out.append(_d(1, start, end, "Hud",
                  f"{{\\an7\\pos(0,0)\\p1\\1c{NAVY}\\1a&H38&\\3c&HFFFFFF&\\3a&HCC&\\bord2\\shad0{fade}"
                  f"\\blur6\\t(0,300,\\blur0.8)\\move(0,46,0,0,0,300)}}" + rrect(x0, y0, width, h, 28) + "{\\p0}"))
    # lewa listwa akcentu rośnie z góry na dół
    out.append(_d(2, start, end, "Hud",
                  f"{{\\an7\\pos(0,0)\\p1\\1c{AZURE}\\bord0\\shad0{fade}"
                  f"\\clip({x0},{y0 + 18},{x0 + 8},{y0 + 19})\\t(120,520,\\clip({x0},{y0 + 18},{x0 + 8},{y0 + h - 18}))}}"
                  + rrect(x0 + 1, y0 + 18, 6, h - 36, 3) + "{\\p0}"))
    # linia skanu przelatuje raz przez kartę
    out.append(_d(3, start, min(end, start + 0.75), "Hud",
                  f"{{\\an7\\p1\\1c{ICE}\\1a&H40&\\bord0\\shad0\\blur2\\move({x0},{y0},{x0},{y0 + h - 4},80,700)"
                  f"\\fad(80,150)}}m 0 0 l {width} 0 l {width} 3 l 0 3{{\\p0}}"))
    # pigułka (kicker) z ikoną
    if kicker:
        k = kicker.upper()
        pill_w = int(len(k) * 17.5 + (96 if icon else 52))
        out.append(_d(4, start + 0.14, end, "Hud",
                      f"{{\\an7\\pos(0,0)\\p1\\1c{AZURE}\\1a&HE0&\\3c{AZURE}\\3a&H70&\\bord2\\shad0{fade}"
                      f"\\move(-24,0,0,0,140,380)}}" + rrect(x0 + pad, y_pill, pill_w, pill_h, pill_h / 2) + "{\\p0}"))
        tx = x0 + pad + (70 if icon else 26)
        out.append(_d(5, start + 0.14, end, "Hud",
                      f"{{\\an4\\move({tx - 24},{y_pill + pill_h / 2:.0f},{tx},{y_pill + pill_h / 2:.0f},140,380)"
                      f"\\fn{sans}\\fs30\\fsp3\\b1\\c{BLUE200}\\bord0\\shad0{fade}}}" + _esc(k)))
        if icon:
            out += icon_events(icon, x0 + pad + 18, y_pill + 11, 36, start + 0.2, end, layer=6,
                               color=AZURE, motion="spin" if icon == "radar" else "pulse")
    # tytuł: każda linia odsłaniana wipe'em, akcentowana z poświatą
    for i, raw in enumerate(lines):
        text, accent = _accent_split(raw)
        y = y_title + i * lh
        a = 220 + i * 120
        clip = _wipe(x0 + pad, y - 6, width - 2 * pad, lh + 10, a, a + 320)
        if accent:
            out.append(_d(6, start, end, "Hud",
                          f"{{\\an7\\pos({x0 + pad},{y})\\fn{sans}\\fs{size}\\b1\\c{AZURE}\\alpha&H70&\\bord0"
                          f"\\shad0\\blur10{fade}{clip}}}" + _esc(text)))
        out.append(_d(7, start, end, "Hud",
                      f"{{\\an7\\pos({x0 + pad},{y})\\fn{sans}\\fs{size}\\b1\\c{LIGHT if accent else WHITE}"
                      f"\\bord0\\shad0{fade}{clip}}}" + _esc(text)))
    # wiersze jak kanał zdarzeń
    for i, row in enumerate(items):
        name, _, label = row.partition("|")
        if not label:
            name, label = "", name
        y = y_rows + i * row_h
        t0 = 0.46 + i * 0.11
        if name:
            out += icon_events(name, x0 + pad, y + 4, 34, start + t0, end, layer=6, color=ICE, motion="none",
                               bord=2.4)
        out.append(_d(7, start + t0, end, "Hud",
                      f"{{\\an7\\move({x0 + pad + 30},{y + 4},{x0 + pad + 54},{y + 4},0,260)\\fn{mono}\\fs32"
                      f"\\c{WHITE}\\alpha&H20&\\bord0\\shad0{fade}}}" + _esc(label)))
    # pasek postępu (jak kropka aktywnego slajdu w karuzeli)
    bx, bw = x0 + pad, width - 2 * pad
    out.append(_d(2, start, end, "Hud", f"{{\\an7\\pos(0,0)\\p1\\1c&HFFFFFF&\\1a&HE6&\\bord0\\shad0{fade}}}"
                  + rrect(bx, y_bar, bw, 5, 2.5) + "{\\p0}"))
    out.append(_d(3, start, end, "Hud", f"{{\\an7\\pos(0,0)\\p1\\1c{AZURE}\\bord0\\shad0{fade}"
                  f"\\clip({bx},{y_bar - 2},{bx + 1},{y_bar + 8})\\t(0,{dur},\\clip({bx},{y_bar - 2},{bx + bw},{y_bar + 8}))}}"
                  + rrect(bx, y_bar, bw, 5, 2.5) + "{\\p0}"))
    return out


# ------------------------------------------------------------------ HUD w rogach
def hud_events(start: float, end: float, label: str = "PATROL AUTONOMICZNY", right: str = "ANALIZA AI",
               y: int = 250, sans: str = "Rajdhani SemiBold") -> list[str]:
    """Lewy chip: pulsujący punkt + etykieta. Prawy chip: radar + korektor „analizy” (dekoracja, nie dane)."""
    out: list[str] = []
    dur = int((end - start) * 1000)
    fade = "\\fad(400,400)"
    lw = int(len(label) * 15.5 + 70)
    out.append(_d(1, start, end, "Hud", f"{{\\an7\\pos(0,0)\\p1\\1c{NAVY}\\1a&H50&\\3c&HFFFFFF&\\3a&HD0&\\bord1.5\\shad0{fade}}}"
                  + rrect(60, y, lw, 50, 25) + "{\\p0}"))
    blink = ""
    t = 0
    while t + 1200 < dur and len(blink) < 2400:
        blink += f"\\t({t + 600},{t + 900},\\alpha&HB0&)\\t({t + 900},{t + 1200},\\alpha&H00&)"
        t += 1200
    out.append(_d(2, start, end, "Hud", f"{{\\an7\\pos(0,0)\\p1\\1c{GREEN}\\bord0\\shad0\\blur1{fade}{blink}}}"
                  + circle(86, y + 25, 7) + "{\\p0}"))
    out.append(_d(2, start, end, "Hud", f"{{\\an4\\pos(104,{y + 25})\\fn{sans}\\fs26\\fsp3\\b1\\c{BLUE200}\\bord0\\shad0{fade}}}"
                  + _esc(label)))
    # prawy chip
    rw = int(len(right) * 15.5 + 150)
    rx = 1020 - rw
    out.append(_d(1, start, end, "Hud", f"{{\\an7\\pos(0,0)\\p1\\1c{NAVY}\\1a&H50&\\3c&HFFFFFF&\\3a&HD0&\\bord1.5\\shad0{fade}}}"
                  + rrect(rx, y, rw, 50, 25) + "{\\p0}"))
    out += icon_events("radar", rx + 14, y + 7, 36, start, end, layer=2, color=AZURE, motion="none", fade=(400, 400),
                       bord=2.0)
    out.append(_d(2, start, end, "Hud", f"{{\\an4\\pos({rx + 60},{y + 25})\\fn{sans}\\fs26\\fsp3\\b1\\c{BLUE200}\\bord0\\shad0{fade}}}"
                  + _esc(right)))
    # korektor: 5 słupków, każdy z własnym rytmem
    bx0 = rx + rw - 72
    for i in range(5):
        period = 260 + i * 70
        hs = [10, 26, 16, 30, 12, 22]
        anim, t = "", 0
        j = i
        while t + period < dur and len(anim) < 3000:
            hgt = hs[j % len(hs)]
            anim += f"\\t({t},{t + period},\\fscy{hgt * 100 // 30})"
            t += period
            j += 2
        out.append(_d(2, start, end, "Hud",
                      f"{{\\an1\\pos({bx0 + i * 11},{y + 40})\\p1\\1c{ICE}\\bord0\\shad0{fade}\\fscy40{anim}}}"
                      f"m 0 0 l 6 0 l 6 -30 l 0 -30{{\\p0}}"))
    return out


# ------------------------------------------------------------------ karaoke „pro”
def karaoke_pro(groups: list[list[dict]], y: int, cx: int, size: int, offset: float = 0.0,
                sans: str = "Rajdhani SemiBold") -> list[str]:
    """Fraza wchodzi z rozmyciem i lekkim uniesieniem; słowa przechodzą z przygaszonych w pełną biel
    (\\kf), pod frazą lazurowa linia rośnie w tempie mowy."""
    # jedna linia na frazę: dzielimy grupy, które by się zawinęły (~0,45 em na znak)
    limit = max(12, int(880 / (size * 0.45)))
    lines: list[list[dict]] = []
    for g in groups:
        cur: list[dict] = []
        for w in g:
            if cur and len(" ".join(x["w"] for x in cur + [w])) > limit:
                lines.append(cur)
                cur = []
            cur.append(w)
        if cur:
            lines.append(cur)
    groups = lines
    events = []
    for gi, words in enumerate(groups):
        if not words:
            continue
        body = ""
        for i, w in enumerate(words):
            nxt = words[i + 1]["start"] if i + 1 < len(words) else w["end"]
            body += f"{{\\kf{max(int(round((nxt - w['start']) * 100)), 8)}}}{_esc(w['w'])} "
        text = re.sub(r"[.]+$", "", body.strip())
        start = offset + words[0]["start"]
        end = offset + words[-1]["end"] + 0.25
        if gi + 1 < len(groups) and groups[gi + 1]:
            end = min(end, offset + groups[gi + 1][0]["start"] - 0.02)
        end = max(end, offset + words[-1]["end"] - 0.02)
        dur = int((end - start) * 1000)
        speak = int((words[-1]["end"] - words[0]["start"]) * 1000)
        common = (f"\\an2\\fn{sans}\\fs{size}\\b1\\fad(90,80)\\fscx94\\fscy94\\t(0,160,\\fscx100\\fscy100)"
                  f"\\move({cx},{y + 16},{cx},{y},0,160)")
        # cień pod tekstem dla czytelności na jasnym tle
        events.append(_d(3, start, end, "Narr",
                         f"{{{common}\\1c&H000000&\\1a&H90&\\bord0\\shad0\\blur12}}" + re.sub(r"\{\\kf\d+\}", "", text)))
        events.append(_d(4, start, end, "Narr",
                         f"{{{common}\\1c{WHITE}\\2c{WHITE}\\2a&H58&\\3c{NAVY}\\bord4\\shad0}}" + text))
        # linia postępu pod frazą
        w_est = min(900, int(len(re.sub(r"\{[^}]*\}", "", text)) * size * 0.43))
        x1 = cx - w_est // 2
        events.append(_d(4, start, end, "Narr",
                         f"{{\\an7\\pos(0,0)\\p1\\1c{AZURE}\\bord0\\shad0\\fad(90,80)"
                         f"\\clip({x1},{y + 6},{x1 + 1},{y + 16})\\t(0,{max(speak, 200)},\\clip({x1},{y + 6},{x1 + w_est},{y + 16}))}}"
                         + rrect(x1, y + 8, w_est, 5, 2.5) + "{\\p0}"))
        _ = dur
    return events


def caption_badge(name: str, cx: float, y: float, start: float, end: float) -> list[str]:
    """Ikonka pod napisem w okrągłym znaczku (granat + lazurowy pierścień), wejście z rozmyciem."""
    r = 34
    out = [_d(5, start, end, "Hud",
              f"{{\\an7\\pos(0,0)\\p1\\1c{NAVY}\\1a&H40&\\3c{AZURE}\\3a&H50&\\bord2\\shad0\\fad(180,200)"
              f"\\blur4\\t(0,240,\\blur0.6)}}" + circle(cx, y + r, r) + "{\\p0}")]
    size = 40
    out += icon_events(name, cx - size / 2, y + r - size / 2, size, start, end, layer=6, color=ICE,
                       motion="spin" if name == "radar" else "pulse", bord=2.4)
    return out


# ------------------------------------------------------------------ karta minimalistyczna
_FONTS: dict = {}


def text_width(text: str, size: int, font_file: str) -> float:
    """Szerokość tekstu w px z metryk fontu (PIL), z zapasem na pogrubienie libass."""
    from PIL import ImageFont
    key = (font_file, size)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(font_file, size)
    return _FONTS[key].getlength(text) * 1.02


def card_min_events(title: str, start: float, end: float, y0: int, kicker: str | None,
                    font_file: str, size: int = 80, x0: int = 60, sans: str = "Rajdhani SemiBold") -> list[str]:
    """Spokojna karta: cienka ramka dopasowana do tekstu, lazurowa listwa, odsłanianie linii, kreska czasu."""
    lines = [ln for ln in title.split("\n") if ln.strip()]
    texts = [_accent_split(ln) for ln in lines]
    pad, lh = 34, round(size * 1.08)
    k = (kicker or "").upper()
    k_size, k_sp = 26, 4
    k_w = text_width(k, k_size, font_file) + k_sp * len(k) if k else 0
    w_text = max([text_width(t, size, font_file) for t, _ in texts] + [k_w])
    width = int(min(960, w_text + 2 * pad + 8))
    y_k = y0 + 26
    y_t = y_k + (k_size + 18 if k else 0)
    h = y_t - y0 + len(lines) * lh + 30
    dur = int((end - start) * 1000)
    fade = "\\fad(200,240)"
    rise = "\\move(0,24,0,0,0,280)"
    out = [
        _d(1, start, end, "Hud", f"{{\\an7\\pos(0,0)\\p1\\1c{NAVY}\\1a&H30&\\3c&HFFFFFF&\\3a&HD8&\\bord1.2\\shad0{fade}{rise}}}"
           + rrect(x0, y0, width, h, 16) + "{\\p0}"),
        _d(2, start, end, "Hud", f"{{\\an7\\pos(0,0)\\p1\\1c{AZURE}\\bord0\\shad0{fade}{rise}"
           f"\\clip({x0},{y0},{x0 + 6},{y0 + 1})\\t(100,460,\\clip({x0},{y0},{x0 + 6},{y0 + h}))}}"
           + rrect(x0, y0 + 14, 4, h - 28, 2) + "{\\p0}"),
    ]
    if k:
        out.append(_d(3, start + 0.12, end, "Hud",
                      f"{{\\an7\\move({x0 + pad},{y_k + 20},{x0 + pad},{y_k},120,400)\\fn{sans}\\fs{k_size}\\fsp{k_sp}\\b1"
                      f"\\c{ICE}\\bord0\\shad0{fade}}}" + _esc(k)))
    for i, (text, accent) in enumerate(texts):
        y = y_t + i * lh
        a = 200 + i * 130
        clip = _wipe(x0 + pad, y - 6, width - pad, lh + 12, a, a + 340)
        out.append(_d(4, start, end, "Hud",
                      f"{{\\an7\\pos({x0 + pad},{y})\\fn{sans}\\fs{size}\\b1\\c{LIGHT if accent else WHITE}"
                      f"\\bord0\\shad0{fade}{clip}}}" + _esc(text)))
    bx, by = x0 + pad, y0 + h - 14
    out.append(_d(3, start, end, "Hud", f"{{\\an7\\pos(0,0)\\p1\\1c{AZURE}\\1a&H30&\\bord0\\shad0{fade}"
                  f"\\clip({bx},{by - 2},{bx + 1},{by + 5})\\t(0,{dur},\\clip({bx},{by - 2},{x0 + width - pad},{by + 5}))}}"
                  + rrect(bx, by, width - 2 * pad, 2.5, 1.2) + "{\\p0}"))
    return out
