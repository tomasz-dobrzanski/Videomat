# Go2 (5) — wersja kinowa v2 (60,7 s)

Montaż klienta **„Go2 (5).mp4” zostaje co do klatki**. Dokładamy: lektor (Adam, ElevenLabs v3, wymowa polska),
napisy w stylu skilla video-captions (word_blast na hakach, highlight w narracji, jednolite nagłówki 92 px
z kickerem i panelem), podkład napięciowy, riser/uderzenie/akord, grading.

Wymowa: pole `say` w `film.json` — napis pokazuje „BHP” i „DCS Robotics”, głos czyta „be ha pe” i „De Ce Es Robotiks”.
Sprawdzone transkrypcją zwrotną (whisper rozpoznał z powrotem „BHP” i „DCS Robotics”).

## Lektor

| | Napis | Ujęcie |
|---|---|---|
| 1 | Innowacje potrzebują pionierów. | budynek dcs.pl |
| 2 | Tych, którzy widzą wcześniej. | Go2 na parkingu |
| 3 | Na budowie nic nie jest oczywiste. Dlatego robot wchodzi pierwszy. | hala |
| 4 | Lidar 360 stopni. Kamery głębi. SLAM. | laptop z mapą |
| 5 | Mapa powstaje w czasie rzeczywistym. Trasę planuje sam. | laptop / test |
| 6 | AI. Tysiące obrazów treningowych. | matryca |
| 7 | Kask. Kamizelka. Jedna różnica wystarczy. | szybkie detekcje |
| 8 | Nieprawidłowość BHP? Nadzór wie natychmiast. | detekcje |
| 9 | Zmienia piętra. Pokonuje schody. Wraca do stacji dokowania. | schody (40,2–45 s) |
| 10 | Robot nie zastępuje specjalisty BHP. Daje mu dodatkowe oczy na budowie. | plansza DCS |
| 11 | DCS Robotics. Programujemy roboty, które widzą więcej. | plansza, potem dcsrobotics.pl |

Nagłówki (wszystkie 92 px, y 640 albo 1180 gdy zasłaniałyby postać): PIONIERZY · ROBOT WCHODZI PIERWSZY ·
LIDAR 360° · MAPA NA ŻYWO · TYSIĄCE OBRAZÓW · KASK. KAMIZELKA. · BHP POD KONTROLĄ · ZMIENIA PIĘTRA ·
DODATKOWE OCZY · dcsrobotics.pl.

## Do potwierdzenia przed wysyłką

- Linie 4, 5, 9 (lidar 360, kamery głębi, SLAM, nawigacja autonomiczna, zmiana pięter, stacja dokowania) to
  deklaracje możliwości robota. Klient wcześniej zarzucił „wybieganie w przyszłość” — te zdania wymagają
  potwierdzenia zespołu robotyki, że to było testowane albo jest w konfiguracji dostarczonej klientowi.
- Dźwięk: -15,9 LUFS, szczyt -1,5 dB.

## Odtworzenie

```powershell
python -m videomat.cli film projects/go2kino/film.json
```
Źródło `GOTOWE FILMY/Go2 (5).mp4`, podkład `assets/drone.mp3` (z generatora efektów) — oba poza gitem.
