# Videomat

Lokalne studio do produkcji krótkich filmów 9:16. Renderowanie na ffmpeg + libass z NVENC,
transkrypcja na GPU, lektor i efekty z ElevenLabs, edytor w przeglądarce i warstwa „film z prompta”.

Montaż jest **dokumentem**, nie skryptem: `projects/<nazwa>/film.json` opisuje sceny, warstwy,
lektora i muzykę. Edytor i model językowy piszą ten sam plik, renderer go wykonuje.

## Start

```powershell
copy .env.example .env      # wpisz własne klucze
python -m videomat.cli doctor
python -m videomat.cli studio
```

Studio wstaje na http://127.0.0.1:8000 (tylko localhost). Przy pierwszym uruchomieniu samo zbuduje
frontend z katalogu `studio/` (potrzebny Node; na tej stacji jest 24.13).

Klucze trzymamy wyłącznie w `.env`. Klucz, który trafił do czatu albo do logu, trzeba zrotować.

## Studio

| Panel | Do czego służy |
|---|---|
| **Materiał** | Wgrywanie nagrań i muzyki (transkrypcja startuje sama), teksty lektora, generowanie pojedynczych linii. Klik w słowo transkryptu ustawia początek ujęcia, klik z Shift — koniec. |
| **Podgląd** | Klatka spod głowicy odświeżana na bieżąco (poniżej 2 s), obok render podglądowy i finalny. |
| **Scena** | Wszystkie pola zaznaczonej sceny i jej warstw: teksty, pozycje, czasy, animacje. |
| **Oś czasu** | Sceny jako bloki: przeciąganie kolejności, zaznaczanie, ustawianie głowicy. |
| **Prompt** | Instrukcja po polsku → propozycja zmian → podgląd różnicy → zastosuj albo odrzuć. |
| **Zadania** | Postęp renderu i transkrypcji, przerywanie w locie. |

Skróty: `Ctrl+S` zapis, `Ctrl+Z` / `Ctrl+Y` cofnij i ponów, strzałki przewijają o klatkę
(z Shiftem o sekundę).

## Format `film.json`

Czasy są **symboliczne**, nie bezwzględne. Scena ma `duration: null` i wylicza długość z lektora
(`min_duration` + `tail`) albo z zakresu klipu. Zdarzenia odwołują się do `"vo3.end+0.25"` czy
`"punch.end"`. Skrócenie jednej sceny nie rozsypuje reszty montażu.

```jsonc
{
  "scenes": [
    { "id": "cold_open", "type": "black", "min_duration": 2.6, "tail": -0.15,
      "narration": [{ "ref": "vo1", "at": 0.45, "captions": true, "y": 1500 }],
      "layers": [{ "type": "title", "text": "OJCIEC CHRZESTNY", "y": 880, "size": 104 }] },
    { "id": "rec1a", "type": "clip", "clip": "c1", "start": 0.05, "end": 5.70 }
  ],
  "music": { "asset": "main", "events": [{ "at": "freeze3", "action": "cut" }] }
}
```

Typy scen: `black`, `clip`, `freeze`, `still` (z `zoom`).
Typy warstw: `title`, `subtitle`, `headline`, `stamp`, `counter`, `panel`, `shape`, `board`,
`word_list`, `grid`. W tekście warstwy działa prosta składnia: `[c:accent]`, `[c:grey]`,
`[fs:60]`, `[b:0]`, `[/]`.

**Cytatów nie da się zmyślić.** Scena typu `clip` nie ma pola z tekstem wypowiedzi — napisy
powstają wyłącznie ze słów transkrypcji z zakresu `start..end`. Poprawki błędów rozpoznawania mowy
idą przez jawną mapę `assets.clips.<id>.fixes`, widoczną w interfejsie.

## Cache scen

Każda scena renderuje się osobno, do pliku nazwanego skrótem jej treści. Zmiana jednego napisu
unieważnia jedną scenę.

