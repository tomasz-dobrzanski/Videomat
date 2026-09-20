#!/usr/bin/env python3
"""
align_phrases.py — phrase-boundary alignment for verbatim subtitles when the
ASR gives only segment-level timing (sherpa-onnx Whisper has no word timestamps).

Method: for each planned sub chunk inside a VAD segment, binary-search the time
t at which decoding audio[seg_start:t] first contains the chunk's last word
(matched by an accent-stripped key). ~4 decodes per boundary. Use the `base`
model here (3x faster than small; keys are short so accuracy suffices).
Run in the FOREGROUND in batches (< 5 min each); background jobs get killed.

Usage:
    python3 align_phrases.py plan.json audio16k.wav out.json [base|small]

plan.json — list of segments (from transcribe.py) with your chunking:
[
  {"start": 7.03, "end": 12.25, "chunks": [
      {"text": "Na budowie zagrożenie",            "keys": ["zagroz"]},
      {"text": "rzadko wygląda groźnie od razu.",  "keys": ["razu"]},
      {"text": "przeszkoda na trasie,",            "keys": null}      # null = ends at segment end
  ]}
]
Keys: lowercase, diacritics stripped, first 4-7 letters of the LAST word; give
several variants for words ASR garbles (e.g. "BHP" -> ["bhp","pch","beha"]).

ALWAYS post-check the result: speech rate per chunk should be 0.18–0.75 s/word.
If a segment violates it (music masked a word → detected late), fall back to
character-proportional timing for that segment, and snap enumeration items to
scene cuts when the edit is cut on the words.
"""
import json, sys, unicodedata
import numpy as np, soundfile as sf, sherpa_onnx

plan_path, wav, out = sys.argv[1], sys.argv[2], sys.argv[3]
size = sys.argv[4] if len(sys.argv) > 4 else "base"
mdir = f"sherpa-onnx-whisper-{size}"
audio, sr = sf.read(wav, dtype="float32")
rec = sherpa_onnx.OfflineRecognizer.from_whisper(
    encoder=f"{mdir}/{size}-encoder.int8.onnx", decoder=f"{mdir}/{size}-decoder.int8.onnx",
    tokens=f"{mdir}/{size}-tokens.txt", language="pl", task="transcribe", num_threads=4)

def norm(t): return unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
def decode(a, b):
    st = rec.create_stream(); st.accept_waveform(sr, audio[int(a*sr):int(b*sr)]); rec.decode_stream(st)
    return norm(st.result.text)

subs = []
for seg in json.load(open(plan_path, encoding="utf-8")):
    a, b, cur = seg["start"], seg["end"], seg["start"]
    chunks = seg["chunks"]
    for i, ch in enumerate(chunks):
        if not ch.get("keys"):
            end = b
        else:
            lo, hi, found = cur + 0.15, b, None
            for _ in range(4):
                mid = (lo + hi) / 2
                if any(k in decode(a, mid) for k in ch["keys"]): found, hi = mid, mid
                else: lo = mid
            if found: end = round(found, 2)
            else:
                rem = sum(len(c["text"]) for c in chunks[i:])
                end = round(cur + (b - cur) * len(ch["text"]) / rem, 2)
        subs.append({"text": ch["text"], "start": round(cur, 2), "end": end}); cur = end
        print(f"{subs[-1]['start']:7.2f}-{end:7.2f}  {ch['text']}", flush=True)
json.dump(subs, open(out, "w"), ensure_ascii=False, indent=1)
