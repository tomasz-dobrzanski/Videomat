"""Grafiki marki do zwiastuna G1: biała plansza końcowa i plakietka-znak z oficjalnym logo DCS Robotics.

Logo z dcsrobotics.pl (`Websitomat/stronki/robot-ai/public/brand/dcs-robotics-logo.png`) jest projektowane na białe
tło — szary napis „robotics” ginie na ciemnym. Kolorów logo nie zmieniamy (zasada marki), więc logo zawsze stoi
na bieli: pełna plansza na końcu i mała biała plakietka w rogu w trakcie filmu.

    python projects/g1/build_brand.py
"""
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
APPKI = Path(os.environ.get("DCS_APPKI", r"C:/AI TOMASZ PLIKI/Appki"))
LOGO = APPKI / "Websitomat/stronki/robot-ai/public/brand/dcs-robotics-logo.png"
FONT = ROOT / "fonts/Rajdhani-SemiBold.ttf"
assets = HERE / "assets"
assets.mkdir(exist_ok=True)

logo = Image.open(LOGO).convert("RGB")
# przycięcie białych marginesów oryginału
gray = logo.convert("L").point(lambda v: 255 if v < 245 else 0)
logo = logo.crop(gray.getbbox())

# --- plansza końcowa 1920x1080, biel
W, H = 1920, 1080
card = Image.new("RGB", (W, H), (255, 255, 255))
lw = 720
lg = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
ly = (H - lg.height) // 2 - 70
card.paste(lg, ((W - lw) // 2, ly))
d = ImageDraw.Draw(card)
f1 = ImageFont.truetype(str(FONT), 48)
f2 = ImageFont.truetype(str(FONT), 40)
t1, t2 = "Z symulacji na stanowisko pracy", "dcsrobotics.pl"
y1 = ly + lg.height + 70
d.text(((W - d.textlength(t1, font=f1)) / 2, y1), t1, font=f1, fill=(95, 99, 104))
d.line([(W / 2 - 60, y1 + 78), (W / 2 + 60, y1 + 78)], fill=(0, 180, 220), width=3)
d.text(((W - d.textlength(t2, font=f2)) / 2, y1 + 100), t2, font=f2, fill=(0, 165, 205))
card.save(assets / "endcard.png")

# --- plakietka: biały zaokrąglony prostokąt z logo, przezroczyste tło
pw, ph, r = 440, 210, 28
plate = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
ImageDraw.Draw(plate).rounded_rectangle([0, 0, pw - 1, ph - 1], r, fill=(255, 255, 255, 255))
inner = logo.resize((pw - 90, round(logo.height * (pw - 90) / logo.width)), Image.LANCZOS)
plate.paste(inner, ((pw - inner.width) // 2, (ph - inner.height) // 2))
plate.save(assets / "watermark.png")
print("OK", assets / "endcard.png", assets / "watermark.png")
