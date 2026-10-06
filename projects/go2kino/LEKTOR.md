# Go2 (5) — wersja kinowa (60,7 s)

Montaż klienta **„Go2 (5).mp4” zostaje co do klatki** (ten sam czas, te same ujęcia, znak wodny DCS Robotics).
Dokładamy warstwę kinową: lektor, napisy, nagłówki, grading i dźwięk na oryginalnej muzyce.

## Lektor (poprawiony — bez zagrożeń, o autonomii i kaskach/kamizelkach)

| | Tekst | Ujęcie |
|---|---|---|
| 1 | Innowacje potrzebują pionierów. | budynek dcs.pl |
| 2 | Tych, którzy widzą wcześniej. I działają, zanim pojawi się problem. | Go2 na parkingu |
| 3 | Na budowie liczą się szczegóły. Kask. Kamizelka. Człowiek we właściwym miejscu. | hala, inżynierowie |
| 4 | Dlatego robot idzie pierwszy. | robot w korytarzu |
| 5 | Autonomicznie. Mapuje przestrzeń. Zna swoją trasę. | laptop z mapą |
| 6 | I sprawdza najważniejsze. Kask i kamizelkę. | test na parkingu |
| 7 | Nauczył się tego na tysiącach obrazów. | matryca danych |
| 8 | Kask jest. Kamizelka jest. Tu czegoś brakuje. | szybkie detekcje (zielone / czerwone) |
| 9 | Gdy widzi różnicę, nie czeka. Oznacza miejsce. Informuje. Daje obraz i kontekst. | schody |
| 10 | Robot nie zastępuje specjalisty BHP. Daje mu dodatkowe oczy na budowie. | plansza DCS |
| 11 | DCS Robotics. Programujemy roboty, które widzą więcej. | plansza DCS, potem napis dcsrobotics.pl |

Co zmieniono względem starego tekstu: wypadły „źle zabezpieczone przejście”, „plandeka na ziemi”, „miejsce,
w które nikt nie powinien wejść”, „strefy ryzyka”, „każda sekunda ma znaczenie”, „jeden krok decyduje
o wszystkim”. Zostały pionierzy, autonomia, mapowanie, kask i kamizelka, wsparcie specjalisty BHP.

## Warstwa kinowa

- Napisy lektora (highlight, 88 px) + nagłówki: PIONIERZY · ROBOT IDZIE PIERWSZY · AUTONOMIA · TYSIĄCE OBRAZÓW ·
  WIDZI RÓŻNICĘ · DODATKOWE OCZY NA BUDOWIE · dcsrobotics.pl.
- Dźwięk: oryginalna muzyka klienta (-1 dB) + lektor Brian (ElevenLabs) + riser przed detekcjami, uderzenie na
  pierwszym cięciu, ciepły akord na planszy. Całość -15,6 LUFS, szczyt -0,2 dB.
- Grading: kontrast, lekkie odbarwienie, ziarno, winieta (`theme.grade`).

## Odtworzenie

```powershell
python -m videomat.cli film projects/go2kino/film.json
```

Źródło: `GOTOWE FILMY/Go2 (5).mp4` (poza gitem). Gotowy plik: `GOTOWE FILMY/Go2 (5) - kino.mp4`.
