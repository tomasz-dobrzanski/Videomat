# Autonomia i wykrywanie kasków oraz kamizelek — lektor (do akceptacji)

Film 9:16, 29 s. Ton spokojny, rzeczowy. Bez nazw klientów, bez liczb skuteczności, bez scen zagrożeń.

## Tekst lektora

1. Na bezpiecznej budowie liczy się każdy szczegół.
2. Testujemy autonomicznego robota z modelem, który rozpoznaje kaski i kamizelki.
3. Model uczył się na tysiącach obrazów, także tych, które sami wygenerowaliśmy.
4. Robot sprawdza, czy osoba ma kask i kamizelkę.
5. Informacja trafia do człowieka. Decyzja zawsze należy do nadzoru.
6. Autonomia, która wspiera już bezpieczną budowę.

## Co jest na ekranie

Żadnych napisów ani opisów, tylko obraz i ramki modelu: **zielona** = wykryty kask lub kamizelka, **czerwona** = brak kasku
lub kamizelki.

| Scena | Obraz |
|---|---|
| 1–3, 6 | Nieskończona matryca: każdy kafel zawiera kolejną matrycę, z czasem pojawiają się ramki modelu |
| 4–5 | Szybki montaż 30 różnych kadrów (chód, noszenie kabla, tablet, wózek paletowy, klęczenie), cięcia przyspieszają od 0,5 do 0,2 s, ramka zatrzaskuje się w 2 klatkach |

Obrazy to syntetyczne zdjęcia z `dcs-vision-ai/datasets/ppe-gen*`, ramki z `run_ppe.py`.
Na życzenie usunięto podpisy „obrazy syntetyczne”; przy publikacji warto dać tę informację w opisie filmu.

## Do potwierdzenia przed wysyłką

- **Zdanie 3 („także tych, które sami wygenerowaliśmy”).** Karta modelu w `dcs-vision-ai` opisuje trening na dwóch zbiorach
  publicznych (CC BY 4.0). Dane generowane (`ppe-gen*`, `ppe-white-synth*`) są w repozytorium, ale trzeba potwierdzić,
  że weszły do wytrenowanego punktu kontrolnego. Jeśli nie, zdanie zmienić na „…oraz na obrazach syntetycznych”.
- **Ramki to wynik modelu na obrazach syntetycznych, a nie ocena skuteczności.** Bramka wydaniowa modelu (test hold-out)
  nie jest domknięta, najsłabsza klasa to brak kamizelki. Dlatego w filmie nie ma żadnych liczb skuteczności.
- **Czerwone ramki.** Pokazane tylko tam, gdzie model słusznie wskazuje brak (bluzy, czapki, garnitur). Białe i szare
  kamizelki model błędnie oznacza jako brak, więc ich nie ma w filmie.
- **Robot.** Film mówi „autonomiczny robot”. Nie pokazuje sprzętu ani funkcji poza wykrywaniem kasków i kamizelek,
  bo nie mamy nagrań z testów, które można pokazać.
- **Akceptacja nadawcy** (zasady TomAi): film do klienta dopiero po akceptacji Marka Miałkowskiego, potem tag i wpis w CHANGELOG.

## Odtworzenie

```powershell
python projects/dcs-ppe/run_ppe.py            # wynik modelu na obrazach (ONNX z repo robota)
python projects/dcs-ppe/build_visuals.py      # matrix.mp4 i detect.mp4 do projects/dcs-ppe/assets/
python -m videomat.cli film projects/dcs-ppe/film.json
```

Lektor generuje studio albo `speech.ensure_lines`; podkład to `assets/pad.mp3` z generatora efektów ElevenLabs
(muzyka na darmowym planie niedostępna). Pliki wideo i audio są poza gitem.
