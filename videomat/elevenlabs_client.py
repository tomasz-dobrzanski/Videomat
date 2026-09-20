"""Minimalny klient ElevenLabs przez requests (bez SDK). Klucz wyłącznie z env ELEVENLABS_API_KEY.

Endpointy (dokumentacja ElevenLabs, sprawdzone 2026-09-18):
  POST /v1/text-to-speech/{voice_id}                  -> audio
  POST /v1/text-to-speech/{voice_id}/with-timestamps  -> {audio_base64, alignment{characters, character_start_times_seconds, character_end_times_seconds}}
  POST /v1/music                                      -> audio  (prompt | composition_plan, music_length_ms, force_instrumental, model_id)
  POST /v1/sound-generation                           -> audio  (text, duration_seconds 0.5–30, prompt_influence, loop)
  GET  /v1/voices, GET /v1/models, GET /v1/user/subscription
"""
from __future__ import annotations

import time

import requests

from . import config

BASE = "https://api.elevenlabs.io"


class ElevenLabsError(RuntimeError):
    pass


def _headers(json_body: bool = True) -> dict:
    h = {"xi-api-key": config.require_key("ELEVENLABS_API_KEY")}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _explain(r: requests.Response) -> str:
    hints = {
        401: "nieprawidłowy klucz API (sprawdź .env)",
        402: "brak kredytów / funkcja niedostępna w planie",
        403: "brak uprawnień klucza do tej funkcji (np. Music wymaga odpowiedniego planu)",
        422: "błędne parametry żądania",
        429: "limit zapytań — spróbuj za chwilę",
    }
    try:
        detail = r.json()
    except Exception:
        detail = r.text[:400]
    return f"HTTP {r.status_code} ({hints.get(r.status_code, 'błąd')}): {detail}"


def _post(path: str, body: dict, params: dict | None = None, timeout: int = 300, retries: int = 2) -> requests.Response:
    url = BASE + path
    for attempt in range(retries + 1):
        r = requests.post(url, headers=_headers(), json=body, params=params, timeout=timeout)
        if r.status_code == 429 and attempt < retries:
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code >= 400:
            raise ElevenLabsError(_explain(r))
        return r
    raise ElevenLabsError("retries exhausted")


def get(path: str, timeout: int = 60) -> dict:
    r = requests.get(BASE + path, headers=_headers(False), timeout=timeout)
    if r.status_code >= 400:
        raise ElevenLabsError(_explain(r))
    return r.json()


def list_voices() -> list[dict]:
    return [{"voice_id": v["voice_id"], "name": v.get("name"), "labels": v.get("labels", {})}
            for v in get("/v1/voices").get("voices", [])]


def subscription() -> dict:
    return get("/v1/user/subscription")