| Operacja | Czas (film 56 s, 17 scen, RTX 4060 Ti) |
|---|---|
| Pierwszy render finalny | około 90 s |
| Render po zmianie jednego napisu | 4,6 s (16 scen z cache) |
| Render bez zmian | 3,5 s |
| Podgląd jednej klatki | poniżej 2 s |

## Stenogram

Druga noga projektu: z nagrania na tekst z podziałem na mówców. Odtwarza pipeline, którym powstały
stenogramy NEXT100, i dokłada tryb na żywo, którego tamten nie miał.

```powershell
# z YouTube albo z pliku
python -m videomat.cli stenogram "https://www.youtube.com/watch?v=..." --title "Debata" --speakers 4
python -m videomat.cli stenogram nagranie.mp4 --model large-v3 --names "SPEAKER_00=Jan Kowalski"

# na żywo: mikrofon albo transmisja
python -m videomat.cli audio-devices
python -m videomat.cli live --device 1
python -m videomat.cli live --source "https://www.youtube.com/watch?v=<transmisja>"
```

Co robi pełny przebieg:

1. **Pozyskanie** — yt-dlp (z przełączaniem klienta, bo YouTube odrzuca domyślny), pliki lokalne,
   pobieranie fragmentu przez `section=(od, do)` zamiast wielogodzinnej całości.
2. **Podział** — nagrania dłuższe niż 18 minut tnie na kawałki po 15 minut z 15-sekundową zakładką,
   a cięcie wypada w najcichszym miejscu w oknie ±30 s, żeby nie urwać zdania.
3. **Transkrypcja** — faster-whisper (domyślnie `large-v3`) z `condition_on_previous_text=False`,
   bo inaczej model wpada w pętle powtórzeń na oklaskach i muzyce. Język rozpoznawany per segment:
   polskie znaki, a przy ich braku słowa funkcyjne.
4. **Mówcy** — pyannote `speaker-diarization-3.1` na GPU, przypisanie po nakładaniu czasowym na
   poziomie słów, sklejanie sąsiednich wypowiedzi tej samej osoby.
5. **Nazwiska** — albo mapowanie ręczne (`--names`), albo porównanie odcisków głosu z próbkami
   (speechbrain ECAPA). Poniżej progu podobieństwa mówca zostaje anonimowy — lepszy pusty podpis
   niż przypisanie wypowiedzi niewłaściwej osobie.
6. **Dokumenty** — DOCX (granat, pasek statusu, tabela metadanych, znaczniki czasu, tabela miejsc
   do odsłuchania), Markdown, TXT, CSV, JSON oraz raport kontroli jakości.

Kontrola jakości: fragment trafia do weryfikacji, gdy `avg_logprob < -0.8` albo
`no_speech_prob > 0.5`. Status dokumentu to „Zweryfikowany", „Częściowo zweryfikowany" albo
„Wymaga kontroli" zależnie od udziału takich fragmentów.

**Tryb na żywo** działa inaczej: tekst roboczy pojawia się w trakcie mówienia, a wypowiedź zostaje
zamknięta po pauzie. Rozpoznawanie mówców czeka do końca sesji — pyannote potrzebuje szerszego
kontekstu, a zgadywanie w locie kończyłoby się podpisywaniem cudzych słów. Po zatrzymaniu sesji
`finalize()` przepuszcza zapisany dźwięk przez pełny przebieg z większym modelem i mówcami.

Diaryzacja **musi iść przed transkrypcją** w jednym procesie: faster-whisper ładuje własną wersję
cuDNN, po której pyannote nie potrafi już zainicjować karty.

## Komendy

