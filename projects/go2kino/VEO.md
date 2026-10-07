# Efekt „budowa się zmienia” — Veo (9:16) i plan B

Klatka referencyjna: `GOTOWE FILMY/veo_ref_korytarz_9x16.jpg` (z `710.mp4`, 2,8 s: korytarz z cegły, robot Go2 przy
ścianie, pracownik w kasku i kamizelce w głębi). Kamera STOI — zmienia się tylko korytarz. Tak łatwiej trzymać
ciągłość między odcinkami i sklejać je w jeden timelapse długości lektora.

## Prompt główny (do każdego odcinka, po angielsku — Veo lepiej trzyma się angielskich opisów)

> Static locked-off vertical shot, the exact framing of the reference image: an old brick corridor in a building under
> renovation, concrete floor, windows at the far end. Time-lapse of construction progress, smooth and calm.
> A yellow-and-grey quadruped robot walks slowly along the same route by the left wall in every stage.
> Workers always wear white hard hats and high-visibility vests; the site is tidy and well organised.
> Photorealistic, natural daylight, documentary style, no text, no logos, no camera movement, no cuts.

## Odcinki (8 s każdy; każdy kolejny startuje z ostatniej klatki poprzedniego)

| # | Do promptu głównego dopisz |
|---|---|
| 1 | Stage: the corridor as it is now; one worker walks toward the camera carrying a laptop, the robot patrols. |
| 2 | Stage: workers carry out old debris in bags and roll a cart away; floor gets cleaner. |
| 3 | Stage: scaffolding is set up along the right wall; two workers in hard hats and vests install it. |
| 4 | Stage: new electrical conduits and cable trays appear along the ceiling, installed piece by piece. |
| 5 | Stage: a new drywall partition rises on the right, panel by panel; a worker carries a board past the robot. |
| 6 | Stage: walls are plastered and become smooth and light grey; scaffolding is taken down. |
| 7 | Stage: walls painted white, ceiling lights installed and switched on, floor finished. |
| 8 | Stage: finished bright corridor, the robot walks the same route, one worker in hard hat checks a tablet. |

8 × 8 s = 64 s — przytniemy do długości lektora (≈ 60 s) przy montażu. Jeśli narzędzie nie przyjmuje 9:16,
generuj 16:9 z tym samym promptem, a ja wykadruję do pionu.

## Plan B — 50 zdjęć generowanych

Ta sama klatka referencyjna jako obraz wejściowy, ten sam prompt główny bez słów o ruchu, 50 etapów od „stan obecny”
przez „rozbiórka do cegły”, „rusztowania”, „instalacje”, „ścianki”, „tynk”, „malowanie” do „gotowy korytarz”
(po ~6 zdjęć na etap). Montaż: przenikanie 0,3 s między zdjęciami, lekki najazd, robot doklejony z prawdziwego
nagrania w tym samym miejscu, jeśli generator go zgubi.

## Uczciwie

Wygenerowany timelapse to wizualizacja. W filmie podpisujemy go „wizualizacja”, a zdanie lektora o monitoringu postępu
prac musi potwierdzić zespół robotyki (czy funkcja była testowana u klienta).
