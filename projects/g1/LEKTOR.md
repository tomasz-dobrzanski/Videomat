# G1 — zwiastun 16:9 (60 s): robot uczy się ruchu

Źródło: `RobotChwytak/media/rolka_sim_2026-10-06/ujecia_hd` (symulacja MuJoCo, 60 kl./s). Każda klatka ma podpis
„SYMULACJA” i tak zostaje. Nie twierdzimy, że sieć uczona tylko w symulacji działa (README rolki: ACT 0/30).
139° to wynik symulacji z 6.10 (`runs/rolka/glosnik_plan6/wynik/wynik.json`, przechył maks. 139,3°).

## Tekst do nagrania (jeden plik, po polsku, spokojnie, z pauzami)

| okno w filmie | tekst |
|---|---|
| 5,5–10,5 s | Zanim robot dotknie czegokolwiek na hali, uczy się tutaj. |
| 10,5–15,0 | W symulacji, gdzie fizyka liczy każdy kontakt i każdy nacisk. |
| 15,0–19,0 | Patrzy. Koryguje. Chwyta. („Chwyta” w 18,2 s — moment zacisku) |
| 22,0–28,0 | Gdy cel jest poza zasięgiem, sam podjeżdża bliżej. |
| 30,5–36,5 | Setki prób. Każda zmierzona. Także te nieudane. |
| 36,5–41,0 | Potem coś trudniejszego. Element z linii produkcyjnej. |
| 44,5–51,0 | Dwa chwytaki. Jeden pewny ruch. Obrót o sto trzydzieści dziewięć stopni. |
| 51,0–54,5 | Najpierw symulacja. Potem stanowisko pracy. |
| 54,5–60,0 | DCS Robotics. Uczymy roboty pracy. (czytać „de-ce-es robotiks”) |

Po nagraniu: linie tniemy wyłącznie w ciszy między zdaniami i stawiamy w oknach z tabeli; napisy karaoke
liczą się z czasów słów nagrania.

## Muzyka

`build_score.py` — synteza 100 BPM, d-moll → D-dur, uderzenia na zaciskach (2,03 / 3,0 / 18,2 / 29,53 / 42,4 / 54,5 s),
riser przed chwytem piłki i przed zaciskiem na elemencie, 0,4 s ciszy przed kulminacją. ElevenLabs Music wymaga
płatnego planu, dlatego ścieżka jest generowana lokalnie.

## Odtworzenie

```powershell
python projects/g1/build_score.py
python -m videomat.cli film projects/g1/film.json
```
Plansza końcowa `assets/endcard.png`: logo `RobotChwytak/assets/marka/dcs_logo_na_ciemne.png` na tle #05070C.
