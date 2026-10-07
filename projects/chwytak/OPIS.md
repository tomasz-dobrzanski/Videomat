# RobotChwytak — robot i symulacja (8.10.2026)

Dwa filmy 9:16 z trzech nagrań robota (`GOTOWE FILMY/RobotChwytak/`): chwyt kosza głośnika jedną ręką, uniesienie,
obrót, odłożenie do gniazda, reset stanowiska ręką operatora.

## 1. „Robot vs symulacja” (27 s)
- 0–2,5 s: tytuł „TEN SAM RUCH.”
- 2,5–13,3 s: naprzemiennie robot (cykl 2, zwolniony ×0,5 z 60 kl./s) i symulacja MuJoCo w tej samej fazie ruchu;
  cięcia przyspieszają z 1,0 s do 0,35 s, każde cięcie ma uderzenie w muzyce (rosnące napięcie).
- 13,3–23,1 s: porównanie 1:1 — robot u góry (cykl 1, ×0,6), symulacja na dole zsynchronizowana fazami
  (przy koszu → zacisk → uniesienie → obrót → odłożenie), etykieta fazy na łączeniu.
- 23,1–27,1 s: plansza DCS Robotics (oficjalne logo, białe tło).

Symulacja: `render_sim.py` = ten sam przebieg co `RobotChwytak/tools/film_proby.py --yaw 180` z konfiguracją zalecaną
(`runs/filmy/po_obrot180.json`), render pionowy HD, kamera śledząca. Wynik fizyki: chwyt OK (docisk 14,8 N, uniesienie
8,8 cm), osadzenie w gnieździe w symulacji NIEUDANE (5 mm nad, 3,5 mm w bok) — dlatego w filmie pokazujemy fazy do
odłożenia, bez twierdzenia „idealne włożenie”. Synchronizacja to dopasowanie czasów faz (time-warp), nie 1:1 trajektoria
stawów: nagrania robota nie mają telemetrii, a symulacja ma inną scenę (stół, gniazdo z boku).

## 2. „Nagrania bez cięć” (62,5 s)
Trzy nagrania w całości, połączone tylko krótkim przejściem przez czerń. Karta na początku każdego ujęcia,
plakietki faz pod robotem (zacisk, uniesienie, obrót, odłożenie, reset stanowiska), cichy podkład.

## Odtworzenie
```powershell
python projects/chwytak/render_sim.py      # symulacja (≈ 2,5 min, GPU)
python projects/chwytak/build_base.py      # obraz + plan cięć
python projects/chwytak/build_score.py     # muzyka pod cięcia
python -m videomat.cli film projects/chwytak/film.json
python -m videomat.cli film projects/chwytak/film_bez_ciec.json   # baza: assets/uncut.mp4 (każde nagranie osobno, autoobrót)
```
