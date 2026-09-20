"""Deklaratywny model filmu (film.json) + rozwiązywanie czasów.

Film jest dokumentem, nie skryptem. Sceny idą po kolei, każda ma długość wyliczaną albo podaną
wprost. Zdarzenia (lektor, efekty, muzyka) odwołują się do granic scen symbolicznie ("s3.end+0.5"),
więc skrócenie jednej sceny nie rozsypuje reszty montażu.

    from videomat.timeline import Film, resolve
    film = Film.model_validate_json(Path("projects/ojciec/film.json").read_text("utf-8"))
    r = resolve(film, durations={"vo1": 4.42, ...})     # durations: długości plików lektora
    r.total, r.scenes[0].start, r.narration["vo1"].start

Zasada faktograficzna: scena typu "clip" NIE MA pola z tekstem cytatu. Napisy powstają wyłącznie
ze słów transkrypcji w zakresie in..out. Model językowy może wybrać zakres, ale nie może napisać
słów, których nikt nie powiedział. Poprawki błędów ASR idą przez jawną mapę clip.fixes.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1

SceneType = Literal["black", "clip", "freeze", "still"]
LayerType = Literal["title", "subtitle", "headline", "stamp", "counter", "panel", "shape", "board",
                    "word_list", "grid"]
MusicAction = Literal["start", "cut", "resume", "fade_out"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ czas symboliczny
TIME_RE = re.compile(r"^\s*([A-Za-z_][\w-]*)(?:\.(start|end))?\s*(?:([+-])\s*([0-9]*\.?[0-9]+))?\s*$")


class TimeError(ValueError):
    pass


def parse_time(value: float | int | str) -> tuple[str | None, str, float]:
    """'s3.end+0.5' -> ('s3', 'end', 0.5);  2.5 -> (None, 'start', 2.5).

    Zwraca (id odniesienia albo None dla czasu bezwzględnego, 'start'|'end', przesunięcie).
    """
    if isinstance(value, (int, float)):
        return None, "start", float(value)
    text = str(value).strip()
    try:
        return None, "start", float(text)
    except ValueError:
        pass
    m = TIME_RE.match(text)
    if not m:
        raise TimeError(f"Nie rozumiem czasu: {value!r}. Użyj liczby albo 'scena.end+0.5'.")
    ref, anchor, sign, offset = m.groups()
    delta = float(offset or 0.0) * (-1 if sign == "-" else 1)
    return ref, anchor or "start", delta


# ------------------------------------------------------------------ assety
class ClipAsset(Strict):
    path: str = Field(description="Ścieżka do pliku wideo, względem katalogu projektu albo katalogu Videomat.")
    crop: str | None = Field(default=None, description="Filtr ffmpeg crop=W:H:X:Y, np. do usunięcia logo stacji.")
    transcript: str | None = Field(default=None, description="Ścieżka do transcript.json (segmenty + słowa).")
    fixes: dict[str, str] = Field(default_factory=dict, description="Jawne poprawki błędów ASR: słowo -> poprawione.")


class MusicAsset(Strict):
    path: str
    gain_db: float = -10.5


class SfxAsset(Strict):
    path: str | None = Field(default=None, description="Gotowy plik; gdy pusty, generowany z promptu.")
    prompt: str | None = Field(default=None, description="Opis dla generatora efektów ElevenLabs.")
    duration: float | None = None
    loop: bool = False


class VoiceConfig(Strict):
    provider: Literal["elevenlabs"] = "elevenlabs"
    voice_id: str | None = None
    voice_order: list[str] = Field(default_factory=list, description="Nazwy głosów do wypróbowania po kolei.")
    model: str = "eleven_v3"
    stability: float = 0.5
    similarity: float = 0.84
    speed: float = 1.15
    tempo: float = Field(default=1.0, description="Przyspieszenie po TTS przez atempo (v3 ignoruje speed).")


class Assets(Strict):
    clips: dict[str, ClipAsset] = Field(default_factory=dict)
    music: dict[str, MusicAsset] = Field(default_factory=dict)
    sfx: dict[str, SfxAsset] = Field(default_factory=dict)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)


# ------------------------------------------------------------------ lektor
class NarrationLine(Strict):
    id: str
    text: str
    fallback: float = Field(default=3.0, description="Długość używana, gdy nie ma jeszcze pliku audio.")
    gain_db: float = 3.5


class NarrationPlacement(Strict):
    ref: str = Field(description="Id linii z listy narration.")
    at: float | str = Field(default=0.0, description="Czas w scenie: liczba albo 'vo3.end+0.25'.")
    captions: bool = Field(default=True, description="Czy pokazać napisy karaoke pod lektorem.")
    y: int = 1500


class SfxPlacement(Strict):
    ref: str
    at: float | str = 0.0
    gain_db: float = 0.0


# ------------------------------------------------------------------ warstwy i sceny
class Layer(Strict):
    """Warstwa graficzna sceny. Pola nieużywane przez dany typ zostają puste."""

    type: LayerType
    text: str | None = None
    x: int | None = None
    y: int | None = None
    size: int | None = None
    color: str | None = Field(default=None, description="Kolor #RRGGBB; puste = kolor stylu.")
    align: int | None = Field(default=None, description="Wyrównanie ASS (1-9).")
    bold: bool | None = None
    spacing: int | None = None
    border: int | None = Field(default=None, description="Grubość obwódki ASS; puste = wartość stylu.")
    pop: bool = Field(default=False, description="Wejście ze skokiem skali (jak przy wyniku głosowania).")
    start: float | str = Field(default=0.0, description="Czas w scenie: liczba albo 'vo7.end+0.15'.")
    end: float | str | None = Field(default=None, description="Puste = do końca sceny.")
    fade_in: int = 150
    fade_out: int = 200
    # counter
    n: int | None = None
    # panel / shape
    width: int | None = None
    height: int | None = None
    opacity: int | None = Field(default=None, description="Przezroczystość ASS 0-255 (0 = pełny kolor).")
    # board: siatka kwadratów
    count: int | None = None
    columns: int | None = None
    step: float | None = Field(default=None, description="Odstęp czasowy między elementami siatki/listy.")
    gap: int | None = None
    cell: int | None = None
    # word_list: kolejne słowa pojawiające się jedno pod drugim
    items: list[str] = Field(default_factory=list)
    line_height: int | None = None


class Scene(Strict):
    id: str
    type: SceneType
    duration: float | None = Field(default=None, description="Puste = wyliczane z klipu albo z lektora.")
    min_duration: float = 0.0
    tail: float = Field(default=0.0, description="Czas po ostatnim lektorze, gdy długość jest wyliczana.")
    # clip / freeze / still
    clip: str | None = None
    start: float | None = Field(default=None, description="Wejście w klip (sekundy) dla typu clip.")
    end: float | None = Field(default=None, description="Wyjście z klipu (sekundy) dla typu clip.")
    at: float | None = Field(default=None, description="Moment klatki dla freeze/still.")
    zoom: bool = False
    captions: bool = Field(default=True, description="Napisy karaoke z transkrypcji (tylko typ clip).")
    caption_y: int = 1560
    layers: list[Layer] = Field(default_factory=list)
    narration: list[NarrationPlacement] = Field(default_factory=list)
    sfx: list[SfxPlacement] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "Scene":
        if self.type == "clip":
            if not self.clip:
                raise ValueError(f"Scena {self.id}: typ 'clip' wymaga pola clip.")
            if self.start is None or self.end is None:
                raise ValueError(f"Scena {self.id}: typ 'clip' wymaga start i end.")
            if self.end <= self.start:
                raise ValueError(f"Scena {self.id}: end musi być większe od start.")
        if self.type in ("freeze", "still"):
            if not self.clip:
                raise ValueError(f"Scena {self.id}: typ '{self.type}' wymaga pola clip.")
            if self.at is None:
                raise ValueError(f"Scena {self.id}: typ '{self.type}' wymaga at (moment klatki).")
            if self.duration is None and not self.narration:
                raise ValueError(f"Scena {self.id}: typ '{self.type}' wymaga duration albo lektora.")
        return self


# ------------------------------------------------------------------ muzyka
class MusicEvent(Strict):
    at: float | str
    action: MusicAction
    gain_db: float | None = None


class MusicTrack(Strict):
    asset: str
    gain_db: float | None = None
    events: list[MusicEvent] = Field(default_factory=list)
    fade_in: float = 0.4
    fade_out: float = 1.8
    duck_after: float | None = Field(default=None, description="Ściszenie (mnożnik) po tym czasie od startu.")
    duck_factor: float = 0.6


class Format(Strict):
    width: int = 1080
    height: int = 1920
    fps: int = 30


class Theme(Strict):
    sans: str = "Rajdhani SemiBold"
    serif: str = "Cambria"
    mono: str = "Consolas"
    white: str = "#FFFFFF"
    grey: str = "#9F9F9F"
    accent: str = "#FFD900"
    accent2: str = "#00E5FF"
    caption_size: int = 96
    narration_size: int = 72
    grade: bool = Field(default=True, description="Filmowy grading: kontrast, ziarno, winieta.")


class Film(Strict):
    version: int = SCHEMA_VERSION
    name: str = "film"
    format: Format = Field(default_factory=Format)
    theme: Theme = Field(default_factory=Theme)
    assets: Assets = Field(default_factory=Assets)
    narration: list[NarrationLine] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    music: MusicTrack | None = None

    @model_validator(mode="after")
    def _check(self) -> "Film":
        ids = [s.id for s in self.scenes]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"Powtórzone id scen: {sorted(dup)}")
        nids = [n.id for n in self.narration]
        dup = {i for i in nids if nids.count(i) > 1}
        if dup:
            raise ValueError(f"Powtórzone id lektora: {sorted(dup)}")
        known_n = set(nids)
        for s in self.scenes:
            if s.clip and s.clip not in self.assets.clips:
                raise ValueError(f"Scena {s.id}: nieznany klip {s.clip!r}")
            for p in s.narration:
                if p.ref not in known_n:
                    raise ValueError(f"Scena {s.id}: nieznana linia lektora {p.ref!r}")
            for p in s.sfx:
                if p.ref not in self.assets.sfx:
                    raise ValueError(f"Scena {s.id}: nieznany efekt {p.ref!r}")
        if self.music and self.music.asset not in self.assets.music:
            raise ValueError(f"Nieznany podkład {self.music.asset!r}")
        return self

    def scene(self, sid: str) -> Scene:
        for s in self.scenes:
            if s.id == sid:
                return s
        raise KeyError(sid)


# ------------------------------------------------------------------ wynik rozwiązania
class ResolvedScene(Strict):
    id: str
    index: int
    start: float
    duration: float
    end: float


class ResolvedNarration(Strict):
    id: str
    scene: str
    local_start: float
    start: float
    duration: float
    end: float
    captions: bool
    y: int
    gain_db: float


class ResolvedSfx(Strict):
    ref: str
    scene: str
    start: float
    gain_db: float


class ResolvedMusicSegment(Strict):
    start: float
    end: float
    gain_db: float
    fade_in: float
    fade_out: float
    duck_after: float | None = None
    duck_factor: float = 1.0


class Resolved(Strict):
    total: float
    scenes: list[ResolvedScene]
    narration: list[ResolvedNarration]
    sfx: list[ResolvedSfx]
    music: list[ResolvedMusicSegment] = Field(default_factory=list)

    def scene(self, sid: str) -> ResolvedScene:
        for s in self.scenes:
            if s.id == sid:
                return s
        raise KeyError(sid)

    def marks(self) -> dict[str, float]:
        """Płaska mapa nazwa -> czas bezwzględny (zgodna z dawnym marks.json)."""
        out = {n.id: round(n.start, 3) for n in self.narration}
        for i, s in enumerate(self.sfx):
            out[f"{s.ref}_{i + 1}" if any(o.ref == s.ref for o in self.sfx[:i]) else s.ref] = round(s.start, 3)
        for i, m in enumerate(self.music):
            out[f"music{i + 1}_start"] = round(m.start, 3)
            out[f"music{i + 1}_end"] = round(m.end, 3)
        return out


def _narration_durations(film: Film, durations: dict[str, float] | None) -> dict[str, float]:
    known = dict(durations or {})
    return {n.id: float(known.get(n.id, n.fallback)) for n in film.narration}


def _place_scene_narration(scene: Scene, dur: dict[str, float]) -> dict[str, tuple[float, float]]:
    """Rozmieszcza lektora wewnątrz sceny. Zwraca ref -> (start lokalny, długość)."""
    placed: dict[str, tuple[float, float]] = {}
    pending = list(scene.narration)
    guard = 0
    while pending:
        guard += 1
        if guard > len(scene.narration) + 5:
            unresolved = ", ".join(p.ref for p in pending)
            raise TimeError(f"Scena {scene.id}: nie mogę rozwiązać kolejności lektora ({unresolved}). "
                            "Sprawdź, czy odwołania nie tworzą pętli.")
        rest = []
        for p in pending:
            ref, anchor, delta = parse_time(p.at)
            if ref is None:
                start = delta
            elif ref in placed:
                base = placed[ref][0] + (placed[ref][1] if anchor == "end" else 0.0)
                start = base + delta
            else:
                rest.append(p)
                continue
            placed[p.ref] = (start, dur.get(p.ref, 0.0))
        if len(rest) == len(pending):
            unresolved = ", ".join(p.ref for p in rest)
            raise TimeError(f"Scena {scene.id}: odwołanie do nieumieszczonej linii lektora ({unresolved}).")
        pending = rest
    return placed


def scene_duration(scene: Scene, placed: dict[str, tuple[float, float]]) -> float:
    if scene.duration is not None:
        return float(scene.duration)
    if scene.type == "clip":
        return float(scene.end) - float(scene.start)  # type: ignore[arg-type]
    last = max((s + d for s, d in placed.values()), default=0.0)
    return max(scene.min_duration, last + scene.tail)


def resolve(film: Film, durations: dict[str, float] | None = None) -> Resolved:
    """Zamienia film na oś czasu: bezwzględne pozycje scen, lektora, efektów i muzyki."""
    dur = _narration_durations(film, durations)
    scenes: list[ResolvedScene] = []
    narration: list[ResolvedNarration] = []
    sfx_pending: list[tuple[SfxPlacement, str]] = []
    t = 0.0
    for i, sc in enumerate(film.scenes):
        placed = _place_scene_narration(sc, dur)
        length = scene_duration(sc, placed)
        if length <= 0:
            raise TimeError(f"Scena {sc.id}: długość musi być dodatnia (wyszło {length}).")
        scenes.append(ResolvedScene(id=sc.id, index=i, start=t, duration=length, end=t + length))
        for p in sc.narration:
            local, d = placed[p.ref]
            line = next(n for n in film.narration if n.id == p.ref)
            narration.append(ResolvedNarration(
                id=p.ref, scene=sc.id, local_start=local, start=t + local, duration=d, end=t + local + d,
                captions=p.captions, y=p.y, gain_db=line.gain_db))
        sfx_pending += [(p, sc.id) for p in sc.sfx]
        t += length
    total = t

    lookup = {s.id: s for s in scenes}

    def absolute(value: float | str, scene_id: str | None = None) -> float:
        ref, anchor, delta = parse_time(value)
        if ref is None:
            base = lookup[scene_id].start if scene_id else 0.0
            return base + delta
        if ref == "film":
            return (total if anchor == "end" else 0.0) + delta
        if ref in lookup:
            s = lookup[ref]
            return (s.end if anchor == "end" else s.start) + delta
        match = next((n for n in narration if n.id == ref), None)
        if match:
            return (match.end if anchor == "end" else match.start) + delta
        raise TimeError(f"Nieznane odniesienie czasu: {ref!r}")

    sfx = [ResolvedSfx(ref=p.ref, scene=sid, start=absolute(p.at, sid), gain_db=p.gain_db)
           for p, sid in sfx_pending]

    music: list[ResolvedMusicSegment] = []
    if film.music:
        track = film.music
        base_gain = track.gain_db if track.gain_db is not None else film.assets.music[track.asset].gain_db
        events = sorted(
            [(absolute(e.at), e) for e in track.events],
            key=lambda pair: pair[0],
        )
        playing_from: float | None = 0.0
        gain = base_gain
        first = True
        for when, ev in events:
            if ev.action in ("start", "resume"):
                if playing_from is None:
                    playing_from = when
                    first = False
                if ev.gain_db is not None:
                    gain = ev.gain_db
            elif ev.action in ("cut", "fade_out") and playing_from is not None:
                music.append(ResolvedMusicSegment(
                    start=playing_from, end=when, gain_db=gain,
                    fade_in=track.fade_in if first or not music else 0.8,
                    fade_out=track.fade_out if ev.action == "fade_out" else 0.0,
                    duck_after=track.duck_after if first else None,
                    duck_factor=track.duck_factor))
                playing_from = None
                first = False
        if playing_from is not None:
            music.append(ResolvedMusicSegment(
                start=playing_from, end=total, gain_db=gain,
                fade_in=track.fade_in if not music else 0.8, fade_out=track.fade_out,
                duck_after=track.duck_after if not music else None, duck_factor=track.duck_factor))

    return Resolved(total=total, scenes=scenes, narration=narration, sfx=sfx, music=music)


# ------------------------------------------------------------------ kolory
def hex_to_ass(color: str) -> str:
    """#RRGGBB -> &HBBGGRR (ASS trzyma kolory odwrotnie niż HTML)."""
    c = color.strip().lstrip("#")
    if len(c) != 6:
        raise ValueError(f"Kolor musi mieć postać #RRGGBB, dostałem {color!r}")
    return f"&H00{c[4:6]}{c[2:4]}{c[0:2]}".upper()
