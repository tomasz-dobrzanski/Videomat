# Efekt „budowa się zmienia” — Veo (9:16) i plan B

Klatka referencyjna: `GOTOWE FILMY/veo_ref_korytarz_9x16.jpg` (z `710.mp4`, 2,8 s: korytarz z cegły, robot Go2 przy
ścianie, pracownik w kasku i kamizelce w głębi). Kamera jedzie jak robot przez budowę, a budowa wokół niej rośnie w timelapsie. Odcinki
sklejamy w jedną podróż długości lektora.

## Prompt główny — kamera jedzie jak robot (hyperlapse)

> Vertical 9:16 first-person hyperlapse from the point of view of a quadruped inspection robot, camera mounted low at
> about 50 cm above the floor, smooth steady forward glide with a very subtle walking bob, slowly moving through an old
> brick corridor of a building under renovation, starting from the exact framing of the reference image.
> As the camera travels forward, time passes around it: the construction site visibly progresses in time-lapse —
> people move quickly like in a time-lapse, materials appear and are carried, structures grow.
> Workers always wear white hard hats and high-visibility vests; the site is tidy and well organised.
> Photorealistic, natural daylight, documentary style, continuous single take, no cuts, no text, no logos.

## Odcinki (8 s każdy; każdy startuje z ostatniej klatki poprzedniego, kamera jedzie dalej tą samą trasą)

| # | Do promptu głównego dopisz |
|---|---|
| 1 | Present day: bare brick walls and dusty floor; the camera lowers to robot height and starts moving forward; a worker with a laptop steps aside. |
| 2 | Debris is carried out in bags, a cart rolls past, the floor becomes clean as the camera passes. |
| 3 | Scaffolding rises along the right wall as the camera approaches; two workers assemble it in fast motion. |
| 4 | Cable trays and conduits appear along the ceiling above the moving camera, installed piece by piece. |
| 5 | The camera turns gently around a corner; a new drywall partition grows panel by panel beside it. |
| 6 | Walls get plastered smooth and light grey, scaffolding disappears as the camera glides on. |
| 7 | Walls turn white, ceiling lights switch on one after another ahead of the camera, floor gets finished. |
| 8 | The camera arrives in a bright finished corridor and slows to a stop; a worker in a hard hat checks a tablet. |

Ciągłość: zawsze ta sama wysokość kamery, kierunek jazdy i pora dnia. Zła klatka końcowa = generujemy odcinek
ponownie, nie sklejamy na siłę. 8 × 8 s = 64 s, montaż przycina do lektora (≈ 60 s) i dokłada lekkie
przenikanie 6 klatek na łączeniach.

## Plan B — 50 zdjęć generowanych

Ta sama klatka referencyjna jako obraz wejściowy, ten sam prompt główny bez słów o ruchu, 50 etapów od „stan obecny”
przez „rozbiórka do cegły”, „rusztowania”, „instalacje”, „ścianki”, „tynk”, „malowanie” do „gotowy korytarz”
(po ~6 zdjęć na etap). Montaż: przenikanie 0,3 s między zdjęciami, lekki najazd, robot doklejony z prawdziwego
nagrania w tym samym miejscu, jeśli generator go zgubi.

## Uczciwie

Wygenerowany timelapse to wizualizacja. W filmie podpisujemy go „wizualizacja”, a zdanie lektora o monitoringu postępu
prac musi potwierdzić zespół robotyki (czy funkcja była testowana u klienta).
