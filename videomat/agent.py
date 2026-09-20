"""Prompt → montaż. Model językowy dostaje spis materiału i pisze plan filmu, nie kod.

Model NIE dostaje do ręki assetów ani tekstu cytatów. Może wybrać zakres klipu (scena typu clip),
a słowa na ekranie i tak powstaną z transkrypcji — więc nie jest w stanie włożyć komuś w usta
zdania, którego nie powiedział. Może pisać wyłącznie teksty własne: lektora i plansze.

    plan = propose(film, assets, "skróć intro o sekundę", provider=OpenAIProvider())
    new_film, changes = apply_plan(film, plan)
"""
from __future__ import annotations

import json
import os
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from . import config
from .timeline import Film, MusicEvent, NarrationLine, Scene

DEFAULT_MODEL_ENV = "VIDEOMAT_LLM_MODEL"


class AgentError(RuntimeError):
    pass


def explain(exc: Exception) -> str:
    """Zamienia błąd dostawcy na zdanie, które coś znaczy dla człowieka."""
    text = str(exc)
    if "insufficient_quota" in text or "credit_balance_exhausted" in text:
        return ("Konto OpenAI nie ma środków — doładuj je w panelu rozliczeń, "
                "żeby korzystać z promptu. Montaż ręczny działa niezależnie.")
    if "invalid_api_key" in text or "Incorrect API key" in text:
        return "Klucz OPENAI_API_KEY jest nieprawidłowy — popraw go w .env."
    if "429" in text:
        return "Limit zapytań do modelu. Spróbuj za chwilę."
    if "model_not_found" in text or "does not exist" in text:
        return ("Wybrany model jest niedostępny na tym koncie. "
                "Wskaż inny przez VIDEOMAT_LLM_MODEL w .env.")
    return f"Model nie odpowiedział: {text[:200]}"


class FilmPlan(BaseModel):
    """To, co model może napisać: linie lektora, sceny i sterowanie muzyką."""

    model_config = ConfigDict(extra="forbid")

    narration: list[NarrationLine] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    music_events: list[MusicEvent] = Field(default_factory=list)
    notes: str = Field(default="", description="Krótkie wyjaśnienie zmian dla człowieka.")


RULES = """Jesteś montażystą krótkich filmów pionowych 9:16 (1080x1920, 30 kl./s).
Układasz montaż jako listę scen. Obowiązują zasady:

1. PRAWDA. Scena typu "clip" pokazuje fragment nagrania; napisy powstają automatycznie ze słów
   transkrypcji z zakresu start..end. Nie wolno Ci wpisywać cudzych wypowiedzi jako tekstu warstw.
   Teksty warstw i lektora to Twoje własne słowa — komentarz, nie cytat.
2. Nie twierdź rzeczy, których nie ma w materiale ani w poleceniu użytkownika. Dat, liczb i nazwisk
   nie zgadujesz.
3. BEZPIECZNE POLE. Tekst mieści się w x 60-1020 i y 250-1600. Napisy cytatów siedzą na y 1560,
   napisy lektora na y 1500 (albo 360, gdy dół kadru jest zajęty).
4. RYTM. Coś się rusza co 1-2 sekundy. Nie zostawiaj statycznej planszy dłużej niż 3 sekundy bez
   zmiany. Jeden styl napisów w całym filmie.
5. DŁUGOŚĆ SCEN. Zostaw duration puste, gdy scena ma się dopasować do lektora: użyj min_duration
   i tail. Sceny typu clip biorą długość z zakresu start..end.
6. CZASY. Zamiast liczb bezwzględnych używaj odniesień: "vo3.end+0.25" wewnątrz sceny,
   "nazwa_sceny.end" dla zdarzeń muzyki.

Typy scen: black (plansza), clip (fragment nagrania), freeze (zatrzymana klatka), still (klatka z
powolnym najazdem, zoom=true).
Typy warstw: title, subtitle, headline, stamp, counter, panel, shape, board, word_list, grid.
W tekście warstwy działa prosta składnia: [c:accent] [c:grey] [c:white] [fs:60] [b:0] [/].
"""


class Provider(Protocol):
    def complete(self, system: str, user: str, schema_model: type[BaseModel]) -> BaseModel: ...


