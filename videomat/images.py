"""Plansze / B-roll stills z Gemini image generation (gemini-3.1-flash-image, 9:16). Płatne (nie free tier).

    generate_image("minimalist dark tech background with subtle circuit lines", "work/bg.png")
    generate_image("...", "work/x.png", reference="photo.jpg")   # edycja z fotką wejściową
"""
from __future__ import annotations

from pathlib import Path

from . import config

DEFAULT_MODEL = "gemini-3.1-flash-image"


def generate_image(prompt: str, out_path: str | Path, reference: str | Path | None = None,
                   aspect_ratio: str = "9:16", model: str = DEFAULT_MODEL) -> Path:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.require_key("GEMINI_API_KEY"))
    contents: list = [prompt]
    if reference:
        from PIL import Image
        contents.append(Image.open(reference))
    resp = client.models.generate_content(
        model=model, contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            out_path.write_bytes(part.inline_data.data)
            return out_path
    raise SystemExit("Gemini nie zwrócił obrazu (sprawdź prompt / billing).")
