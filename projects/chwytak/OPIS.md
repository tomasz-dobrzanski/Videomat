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

## Zmiany 8.10 (wieczór)
- Ujęcie 1 kończy się w 18 s (bez trzeciego powtórzenia i drugiego resetu) — film 49,4 s.
- Stoper „podniesienie → odłożenie”: start, gdy kosz odrywa się od gniazda, stop, gdy z powrotem w nim stoi
  (przed puszczeniem). Momenty odczytane z klatek co 0,2 s, więc dokładność ±0,2 s:
  ujęcie 1: 2,4 s i 2,6 s · ujęcie 2: 1,4 s i 1,6 s · ujęcie 3: 1,3 s.

## Sora (sim → real, efekt lidaru) — prompt gotowy, klucz OpenAI w .env odrzucony (401)
Klatka startowa: dowolna z `assets/sim_obrot180.mp4` (biały G1-D przy stole), klatka końcowa: z nagrania robota.
```
Vertical 9:16, 8 seconds, one continuous shot. Start from the reference simulation render: a white humanoid robot arm
grips a black speaker basket on a table in a dark 3D simulation. A cyan LiDAR scan sweeps from top to bottom: the scene
turns into a dense point cloud and wireframe, glowing cyan points flow and re-assemble, and the same moment
materialises as a real photographed lab: a silver humanoid robot lifting and rotating the real speaker basket on a
black fixture. Clean high-tech look, precise, no text, no logos, no people's faces.
```

## Wersja z lektorem (8.10, noc) — „Jeden ruch”, 67,7 s
Montaż prowadzi lektor (Jon, nagranie 02:02): 0–22,6 s symulacja (tytuł, dojazd, zacisk, uniesienie, obrót) pod
tekstem o cyfrowym bliźniaku; cięcie na robota dokładnie na „Gotowy model trafia bezpośrednio do robota”;
trzy nagrania robota (ujęcie 1 dwa powtórzenia bez cięć 16,8 s, ujęcia 2 i 3 po jednym powtórzeniu); outro Veo
z G1-D przy linii, „DCS Robotics. Uczymy roboty pracy.” na planszy. Lektor jako dwa ciągłe fragmenty (cięcie raz,
w pauzie przed „DCS Robotics”), napisy karaoke z czasów słów, stoper w lewym górnym rogu, muzyka `build_score2.py`
(uderzenia na zaciskach, impact na przejściu sim→robot, akord na outro). -14,6 LUFS, szczyt -0,7 dB.

## Wersja finalna (8.10, 02:30) — 62,8 s, lektor 02:15
0–3 tytuł w symulacji · 3–17,4 symulacja tylko kluczowy ruch (zacisk zwolniony ×2, uniesienie i obrót) · 17,4–33,4 VID 2–18 s
(dwa powtórzenia, bez cięć; stopery 2,4 s i 2,6 s) · 33,4–37 wstawka z symulacji na „Setki tysięcy powtórzeń…” ·
37–54,9 MicrosoftTeams-video w całości do drugiego odłożenia (stopery 1,4 s i 1,4 s) · 54,9–62,8 outro Veo, „DCS Robotics.
Uczymy roboty pracy.” Nagranie MicrosoftTeams-video (1) usunięte. Stoper: start gdy kosz rusza, stop gdy stoi w gnieździe
(±0,1 s). Lektor przecięty raz w pauzie przed „DCS Robotics”. -14,8 LUFS, szczyt -1,2 dB.

## Wersja 10/11 (8.10, 03:00) — 59,1 s
Symulacja przyspieszona (dojazd ×1,6, obrót ×1,3, zacisk w czasie rzeczywistym), bez plakietek SYMULACJA i stoperów,
logo w prawym dolnym rogu. Nagrania: VID 2–18 s · wstawka sim na „Setki tysięcy powtórzeń” · Teams tylko ostatni ruch
(11,0 s–koniec, czyste wejście) · Teams (1) 7,0–12,2 s (czyste wejście) · outro. Muzyka z build_score2 (-4 dB).

## Muzyka (8.10, finał)
Podkład dostarczony przez użytkownika: `GOTOWE FILMY/RobotChwytak/mfcc-background-music-274290.mp3` (61,6 s, wycisza się
ok. 58 s — pasuje do 59,1 s filmu bez cięcia). W miksie -11 dB pod lektorem (+2 dB), całość -13,6 LUFS, szczyt -0,4 dB.
Własne kompozycje (`build_score2/3/4.py`) zostają w repo jako zapas. Licencję utworu sprawdza użytkownik (plik z serwisu
z muzyką stockową — przed publikacją potwierdzić warunki użycia komercyjnego).

## Sekwencja symulacji z trzech kamer (8.10, rano) — 56,5 s
`render_sim3.py`: jeden przebieg fizyki (konfiguracja zalecana, płyta szablonu +0,6 mm — bez z-fightingu) renderowany
z trzech kamer naraz: **przód** (śledzi tułów i kosz), **oczy robota** (wysoko przed głową, patrzy na chwytak) i **kamera
przy chwytaku** (z boku, zbliżenie palców na koszu). Cięcie dynamiczne ze zmianą tempa (interpolacja ruchu, 30 kl./s):
dojazd ×4 (przód) → zejście ×1,5 (oczy) → **zacisk ×0,4, slow motion** (chwytak) → uniesienie ×2 (oczy) → obrót ×2,6 (przód)
→ powrót nad gniazdo ×4,5 (chwytak). Cała sekwencja 12,6 s, potem prawdziwe nagrania. Wstawka sim na „Setki tysięcy powtórzeń”
z kamery przedniej ×1,8.

## Film ostateczny (8.10, 06:00) — 56,5 s
Symulacja z czterech kamer (`render_sim3.py`: przód, szeroka, oczy robota, kamera przy chwytaku). Dojazd ×4 (przód) → zejście
(oczy) → zacisk w slow motion (chwytak, z odległości) → od 17 s symulacji tylko szeroka kamera z daleka, bez zbliżeń ręki
→ symulacja kończy się w 25 s, gdy kosz jest nad gniazdem (dalej fizyka szuka spiralą 30 s i osadzenie się nie udaje —
nie pokazujemy). Nagrania prawdziwego robota, lektor, muzyka i outro bez zmian względem poprzedniej wersji.