| Komenda | Działanie |
|---|---|
| `videomat studio` | edytor w przeglądarce |
| `videomat film projects/ojciec/film.json --quality final` | render montażu z pliku |
| `videomat film ... --frame 41.5` | jedna klatka do obejrzenia |
| `videomat project list` / `project new <nazwa>` | projekty |
| `videomat stenogram <adres\|plik>` | stenogram z mówcami: DOCX, MD, TXT, CSV, JSON + raport QC |
| `videomat live --device 1` | stenogram na żywo z mikrofonu albo transmisji |
| `videomat audio-devices` | lista wejść dźwięku |
| `videomat captions in.mp4 --fit pad` | starsza ścieżka: napisy do pojedynczego pliku |
| `videomat roughcut in.mp4` | wycięcie cisz + eksport EDL i FCPXML |
| `videomat tts` `music` `sfx` `voices` | pojedyncze wywołania ElevenLabs |
| `videomat doctor` | stan środowiska i kluczy |
| `videomat serve` → `/classic` | dawny prosty panel |

## Praca nad interfejsem

```powershell
cd studio
npm install
npm run dev        # http://localhost:5173, API proxowane do 127.0.0.1:8000
npm run test       # testy parsera zdarzeń
npm run build      # produkt trafia do web/static
```

Adres `http://127.0.0.1:8000/?nolive` wyłącza strumień zdarzeń — przydatne przy zrzutach ekranu.

## Stan usług zewnętrznych (sprawdzony 2026-09-20)

- **ElevenLabs**: lektor i efekty działają. Music API oraz głosy z biblioteki i własne wymagają
  płatnego planu; podkład muzyczny wgrywasz jako plik.
- **OpenAI**: klucz działa, ale konto nie ma środków — prompt zwraca czytelny komunikat zamiast
  błędu. Montaż ręczny jest od tego niezależny.
- **Gemini/Veo**: klucz ma zablokowaną usługę (`API_KEY_SERVICE_BLOCKED`), więc generowanie awatara
  jest w interfejsie wyłączone.
- **YouTube**: domyślny klient yt-dlp dostaje 403; pobieranie przechodzi na kliencie `android`
  i moduł przełącza go sam. Pobranie fragmentu bywa odrzucane — wtedy leci całość i docinamy lokalnie.
- **Mikrofon**: ta stacja nie ma żadnego wejścia dźwięku (6 wyjść, 0 wejść), więc nasłuch z mikrofonu
  nie był tu sprawdzony. Ścieżka ze strumienia i z pliku — przetestowana.

## Zasady jakości

- Po renderze obejrzyj klatki: `videomat film ... --frame <sekunda>` albo podgląd w studiu.
  Sprawdzasz diakrytyki, bezpieczne pole (x 60–1020, y 250–1600) i brak nachodzenia napisów.
- Każdy render dostaje nową nazwę (`_v1`, `_v2`…). Źródła nie są nadpisywane.
- Na ekran trafiają tylko słowa realnie wypowiedziane.
- Ruch co 1–2 s, jeden styl napisów w klipie.

## Struktura

```
videomat/    montaż: timeline (model + czasy), render, cache, jobs, projects, agent, speech
             stenogram: ingest (yt-dlp), diarize (pyannote), stenogram (dokumenty), live (nasłuch)
             wspólne: ffmpeg, transcribe, chunker, tts, music, captions, roughcut, verify, cli
studio/      frontend (Vite + React + TypeScript + Tailwind 4)
web/         API studia (app.py) + zbudowany frontend (static/) + dawny panel
projects/    film.json, assets/, history/ każdego projektu
work/ out/   pliki robocze i wyniki (poza repozytorium)
```

`projects/ojciec/build.py` to zamrożony skrypt pierwszej wersji filmu. Nie jest już źródłem prawdy —
zostaje jako punkt odniesienia: render z `film.json` daje obraz identyczny co do piksela.

## Następne kroki

- Wielościeżkowy montaż obrazu (kilka warstw wideo naraz).
- Lip-sync lektora na klipie awatara (lokalny MuseTalk/LatentSync na RTX 4060 Ti).
- Podgląd dźwięku na osi czasu (przebieg fali).
