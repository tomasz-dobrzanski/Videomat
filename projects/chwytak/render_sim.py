"""Symulacja 1:1 zadania z nagrań robota (chwyt kosza głośnika jedną ręką, uniesienie, obrót 180°, odłożenie do gniazda)
— ten sam przebieg co `RobotChwytak/tools/film_proby.py --yaw 180 --konfig runs/optymalizacja/obrot180_gpu/raport.json`
(konfiguracja „zalecana”), ale render pionowy 1080x1920, 30 kl./s, kamera ustawiona jak telefon na nagraniu
(z przodu, lekko z boku, z góry). Bez napisów poza skromnym „SYMULACJA” (materiał z sim nie udaje nagrania).
Nie modyfikuje repo RobotChwytak — importuje jego moduły.

    python projects/chwytak/render_sim.py --probe          # jedna klatka do ustawienia kamery
    python projects/chwytak/render_sim.py                   # pełny przebieg -> projects/chwytak/assets/sim_obrot180.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

RC = Path(os.environ.get("ROBOTCHWYTAK", r"C:/AI TOMASZ PLIKI/Appki/RobotChwytak"))
sys.path[:0] = [str(RC), str(RC / "speaker"), str(RC / "tools")]
HERE = Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 30


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--az", type=float, default=195.0)
    ap.add_argument("--el", type=float, default=-9.0)
    ap.add_argument("--dist", type=float, default=1.12)
    ap.add_argument("--lx", type=float, default=0.30)
    ap.add_argument("--ly", type=float, default=-0.05)
    ap.add_argument("--lz", type=float, default=0.13)
    a = ap.parse_args()
    os.chdir(RC)
    import cv2
    import mujoco
    import sim_chwyt as C
    import sim_glosnik as G

    par = json.loads((RC / "runs/filmy/po_obrot180.json").read_text(encoding="utf-8"))["par"]
    C.SILA_DOCISKU_N = float(par["docisk_N"])
    G.KIERUNKI_CHWYTU_DEG = tuple(par["kierunki_deg"])
    G.YAW_NAD_GNIAZDEM_DEG = tuple(par["yaw_dozwolone_deg"])
    G.KROK_ZEJSCIA_M = par["krok_zejscia_mm"] / 1000.0
    G.SPIRALA_R_MAX_M = par["spirala_r_mm"] / 1000.0
    G.SPIRALA_SKOK_M = par["spirala_skok_mm"] / 1000.0
    G.DOCISK_RAMIENIEM_M = par["docisk_ramieniem_mm"] / 1000.0

    s = C.zbuduj(obiekt="cad_v2")
    r = C.Reka(s)
    m, d = s.model, s.data
    m.vis.global_.offwidth, m.vis.global_.offheight = W, H
    # Z-fighting: wizualna płyta szablonu (contype 0) ma górną ścianę dokładnie na blacie (z=-0,200).
    # Unosimy ją o 0,6 mm tylko w renderze — fizyka używa osobnych geomów kolizyjnych.
    for gi in range(m.ngeom):
        if m.geom(gi).name == "fx_fixture_black":
            m.geom_pos[gi][2] += 0.0006
    mujoco.mj_forward(m, d)
    ren = mujoco.Renderer(m, H, W)
    cam = mujoco.MjvCamera()
    c0, _ = G.pozy_glosnika(s)
    cam.lookat[:] = [a.lx, a.ly, a.lz]
    cam.distance, cam.azimuth, cam.elevation = a.dist, a.az, a.el

    torso = np.array([0.05, -0.05, 0.22])
    look = {"p": None}

    def frame() -> np.ndarray:
        # kamera śledzi środek między tułowiem a koszem (wygładzone), żeby przeniesienie do gniazda zostało w kadrze
        c, _ = G.pozy_glosnika(s)
        target = 0.45 * torso + 0.55 * np.asarray(c, float) + np.array([0.0, 0.0, 0.08])
        look["p"] = target if look["p"] is None else look["p"] + (target - look["p"]) * 0.06
        cam.lookat[:] = look["p"]
        ren.update_scene(d, cam)
        im = ren.render()[:, :, ::-1].copy()
        cv2.putText(im, "SYMULACJA", (W - 210, H - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (210, 210, 210), 2, cv2.LINE_AA)
        return im

    out_dir = HERE / "assets"
    out_dir.mkdir(exist_ok=True)
    if a.probe:
        cv2.imwrite(str(out_dir / "sim_probe.png"), frame())
        print("probe", out_dir / "sim_probe.png")
        os._exit(0)

    out = out_dir / "sim_obrot180.mp4"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "17",
                           "-b:v", "0", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    stan = {"t_next": float(d.time), "fazy": [], "faza": None, "t0": float(d.time)}

    def klatka():
        t = float(d.time)
        f = getattr(s, "faza", "")
        if f != stan["faza"]:
            stan["fazy"].append([round(t - stan["t0"], 3), f])
            stan["faza"] = f
        if t + 1e-9 < stan["t_next"]:
            return
        stan["t_next"] = t + 1.0 / FPS
        ff.stdin.write(frame().tobytes())

    wynik = {}
    try:
        w = G.chwyc_i_unies(s, r, klatka, 0, yaw_start_deg=par["yaw_start_deg"])
        wynik["chwyt"] = w
        if w.get("ok"):
            wynik["wloz"] = G.wloz(s, r, klatka, np.random.default_rng(0))
    except C.OchronaStop as e:
        wynik["ochrona"] = str(e)
    ff.stdin.close()
    ff.wait()
    wynik["fazy"] = stan["fazy"]
    wynik["czas_s"] = round(float(d.time) - stan["t0"], 2)
    (out_dir / "sim_obrot180.json").write_text(json.dumps(wynik, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in wynik.items() if k != "fazy"}, ensure_ascii=False, default=str))
    os._exit(0)


if __name__ == "__main__":
    main()
