# Videomat — briefing dla Claude Code

Lokalny projekt Windows. Montaż filmu jest **dokumentem** `projects/<nazwa>/film.json`, nie kodem.
Zasady designu napisów: `skill/video-captions/SKILL.md` (czytaj przy pracy nad wyglądem).

## Środowisko (zweryfikowane)
- ffmpeg 7.1.1 full (libass, `ass`, `silencedetect`, `zoompan`, `vignette`), enkoder **h264_nvenc**
  (RTX 4060 Ti 16 GB) z fallbackiem libx264 — wybór w `videomat/config.py::encoder()`.
- Python 3.11: faster-whisper (CUDA), openai 2.46, google-genai, fastapi/uvicorn, pydantic 2, click, rich.
- Node 24.13 + npm 11.6 — frontend w `studio/` (Vite + React + TS + Tailwind 4).
- Fonty w `fonts/`, podawane libassowi przez `ass=...:fontsdir=`; domyślny `Rajdhani SemiBold`.
- Konsola cp1252: CLI ustawia UTF-8 samo; w skryptach doraźnych używaj `PYTHONIOENCODING=utf-8`.

## Jak pracować
```powershell
python -m videomat.cli studio                                   # edytor, http://127.0.0.1:8000
python -m videomat.cli film projects/ojciec/film.json           # render z dokumentu
python -m videomat.cli film projects/ojciec/film.json --frame 41.5   # klatka do obejrzenia
cd studio; npm run build                                        # po zmianach w interfejsie
```

## Twarde zasady
1. **Klucze** tylko w `.env` (gitignore). Nigdy w kodzie, README, logach, promptach. Klucz ujawniony
   w czacie → zalecić rotację. Nie wklejaj kluczy użytkownika do plików.
2. **Cytaty tylko z transkrypcji.** Scena `clip` nie ma pola z tekstem wypowiedzi — to celowe
   ograniczenie typu danych. Poprawki ASR wyłącznie przez `assets.clips.<id>.fixes`.
3. **Weryfikuj obrazem.** Po renderze obejrzyj klatki (`--frame`, `out/verify/`): diakrytyki,
   bezpieczne pole x 60–1020 / y 250–1600, brak nachodzenia napisów.
4. **Nowa nazwa pliku przy każdym renderze** (`config.next_version_path`). Źródeł nie nadpisujemy.
5. **Regresja obrazu.** `projects/ojciec/film.json` musi renderować się identycznie jak
   `out/ojciec_chrzestny_v13.mp4`. Sprawdzenie:
   `ffmpeg -i out/ojciec_chrzestny_v13.mp4 -i <nowy> -lavfi "[0:v][1:v]psnr" -f null -`
   → `average:inf min:inf`. Jeśli PSNR spadnie, zmiana w rendererze popsuła wygląd.
6. **Koszty.** `avatar` i `image` są płatne — najpierw `--dry-run`. Veo jest wyłączone (klucz Gemini
   ma zablokowaną usługę). ElevenLabs Music wymaga płatnego planu.
7. Nie zmieniaj logiki animacji w `videomat/ass.py` — to port `make_ass.py` dla starszej ścieżki
   `captions`. Wygląd filmów żyje w `videomat/render.py` i w `film.json`.

## Gdzie co jest
| Plik | Rola |
|---|---|
| `videomat/timeline.py` | modele filmu (pydantic) + `resolve()` czasów symbolicznych |
| `videomat/render.py` | generator ASS i renderer scen; tu mieszka wygląd |
| `videomat/cache.py` | skrót sceny → plik w `work/<projekt>/cache/` |
| `videomat/jobs.py` | kolejka z anulowaniem, postęp z `ffmpeg -progress` |
| `videomat/projects.py` | projekty, upload, historia zapisów |
| `videomat/speech.py` | lektor: TTS, korekta tempa, czasy słów |
| `videomat/agent.py` | prompt → plan montażu (OpenAI, strict + zapas na JSON) |
| `web/app.py` | API studia; frontend montowany **na końcu**, po trasach API |
| `studio/src/` | interfejs; `lib/sse.ts` ma testy w vitest |

## Pułapki, które już kosztowały czas
- Narzędzie Bash na tej maszynie rozwija `\n` w heredocach — pliki z ukośnikami odwrotnymi (tagi ASS,
  regexy) pisz narzędziem Write/Edit, nie `cat <<EOF`.
- `zoompan` ze `scale=8000` liczy się sekundami na klatkę — w podglądzie klatki geometria najazdu
  jest liczona wprost (`crop` + `scale`), inaczej podgląd trwał 26 s zamiast 1,8 s.
- Domyślne wartości pól pydantic potrafią zmienić wygląd przy zapisie z interfejsu (tak było
  z przenikaniem licznika). Po zmianach w modelu sprawdź regresję PSNR.
- `eleven_v3` ignoruje parametr prędkości — tempo koryguje `atempo` w `speech.py`.
- **Diaryzacja przed transkrypcją.** faster-whisper ładuje własną cuDNN, po której pyannote nie
  zainicjuje karty (`Could not load symbol cudnnGetLibConfig`). Kolejność w `stenogram.run()` jest
  celowa — nie odwracaj jej.
- pyannote na torch 2.6 wymaga dopuszczenia typów z checkpointów (`_allow_pyannote_checkpoints`)
  oraz wpisania `__file__` modułom przekierowań speechbrain (`_calm_lazy_imports`). Bez tego
  drugiego `inspect.stack()` z pytorch-lightning próbuje zaimportować niezainstalowane k2 i spacy.
- yt-dlp: domyślny klient YouTube zwraca 403 — `ingest.CLIENTS` przechodzi po kolei na `android`.

## Stenogram
| Plik | Rola |
|---|---|
| `videomat/ingest.py` | pobieranie z YouTube (przełączanie klienta, fragmenty), pliki, konwersja 16 kHz |
| `videomat/diarize.py` | pyannote + przypisanie mówców do słów + rozpoznawanie osób po głosie |
| `videomat/stenogram.py` | cały przebieg i eksport DOCX/MD/TXT/CSV/JSON + raport QC |
| `videomat/live.py` | nasłuch na żywo: mikrofon albo strumień, wersje robocze i wypowiedzi gotowe |
