"""Mówiący avatar z fotki: Veo 3.1 (Gemini API) image-to-video, 9:16.

OGRANICZENIA (z dokumentacji Veo 3.1, 2026-09-18):
- Veo generuje audio natywnie z promptu; NIE przyjmuje zewnętrznego pliku audio -> brak dokładnego
  lip-syncu do lektora ElevenLabs. Stąd dwa tryby:
    veo-voice    : dialog w promptcie, Veo mówi własnym głosem, usta zsynchronizowane (rekomendowany start)
    eleven-voice : Veo generuje "mówi spokojnie do kamery" bez konkretnych słów; lektor ElevenLabs
                   podkładany w assemble (usta w ruchu, bez dokładnej synchronizacji)
- Klip 4/6/8 s (1080p wymaga 8 s). Dłuższy skrypt -> kilka klipów po zdaniach, ta sama fotka jako image.
- image-to-video z osobą: person_generation="allow_adult" (jedyna dozwolona wartość, także w UE).
- Veo NIE jest w free tier. Orientacyjnie: Fast 720p ~$0.10/s, Fast 1080p ~$0.12/s, Standard ~$0.40/s.
- Pliki na serwerze Google są kasowane po 2 dniach -> pobieramy natychmiast.
Klucz wyłącznie z env GEMINI_API_KEY.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import config

MODELS = {
    "fast": "veo-3.1-fast-generate-preview",
    "standard": "veo-3.1-generate-preview",
}
PRICE_PER_S = {("fast", "720p"): 0.10, ("fast", "1080p"): 0.12, ("standard", "720p"): 0.40, ("standard", "1080p"): 0.40}
MAX_CLIP_S = 8


def estimate_cost(n_clips: int, seconds: int, tier: str, resolution: str) -> float:
    return round(n_clips * seconds * PRICE_PER_S.get((tier, resolution), 0.40), 2)


def split_script(script: str, max_chars: int = 140) -> list[str]:
    """Dzieli skrypt na zdania mieszczące się w ~8 s mowy (~140 znaków PL)."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", script.strip()) if s.strip()]
    out, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) + 1 > max_chars:
            out.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def build_prompt(mode: str, line: str | None, style: str, language: str = "polsku") -> str:
    base = (f"Ta sama osoba co na zdjęciu, portret pionowy 9:16, patrzy w kamerę, naturalne oświetlenie, "
            f"{style}. Delikatny ruch głowy i mimika, ręce spokojne, tło bez zmian, brak napisów na obrazie.")
    if mode == "veo-voice":
        return base + f' Osoba mówi wyraźnie po {language} do kamery: "{line}". Bez muzyki w tle.'
    return base + " Osoba mówi spokojnie do kamery, usta w naturalnym ruchu mowy. Bez wyraźnych słów, bez muzyki."


def generate_clips(photo: str | Path, script: str, out_dir: str | Path, mode: str = "veo-voice",
                   tier: str = "fast", resolution: str = "720p", seconds: int = 8,
                   style: str = "nowoczesne biuro technologiczne, styl korporacyjny",
                   negative_prompt: str = "napisy, tekst, logo, zniekształcona twarz, dodatkowe osoby",
                   dry_run: bool = False, confirm=None) -> dict:
    """Zwraca {"clips": [Path], "prompts": [...], "cost_estimate": float}."""
    photo, out_dir = Path(photo), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = split_script(script) if mode == "veo-voice" else [None]
    seconds = 8 if resolution != "720p" else seconds
    prompts = [build_prompt(mode, ln, style) for ln in lines]
    cost = estimate_cost(len(prompts), seconds, tier, resolution)
    plan = {"model": MODELS[tier], "resolution": resolution, "seconds": seconds, "mode": mode,
            "clips": len(prompts), "cost_estimate_usd": cost, "prompts": prompts}
    (out_dir / "avatar_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    if dry_run:
        return {"clips": [], "plan": plan}
    if confirm and not confirm(plan):
        return {"clips": [], "plan": plan, "cancelled": True}

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.require_key("GEMINI_API_KEY"))
    image = types.Image.from_file(location=str(photo))
    clips = []
    for i, prompt in enumerate(prompts, 1):
        op = client.models.generate_videos(
            model=MODELS[tier], prompt=prompt, image=image,
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16", resolution=resolution, duration_seconds=str(seconds),
                person_generation="allow_adult", negative_prompt=negative_prompt, number_of_videos=1,
            ),
        )
        t0 = time.time()
        while not op.done:
            if time.time() - t0 > 900:
                raise SystemExit("Veo: przekroczono 15 min oczekiwania na klip.")
            time.sleep(10)
            op = client.operations.get(op)
        if getattr(op, "error", None):
            raise SystemExit(f"Veo error: {op.error}")
        vid = op.response.generated_videos[0]
        out = out_dir / f"avatar_{i:02d}.mp4"
        client.files.download(file=vid.video)
        vid.video.save(str(out))
        clips.append(out)
        (out.with_suffix(".prompt.txt")).write_text(prompt, encoding="utf-8")
    return {"clips": clips, "plan": plan}
