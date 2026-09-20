# Briefing dla Claude Code — pipeline video-captions

Ten plik jest dla instancji Claude Code pracującej lokalnie na maszynie użytkownika.
Skill `video-captions` (SKILL.md w tym katalogu) opisuje CO robić. Ten plik opisuje
czego Claude Code potrzebuje, żeby to uruchomić poza sandboxem Claude.ai.

## Zależności systemowe

```bash
# ffmpeg z libass, libx264, filtrami drawtext/ass/zoompan/vignette/noise
ffmpeg -version | head -1          # wymagane >= 6.0
ffmpeg -filters | grep -E "^ .{3}(ass|zoompan|vignette|noise)"

# czcionki (polskie znaki + ö)
fc-list | grep -iE "poppins|dejavu"
# brak → sudo apt install fonts-dejavu fonts-poppins  (albo ręcznie do ~/.fonts)

pip install sherpa-onnx soundfile numpy
```

Ubuntu/Debian: `sudo apt install ffmpeg fonts-dejavu-core fonts-dejavu-extra`.
macOS: `brew install ffmpeg`, czcionki przez Font Book.

## Modele STT

`scripts/transcribe.py` pobiera je sam przy pierwszym uruchomieniu z
`https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/`:

| plik | rozmiar | zastosowanie |
|---|---|---|
| `silero_vad.onnx` | 0,6 MB | detekcja segmentów mowy |
| `sherpa-onnx-whisper-base.tar.bz2` | ~200 MB | szybkie wyrównywanie granic fraz |
| `sherpa-onnx-whisper-small.tar.bz2` | ~640 MB | finalna transkrypcja (dużo lepszy polski) |

Trzymaj je w stałym katalogu (`~/.cache/video-captions/`) i nie pobieraj za każdym razem.

## Różnice względem sandboxa Claude.ai

Lokalnie znikają ograniczenia, pod które pisany był skill. Claude Code powinien o tym wiedzieć:

- **Brak limitu 300 s na komendę** → `align_phrases.py` można puścić w całości zamiast w partiach, a `render.sh` może używać `-preset medium` lub `slow` dla lepszej kompresji.
- **Procesy w tle działają** → długie renderingi można zrównoleglić.
- **Sieć bez allowlisty** → działają API zewnętrzne (patrz niżej), a więc też TTS i muzyka.
- **GPU** → jeśli jest NVENC (`ffmpeg -encoders | grep nvenc`), zamień `libx264` na `h264_nvenc -cq 19`; przyspiesza render kilkukrotnie.

Reszta zasad ze SKILL.md obowiązuje bez zmian — zwłaszcza: weryfikuj klatki przed oddaniem, nowa nazwa pliku przy każdym renderze, nie zmyślaj słów lektora, nie wstawiaj niezweryfikowanych faktów o realnych osobach jako plansz.

## Klucze API

**Nie mam żadnego klucza i nie mogę go wygenerować ani podać.** W tym środowisku
nie było klucza ElevenLabs w zmiennych środowiskowych, a `api.elevenlabs.io`
zwracał 403 (`x-deny-reason: host_not_allowed`). Klucz musisz wygenerować sam w
panelu dostawcy i wpisać go lokalnie.

Zasady, których Claude Code ma się trzymać:

1. Klucz **nigdy** nie trafia do kodu, do repozytorium, do SKILL.md ani do promptu.
2. Klucz trzymany jest w zmiennej środowiskowej albo w `.env` dodanym do `.gitignore`.
3. Klucz wpisuje użytkownik własnoręcznie — Claude Code nie wkleja cudzych kluczy i nie prosi o podanie klucza w czacie.

```bash
# ~/.zshrc albo .env obok projektu
export ELEVENLABS_API_KEY="..."      # wpisujesz Ty, lokalnie
```

```python
import os, requests
key = os.environ["ELEVENLABS_API_KEY"]        # nigdy hardcode
r = requests.post(
    "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
    headers={"xi-api-key": key, "Content-Type": "application/json"},
    json={"text": vo_text, "model_id": "eleven_multilingual_v2"},
    timeout=120)
open("vo.mp3", "wb").write(r.content)
```

Gdy lektor jest już plikiem, montaż idzie normalnie: zmierz jego długość
(`ffprobe`), ustaw pod niego timing plansz, podłóż jako drugą ścieżkę audio i
zmiksuj z oryginałem (`amix=inputs=2:duration=longest:weights=1 0.35`).

## Struktura repo

```
video-captions/
├── SKILL.md                      # instrukcja pipeline'u (czytaj najpierw)
├── CLAUDE.md                     # ten plik
├── references/ass-tags.md        # ściągawka tagów ASS
└── scripts/
    ├── transcribe.py             # VAD + Whisper → transcript.json
    ├── align_phrases.py          # dokładne granice fraz
    ├── make_ass.py               # spec.json → .ass (napisy + nagłówki)
    ├── render.sh                 # wypalenie napisów, dopasowanie 9:16
    └── build_cinematic_cut.py    # biblioteka do montażu wielosegmentowego
```

## Typowy przebieg

```bash
python3 scripts/transcribe.py in.mp4 transcript.json pl small
# podziel segmenty na frazy 2–4 słowa → plan.json
python3 scripts/align_phrases.py plan.json audio16k.wav subs.json base
# złóż spec.json (napisy + jednolite nagłówki)
python3 scripts/make_ass.py spec.json subs.ass
./scripts/render.sh in.mp4 subs.ass out_v1.mp4 none
# wyciągnij klatki w momentach napisów i OBEJRZYJ je przed oddaniem
```
