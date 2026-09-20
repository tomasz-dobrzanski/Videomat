#!/usr/bin/env python3
"""
transcribe.py — VAD-segmented speech-to-text for video files using sherpa-onnx
Whisper models hosted on GitHub releases (works in environments where only
GitHub/PyPI are network-allowed).

Usage:
    pip install sherpa-onnx soundfile --break-system-packages
    python3 transcribe.py input.mp4 transcript.json [pl] [base|small]

Downloads models on first run (~200 MB base / ~640 MB small) from:
  https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/
Output: JSON list of {"start", "end", "text"} phrase segments (VAD-timed).

Accuracy notes: small >> base for Polish; music beds degrade both. ALWAYS
review the transcript, cross-check garbled words against a second model size,
and flag uncertain words to the user instead of guessing silently.
"""
import json, os, subprocess, sys, urllib.request

BASE_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"

def fetch(name, dest):
    if not os.path.exists(dest):
        print(f"downloading {name} ...", file=sys.stderr)
        urllib.request.urlretrieve(BASE_URL + name, dest)

def main():
    src, out = sys.argv[1], sys.argv[2]
    lang = sys.argv[3] if len(sys.argv) > 3 else "pl"
    size = sys.argv[4] if len(sys.argv) > 4 else "small"

    import sherpa_onnx, soundfile as sf, numpy as np

    fetch("silero_vad.onnx", "silero_vad.onnx")
    tarball = f"sherpa-onnx-whisper-{size}.tar.bz2"
    mdir = f"sherpa-onnx-whisper-{size}"
    if not os.path.isdir(mdir):
        fetch(tarball, tarball)
        subprocess.run(["tar", "xjf", tarball], check=True)

    wav = "._stt_16k.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                    "-ac", "1", "-ar", "16000", wav], check=True)
    audio, sr = sf.read(wav, dtype="float32")

    vc = sherpa_onnx.VadModelConfig()
    vc.silero_vad.model = "silero_vad.onnx"
    vc.silero_vad.threshold = 0.5
    vc.silero_vad.min_silence_duration = 0.35
    vc.silero_vad.min_speech_duration = 0.25
    vc.silero_vad.max_speech_duration = 12.0
    vc.sample_rate = sr
    vad = sherpa_onnx.VoiceActivityDetector(vc, buffer_size_in_seconds=len(audio)/sr + 10)

    rec = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=f"{mdir}/{size}-encoder.int8.onnx",
        decoder=f"{mdir}/{size}-decoder.int8.onnx",
        tokens=f"{mdir}/{size}-tokens.txt",
        language=lang, task="transcribe", num_threads=4)

    i, w = 0, 512
    while i < len(audio):
        vad.accept_waveform(audio[i:i+w]); i += w
    vad.flush()

    segs = []
    while not vad.empty():
        s = vad.front
        start = s.start / sr
        st = rec.create_stream()
        st.accept_waveform(sr, np.array(s.samples, dtype="float32"))
        rec.decode_stream(st)
        segs.append({"start": round(start, 2),
                     "end": round(start + len(s.samples)/sr, 2),
                     "text": st.result.text.strip()})
        vad.pop()

    json.dump(segs, open(out, "w"), ensure_ascii=False, indent=1)
    for s in segs:
        print(f"{s['start']:7.2f}-{s['end']:7.2f}  {s['text']}")

if __name__ == "__main__":
    main()
