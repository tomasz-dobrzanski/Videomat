"""Symulacja chwytu z TRZECH kamer naraz (jeden przebieg fizyki, 1080x1920, 30 kl./s):
  sim_front.mp4 — z przodu, kamera śledzi kosz i tułów
  sim_head.mp4  — „oczami robota”: kamera na wysokości głowy patrzy na chwytak
  sim_hand.mp4  — kamera na nadgarstku patrzy na kosz
Ten sam przebieg co render_sim.py (konfiguracja zalecana z runs/filmy/po_obrot180.json), płyta szablonu uniesiona
0,6 mm w renderze (bez z-fightingu). Fazy zapisują się do sim3_fazy.json.

    python projects/chwytak/render_sim3.py
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

RC = Path(os.environ.get("ROBOTCHWYTAK", r"C:/AI TOMASZ PLIKI/Appki/RobotChwytak"))
sys.path[:0] = [str(RC), str(RC / "speaker"), str(RC / "tools")]
HERE = Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 30


def aim(cam, pos, look):
    """Ustaw kamerę orbitalną MuJoCo tak, by stała w `pos` i patrzyła na `look`."""
    v = np.asarray(pos, float) - np.asarray(look, float)
    d = float(np.linalg.norm(v)) + 1e-9
    cam.lookat[:] = look
    cam.distance = d
    cam.elevation = -math.degrees(math.asin(np.clip(v[2] / d, -1, 1)))
    cam.azimuth = math.degrees(math.atan2(-v[1], -v[0]))


def main() -> None:
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
    for gi in range(m.ngeom):
        if m.geom(gi).name == "fx_fixture_black":
            m.geom_pos[gi][2] += 0.0006
    mujoco.mj_forward(m, d)
    ren = mujoco.Renderer(m, H, W)
    cams = {k: mujoco.MjvCamera() for k in ("front", "head", "hand", "wide")}
    torso = m.body("torso_link").id
    wrist = m.body("right_wrist_yaw_link").id
    smooth = {"front": None, "head": None, "hand": None, "handpos": None}

    def node_interp(x, xs, ys):
        """Interpolacja z łagodnym wejściem/wyjściem (smoothstep) między węzłami — ruch kamery bez szarpnięć."""
        ys = np.asarray(ys, float)
        if x <= xs[0]:
            return ys[0]
        for i in range(len(xs) - 1):
            if x <= xs[i + 1]:
                u = (x - xs[i]) / (xs[i + 1] - xs[i])
                u = u * u * (3 - 2 * u)
                return ys[i] + (ys[i + 1] - ys[i]) * u
        return ys[-1]

    def ease(key, target, k=0.08):
        t = np.asarray(target, float)
        smooth[key] = t if smooth[key] is None else smooth[key] + (t - smooth[key]) * k
        return smooth[key]

    out_dir = HERE / "assets"
    procs = {}
    for k in cams:
        procs[k] = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                                     "-r", str(FPS), "-i", "-", "-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr",
                                     "-cq", "17", "-b:v", "0", "-pix_fmt", "yuv420p", str(out_dir / f"sim_{k}.mp4")],
                                    stdin=subprocess.PIPE)
    stan = {"t_next": float(d.time), "fazy": [], "faza": None, "t0": float(d.time)}

    def frame(cam) -> bytes:
        ren.update_scene(d, cam)
        im = ren.render()[:, :, ::-1].copy()
        cv2.putText(im, "SYMULACJA", (W - 210, H - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (210, 210, 210), 2, cv2.LINE_AA)
        return im.tobytes()

    def klatka():
        t = float(d.time)
        f = getattr(s, "faza", "")
        if f != stan["faza"]:
            stan["fazy"].append([round(t - stan["t0"], 3), f])
            stan["faza"] = f
        if t + 1e-9 < stan["t_next"]:
            return
        stan["t_next"] = t + 1.0 / FPS
        c, _ = G.pozy_glosnika(s)
        tcp, _ = r.tcp()
        c = np.asarray(c, float)
        tcp = np.asarray(tcp, float)
        torso_p = d.xpos[torso].copy()
        wrist_p = d.xpos[wrist].copy()
        # 1) przód: stały punkt kamery, cel między tułowiem a koszem
        look = ease("front", 0.45 * (torso_p + [0, 0, 0.1]) + 0.55 * c + [0, 0, 0.06])
        aim(cams["front"], [1.25, -0.30, 0.22], look)
        # 2) oczami robota: kamera przy głowie, patrzy na chwytak
        head = torso_p + [0.22, 0.10, 0.50]
        aim(cams["head"], head, ease("head", 0.7 * tcp + 0.3 * c, 0.12))
        # 3) przy chwytaku: z boku, dalej niż poprzednio, pozycja i cel mocno wygładzone (bez drżenia chwytaka)
        back = wrist_p - tcp; back = back / (np.linalg.norm(back) + 1e-9)
        side = np.cross(back, [0, 0, 1]); side = side / (np.linalg.norm(side) + 1e-9)
        hp_ = ease("handpos", tcp + side * 0.32 + [0.0, 0.0, 0.18], 0.05)
        aim(cams["hand"], hp_, ease("hand", 0.5 * tcp + 0.5 * c, 0.08))
        # 4) szeroka: z daleka, prowadzona wyłącznie czasem symulacji (gładko, bez zależności od drgań chwytaka)
        ts = t - stan["t0"]
        wp = node_interp(ts, [0, 30, 45, 90], [[1.45, -0.55, 0.30], [1.30, -0.75, 0.18], [1.05, -0.80, 0.08], [1.0, -0.8, 0.06]])
        wl = node_interp(ts, [0, 15, 28, 45, 90], [[0.30, -0.15, 0.05], [0.30, -0.15, 0.05], [0.42, -0.28, -0.05], [0.50, -0.36, -0.14], [0.50, -0.36, -0.14]])
        aim(cams["wide"], wp, wl)
        for k in cams:
            procs[k].stdin.write(frame(cams[k]))

    wynik = {}
    try:
        w = G.chwyc_i_unies(s, r, klatka, 0, yaw_start_deg=par["yaw_start_deg"])
        wynik["chwyt"] = w
        if w.get("ok"):
            wynik["wloz"] = G.wloz(s, r, klatka, np.random.default_rng(0))
    except C.OchronaStop as e:
        wynik["ochrona"] = str(e)
    for p in procs.values():
        p.stdin.close()
        p.wait()
    wynik["fazy"] = stan["fazy"]
    (out_dir / "sim3_fazy.json").write_text(json.dumps(wynik, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("OK", {k: str(out_dir / f"sim_{k}.mp4") for k in cams})
    os._exit(0)


if __name__ == "__main__":
    main()
