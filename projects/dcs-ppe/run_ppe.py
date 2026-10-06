"""Wnioskowanie modelu BHP (RF-DETR Small, ONNX) na obrazach z dcs-vision-ai.

Ramki na filmie pochodzą z TEGO skryptu, nie są rysowane ręcznie. Progi per klasa z kalibracji
(`ppe/config/ppe_thresholds.json` w dcs-vision-ai). Ścieżki można nadpisać zmiennymi środowiskowymi:
DCS_APPKI (katalog z repozytoriami), DCS_PPE_ONNX (plik .onnx).
"""
import json, math, sys
from pathlib import Path
import numpy as np, onnxruntime as ort
from PIL import Image
CLASSES = ["person", "helmet", "no_helmet", "vest", "no_vest"]
MEAN = np.array((0.485, 0.456, 0.406), np.float32); STD = np.array((0.229, 0.224, 0.225), np.float32)
import os
ROOT = Path(os.environ.get("DCS_APPKI", r"C:/AI TOMASZ PLIKI/Appki"))
model = Path(os.environ.get("DCS_PPE_ONNX", ROOT / "Security robo dog/AI-Security-Robo-Dog/models/ppe-rfdetr-small640-op16.onnx/rfdetr-small.onnx"))
thr = json.loads((ROOT / "dcs-vision-ai/ppe/config/ppe_thresholds.json").read_text())["thresholds"]
sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
iname = sess.get_inputs()[0].name
sets = ["ppe-gen-hivis", "ppe-gen-grupy-hivis", "ppe-gen", "ppe-gen-trudne"]
out = {}
for s in sets:
    files = sorted((ROOT / "dcs-vision-ai/datasets" / s / "img").glob("*.jpg"))
    step = max(1, len(files) // 70)
    for p in files[::step][:70]:
        im = Image.open(p).convert("RGB"); w, h = im.size
        x = (np.asarray(im.resize((640, 640)), np.float32) / 255 - MEAN) / STD
        dets, labels = sess.run(None, {iname: x.transpose(2, 0, 1)[None]})
        keep = []
        for i in range(dets.shape[1]):
            sc = [1 / (1 + math.exp(-float(labels[0][i][c]))) for c in range(5)]
            c = int(np.argmax(sc))
            if sc[c] < thr[CLASSES[c]]: continue
            cx, cy, bw, bh = (float(v) for v in dets[0][i])
            keep.append({"cls": CLASSES[c], "p": round(sc[c], 3), "box": [round(v, 4) for v in ((cx - bw/2), (cy - bh/2), (cx + bw/2), (cy + bh/2))]})
        out[f"{s}/{p.name}"] = keep
    print(s, len(out), flush=True)
Path("work/dcs-ppe/ppe_detections.json").write_text(json.dumps(out), encoding="utf-8")
