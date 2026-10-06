"""Plansza końcowa: logo DCS Robotics (wersja na ciemne tło) wyśrodkowane na tle 1080x1920.

Logo: Websitomat/oferty/assets/logo-dark.png (oficjalne, nie przerabiamy kolorów).
    python projects/go2/build_endcard.py
"""
import os
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
APPKI = Path(os.environ.get("DCS_APPKI", r"C:/AI TOMASZ PLIKI/Appki"))
logo_path = HERE / "assets" / "logo-dark.png"
if not logo_path.exists():
    logo_path.parent.mkdir(exist_ok=True)
    logo_path.write_bytes((APPKI / "Websitomat/oferty/assets/logo-dark.png").read_bytes())

W, H = 1080, 1920
logo = Image.open(logo_path).convert("RGBA")
bg = Image.new("RGB", (W, H), (5, 7, 12))
lg = logo.resize((860, round(logo.height * 860 / logo.width)), Image.LANCZOS)
bg.paste(lg, ((W - lg.width) // 2, (H - lg.height) // 2 - 40), lg)
bg.save(HERE / "assets" / "endcard.png")
print("OK", HERE / "assets" / "endcard.png")