class OpenAIProvider:
    """Dostawca OpenAI. Nazwa modelu nie jest zaszyta — bierzemy ją z .env albo z listy modeli."""

    def __init__(self, model: str | None = None):
        key = config.env("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise AgentError("Brak OPENAI_API_KEY — wpisz klucz do .env.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AgentError("Brak pakietu openai. Zainstaluj: pip install openai") from exc
        self.client = OpenAI(api_key=key)
        self.model = model or config.env(DEFAULT_MODEL_ENV) or self._guess_model()

    # Warianty nieprzydatne do pisania montażu: kodowanie, mowa, obrazy, wyszukiwarka, migawki czatu.
    EXCLUDE = ("codex", "audio", "realtime", "transcribe", "tts", "image", "search",
               "moderation", "embedding", "nano", "live", "chat-latest", "-pro")
    PREFERRED = ("gpt-6-astra", "gpt-5.5", "gpt-5.4", "gpt-5.2", "o4-mini")

    def _guess_model(self) -> str:
        try:
            names = {m.id for m in self.client.models.list().data}
        except Exception as exc:
            raise AgentError(f"Nie mogę pobrać listy modeli: {str(exc)[:160]}") from exc
        for candidate in self.PREFERRED:
            if candidate in names:
                return candidate
        usable = [n for n in names if n.startswith("gpt-")
                  and not any(bad in n for bad in self.EXCLUDE)]
        if not usable:
            raise AgentError("Konto nie udostępnia modelu tekstowego nadającego się do montażu. "
                             f"Wskaż model przez {DEFAULT_MODEL_ENV} w .env.")

        def version(name: str) -> tuple:
            import re as _re
            found = _re.findall(r"(\d+)(?:\.(\d+))?", name)
            return tuple(int(part or 0) for part in (found[0] if found else ("0", "0")))

        usable.sort(key=lambda n: (version(n), -len(n)), reverse=True)
        return usable[0]

    def complete(self, system: str, user: str, schema_model: type[BaseModel]) -> BaseModel:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            response = self.client.responses.parse(model=self.model, input=messages,
                                                   text_format=schema_model)
            parsed = response.output_parsed
            if parsed is not None:
                return parsed
        except Exception as exc:
            last = exc
        else:
            last = AgentError("Model nie zwrócił planu.")
        # Zapas: zwykła odpowiedź tekstowa z wymuszonym JSON-em i walidacją po naszej stronie.
        schema = json.dumps(schema_model.model_json_schema(), ensure_ascii=False)
        fallback_user = (f"{user}\n\nOdpowiedz wyłącznie obiektem JSON zgodnym z tym schematem "
                         f"(bez komentarzy, bez bloku markdown):\n{schema}")
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[{"role": "system", "content": system}, {"role": "user", "content": fallback_user}],
            )
            text = response.output_text
        except Exception as exc:
            raise AgentError(explain(exc)) from last
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            text = text.split("\n", 1)[1] if "\n" in text else text
        try:
            return schema_model.model_validate_json(text)
        except Exception as exc:
            raise AgentError(f"Plan modelu nie przeszedł walidacji: {str(exc)[:300]}") from exc


def describe_assets(overview: dict) -> str:
    """Spis materiału podawany modelowi: klipy z transkryptem, muzyka, głos."""
    lines = ["MATERIAŁ (tylko te klucze wolno Ci używać):"]
    for clip in overview.get("clips", []):
        lines.append(f'- klip "{clip["key"]}" długość {clip.get("duration")} s')
        for seg in clip.get("segments", [])[:40]:
            lines.append(f'    {seg["start"]:.2f}-{seg["end"]:.2f}  {seg["text"]}')
        if not clip.get("segments"):
            lines.append("    (brak transkrypcji — nie da się zrobić napisów z tego klipu)")
    for music in overview.get("music", []):
        lines.append(f'- muzyka "{music["key"]}" długość {music.get("duration")} s')
    for item in overview.get("sfx", []):
        lines.append(f'- efekt "{item["key"]}"')
    if overview.get("narration"):
        lines.append("ISTNIEJĄCE LINIE LEKTORA:")
        for n in overview["narration"]:
            lines.append(f'- {n["id"]} ({n["duration"]} s): {n["text"]}')
    return "\n".join(lines)


def propose(film: Film, overview: dict, instruction: str, provider: Provider | None = None) -> FilmPlan:
    """Zwraca plan zmian. Nie dotyka pliku — zapis jest osobną decyzją użytkownika."""
    provider = provider or OpenAIProvider()
    current = {
        "narration": [n.model_dump(mode="json") for n in film.narration],
        "scenes": [s.model_dump(mode="json", exclude_defaults=True) for s in film.scenes],
        "music_events": [e.model_dump(mode="json") for e in (film.music.events if film.music else [])],
    }
    has_film = bool(film.scenes)
    user = (
        f"{describe_assets(overview)}\n\n"
        + (f"OBECNY MONTAŻ (JSON):\n{json.dumps(current, ensure_ascii=False)}\n\n" if has_film else "")
        + ("POLECENIE: " if has_film else "ZBUDUJ FILM OD ZERA: ")
        + instruction
        + ("\n\nZwróć KOMPLETNY montaż po zmianie, nie tylko różnicę." if has_film else "")
    )
    plan = provider.complete(RULES, user, FilmPlan)
    if not isinstance(plan, FilmPlan):
        plan = FilmPlan.model_validate(plan.model_dump())
    return plan


def apply_plan(film: Film, plan: FilmPlan) -> tuple[Film, list[str]]:
    """Wkleja plan do filmu, zachowując assety. Zwraca nowy film i listę zmian do pokazania."""
    updated = film.model_copy(deep=True)
    changes: list[str] = []

    before_scenes = {s.id: s for s in film.scenes}
    after_scenes = {s.id: s for s in plan.scenes}
    for sid in after_scenes:
        if sid not in before_scenes:
            changes.append(f"nowa scena {sid}")
        elif before_scenes[sid].model_dump() != after_scenes[sid].model_dump():
            changes.append(f"zmieniona scena {sid}")
    for sid in before_scenes:
        if sid not in after_scenes:
            changes.append(f"usunięta scena {sid}")
    if [s.id for s in film.scenes] != [s.id for s in plan.scenes] and not changes:
        changes.append("zmieniona kolejność scen")

    before_lines = {n.id: n.text for n in film.narration}
    for line in plan.narration:
        if line.id not in before_lines:
            changes.append(f"nowa linia lektora {line.id}")
        elif before_lines[line.id] != line.text:
            changes.append(f"zmieniony tekst {line.id}")
    for lid in before_lines:
        if lid not in {n.id for n in plan.narration}:
            changes.append(f"usunięta linia lektora {lid}")

    if plan.scenes:
        updated.scenes = plan.scenes
    if plan.narration:
        updated.narration = plan.narration
    if plan.music_events and updated.music:
        updated.music.events = plan.music_events
        changes.append("zmienione sterowanie muzyką")

    Film.model_validate(updated.model_dump())
    return updated, changes or ["bez zmian"]
