# Go2 — test na budowie (wersja filmowa, 37 s)

Przeróbka filmu „Go2 (5)”: z nagrań źródłowych usunięto wszystko, co było sztuczne (generowane roboty, drony,
plansze reklamowe), zostały prawdziwe ujęcia z testu. Dodano lektora filmowego, napisy, dźwięk budujący napięcie.

## Tekst lektora

1. Plac budowy. Ostatnie minuty przed testem.
2. Inżynierowie wchodzą na teren. Razem z nimi robot Go2. Autonomiczny.
3. Zanim tu trafił, widział tysiące obrazów. Także takich, które sami wygenerowaliśmy.
4. Teraz ktoś idzie w jego stronę.
5. Kamizelka jest. Kasku nie ma.
6. Człowiek zakłada kask. Model widzi zmianę.
7. Decyzja zawsze należy do człowieka.
8. DCS Robotics. Autonomia, która wspiera bezpieczną budowę.

## Dramaturgia

| Sekcja | Obraz | Dźwięk |
|---|---|---|
| Otwarcie | robot Go2 idzie na kamerę, zbliżenie oklejki | cisza, narastający pad |
| Teren | wejście do hali z inżynierami | miękkie przejście |
| Dane | matryca obrazów z ramkami modelu | — |
| Napięcie | człowiek idzie do robota | riser |
| Punkt kulminacyjny | zwolniona czerwona ramka na ekranie laptopa, kask w ręku | pad urwany, impuls, uderzenie |
| Rozwiązanie | kask na głowie, zielona ramka | gong potwierdzenia |
| Finał | robot w zbliżeniu, logo DCS Robotics | ciepły akord, wygaszenie |

Napięcie jest dramaturgią montażu i dźwięku (pauza, riser, zwolnienie), a nie sugestią zagrożenia na budowie.
Jedyny „brak” w filmie to świadomy test z kaskiem trzymanym w ręku.

## Zgodność z uwagami klienta

- Nie ma robota „zwiadowcy”, dronów ani generowanych scen robota. Są tylko prawdziwe nagrania z testu.
- Funkcja pokazana w filmie: autonomia i wykrywanie kasków oraz kamizelek. Nic więcej nie jest zapowiadane.
- Brak źle zabezpieczonych miejsc, dziur i plandek. Decyzję zawsze podejmuje człowiek.
- Nazwa klienta nie pada w lektorze ani w napisach (widać tylko oklejkę robota i kamizelki z prawdziwego nagrania).

## Do potwierdzenia przed wysyłką

- Zdanie 3 („także takich, które sami wygenerowaliśmy”) — dane syntetyczne muszą być w wytrenowanym modelu.
- Zdanie 2 („Autonomiczny”) — zgodne z mailem klienta, ale warto, żeby potwierdził to zespół robotyki.
- Zgoda klienta na pokazanie jego oklejki i kamizelek z logo oraz na wykorzystanie nagrania.
- Akceptacja nadawcy (zasady TomAi) przed wysyłką.

## Odtworzenie

```powershell
python projects/go2/build_endcard.py
python -m videomat.cli film projects/go2/film.json
```

Źródła wideo leżą w `GOTOWE FILMY/` (poza gitem), matryca z `projects/dcs-ppe/` (`build_visuals.py`).
Lektor: ElevenLabs (głos Brian), efekty i podkład z generatora efektów.
