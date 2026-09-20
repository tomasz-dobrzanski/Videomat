"""Dzielenie słów z timestampami na frazy napisów (reguły ze SKILL.md):
3–6 słów, 1–2.5 s, max 2 linie; czasownik i dopełnienie razem gdy się da (heurystyka: nie łam po
spójnikach/przyimkach); bez kropki na końcu chunku; opcjonalne przyciąganie granic do cięć scen.
"""
from __future__ import annotations

import re

MAX_WORDS = 6
MIN_WORDS = 2
MAX_DUR = 2.5
GAP_BREAK = 0.6          # pauza > 0.6 s zawsze kończy frazę
NO_BREAK_AFTER = {"i", "a", "w", "z", "na", "do", "od", "po", "za", "o", "u", "że", "nie", "się",
                  "bo", "ale", "lub", "czy", "the", "a", "an", "to", "of", "in", "on", "and", "or"}
SENTENCE_END = re.compile(r"[.!?…]+$")


def _clean(text: str) -> str:
    text = text.strip()
    return SENTENCE_END.sub("", text) if len(text) > 2 else text


def chunk_words(words: list[dict], scene_cuts: list[float] | None = None, snap: float = 0.25,
                max_words: int | None = None) -> list[dict]:
    """words: [{"w","start","end"}] -> [{"text","start","end"}]

    max_words: limit słów we frazie (domyślnie MAX_WORDS). Duże napisy potrzebują krótszych fraz.
    """
    limit = MAX_WORDS if max_words is None else max_words
    chunks, cur = [], []

    def flush():
        if cur:
            chunks.append({"text": _clean(" ".join(w["w"] for w in cur)),
                           "start": cur[0]["start"], "end": cur[-1]["end"]})
            cur.clear()

    for i, w in enumerate(words):
        if not w["w"]:
            continue
        if cur:
            gap = w["start"] - cur[-1]["end"]
            dur = w["end"] - cur[0]["start"]
            prev = cur[-1]["w"]
            ends_sentence = bool(SENTENCE_END.search(prev))
            must = gap > GAP_BREAK or len(cur) >= limit or dur > MAX_DUR
            want = ends_sentence or (prev.endswith(",") and len(cur) >= MIN_WORDS)
            bad_break = prev.lower().strip(",.") in NO_BREAK_AFTER and len(cur) < limit
            if must or (want and not bad_break):
                flush()
        cur.append(dict(w))
    flush()

    # scal osamotnione pojedyncze słowa z poprzednim chunkiem jeśli mieści się w limitach
    merged: list[dict] = []
    for c in chunks:
        if merged and len(c["text"].split()) == 1:
            p = merged[-1]
            if len(p["text"].split()) < limit and c["end"] - p["start"] <= MAX_DUR + 0.5:
                p["text"] = _clean(p["text"] + " " + c["text"]); p["end"] = c["end"]
                continue
        merged.append(c)

    # domknij mikro-przerwy między frazami (ciągłość) i przyciągnij do cięć scen
    for i, c in enumerate(merged):
        if i + 1 < len(merged) and merged[i + 1]["start"] - c["end"] < 0.35:
            c["end"] = merged[i + 1]["start"]
        if scene_cuts:
            for t in scene_cuts:
                if abs(t - c["end"]) <= snap and c["end"] != t and t > c["start"] + 0.4:
                    c["end"] = round(t, 2)
                    if i + 1 < len(merged):
                        merged[i + 1]["start"] = round(t, 2)
        c["start"], c["end"] = round(c["start"], 2), round(max(c["end"], c["start"] + 0.4), 2)
    return merged


def chunks_from_segments(segments: list[dict], **kw) -> list[dict]:
    """Segmenty bez słów (np. z SRT) -> frazy z czasem proporcjonalnym do liczby znaków."""
    out = []
    for s in segments:
        if s.get("words"):
            out += chunk_words(s["words"], **kw)
            continue
        words = s["text"].split()
        if not words:
            continue
        groups = [words[i:i + 4] for i in range(0, len(words), 4)]
        total = sum(len(" ".join(g)) for g in groups) or 1
        t = s["start"]
        for g in groups:
            d = (s["end"] - s["start"]) * len(" ".join(g)) / total
            out.append({"text": _clean(" ".join(g)), "start": round(t, 2), "end": round(t + d, 2)})
            t += d
    return out


def parse_srt(path: str) -> list[dict]:
    import re as _re
    txt = open(path, encoding="utf-8-sig").read()
    segs = []
    for block in _re.split(r"\n\s*\n", txt.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        m = _re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", block)
        if not m:
            continue
        g = list(map(int, m.groups()))
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        text = " ".join(l for l in lines if "-->" not in l and not l.strip().isdigit())
        segs.append({"start": a, "end": b, "text": _re.sub(r"<[^>]+>", "", text)})
    return segs
