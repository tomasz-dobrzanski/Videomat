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

| Scena | Obraz | Skąd pochodzi |
|---|---|---|
| 1–3, 6 | Nieskończona matryca: każdy kafel zawiera kolejną matrycę, z czasem pojawiają się ramki modelu | obrazy syntetyczne z `dcs-vision-ai/datasets/ppe-gen*`, ramki z `run_ppe.py` |
| 4–5 | Trzy kadry z rzeczywistym wynikiem modelu, potem jeden dłużej z napisem „człowiek decyduje” | jak wyżej |

Podpis na ekranie: „Obrazy syntetyczne · wizualizacja” oraz „Obrazy syntetyczne · wynik modelu”.

## Do potwierdzenia przed wysyłką

- **Zdanie 3 („także tych, które sami wygenerowaliśmy”).** Karta modelu w `dcs-vision-ai` opisuje trening na dwóch zbiorach
  publicznych (CC BY 4.0). Dane generowane (`ppe-gen*`, `ppe-white-synth*`) są w repozytorium, ale trzeba potwierdzić,
  że weszły do wytrenowanego punktu kontrolnego. Jeśli nie, zdanie zmienić na „…oraz na obrazach syntetycznych”.
- **Ramki to wynik modelu na obrazach syntetycznych, a nie ocena skuteczności.** Bramka wydaniowa modelu (test hold-out)
  nie jest domknięta, najsłabsza klasa to brak kamizelki. Dlatego w filmie nie ma żadnych liczb skuteczności.
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
