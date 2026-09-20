---
name: video-captions
description: Add animated, high-tech style captions (hardsub), big headline overlays, and cinematic cuts to videos, optimized for vertical 9:16 short-form content (TikTok, Reels, Shorts). Use this skill whenever the user wants to add subtitles, captions, napisy, text overlays, headlines, or animated text to a video file, transcribe a video's speech, convert a video to vertical 9:16, or edit a video into a short-form / meme / promo cut — even if they don't say "captions" explicitly. Also use when a user uploads a video and asks to "make it social-media ready", "add text", or "make something out of this".
---

# Video captions — animated hardsub, headlines and cinematic cuts for 9:16

Burns text into video with FFmpeg + libass (ASS subtitle format). ASS, not `drawtext`, because only ASS gives real animation: wipes, karaoke sweeps, moves, fades, blur, vector shapes.

## Hard constraints — read first

1. **Speech-to-text IS available** via `scripts/transcribe.py` (sherpa-onnx Whisper; models auto-download from GitHub releases, reachable even in locked-down sandboxes). If a video has a voiceover, ALWAYS transcribe it and put the ACTUAL spoken words on screen. Never invent narration over real speech.
2. **ASR over music beds makes errors.** Cross-check garbled words by running both model sizes (`base` and `small`), fix only what context makes obvious, and TELL the user which words stayed uncertain. Never silently guess words a real person said — especially in political or journalistic material.
3. **No audio generation.** No TTS, no music generation, no voice cloning, no talking-avatar tool, and third-party audio APIs (ElevenLabs etc.) are blocked by the egress proxy. If the user wants a voiceover, they supply the file; then sync the edit to it.
4. **Verify by looking.** After every render, extract frames where text appears and `view` them. Check diacritics (ąćęłńóśźż), safe zones, wrapping, collisions with burned-in source graphics. Report what was verified. Never deliver an unviewed render.
5. **New filename for every render** (`cut_v1.mp4`, `cut_v2.mp4`). Clients cache by name; reusing one makes the user watch the old version and conclude nothing was done.
6. **Preserve the source.** Work in /home/claude, deliver to /mnt/user-data/outputs.

## Factual accuracy in real-world content

When a cut makes claims about real, named people (politics, business, journalism):
- Put ONLY the words actually spoken into quote captions.
- Dates, vote counts, job titles, party labels and outcomes are assertions. If they can't be verified from the source material or a link the user provides, say so plainly, once, and let the user decide — they are the publisher. Don't quietly render unverified figures as on-screen fact.
- Flag internal inconsistencies the user may not have noticed (e.g. one date stamped on two visibly different events).
- Source clips often carry burned-in third-party graphics (channel bugs, phone numbers, ad banners). Crop them out — they collide with captions and are unrelated content — and say that you did.

## Workflow

### 1. Inspect input
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 in.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 in.mp4
```
Fit strategy: already 9:16 → `none`; horizontal with centered subject → `crop`; full frame matters or source is low-res → `pad` (blurred background).

### 2. Transcribe and time
```bash
python3 scripts/transcribe.py in.mp4 transcript.json pl small
```
Gives VAD-timed phrase segments. Split them into 2–4 word subs, then fix real boundaries:
```bash
python3 scripts/align_phrases.py plan.json audio16k.wav subs.json base
```
It binary-searches each chunk's true end time (~4 decodes per boundary). **Run in the FOREGROUND in batches under 5 minutes — background jobs are killed when the command returns.** Then sanity-check speech rate (0.18–0.75 s/word); fall back to character-proportional timing for any segment that violates it.

Scene cuts, so text lands on them:
```bash
ffmpeg -i in.mp4 -vf "select='gt(scene,0.28)',showinfo" -f null - 2>&1 | grep -oP "pts_time:\K[0-9.]+"
```

### 3. Write the spec
Full schema in the `make_ass.py` docstring. Per-caption optional fields: `size` (px in 1920-space), `y`, `drift`, `glow`, plus `kicker` and `panel` for headlines.

```json
{
  "theme": "hitech",
  "captions": [
    {"text": "gdzie *ryzyko* jest realne", "start": 7.4, "end": 10.4,
     "animation": "highlight", "size": 92, "y": 1450, "drift": false},
    {"text": "ROBOT IDZIE\n*PIERWSZY*", "start": 20.7, "end": 24.7,
     "animation": "headline", "size": 92, "y": 640, "kicker": "Skan · Mapa · Detekcja"}
  ]
}
```

Caption animations: `word_blast` (one word at a time, rapid pop — hooks, punchlines), `highlight` (default for narration; word-by-word colour sweep = constant motion), `headline` (hero title: per-line wipe reveal + rise + accent bar + translucent panel), `typewriter`, `pop`, `fade`, `slide_up`, `none`. `*word*` or `*multi word span*` = accent colour, works with punctuation.

**Uniform headlines.** Headlines in one clip share a system: same `size`, same `y`, same structure (kicker + white line + accent line + panel). Keep every line ≤15 characters so auto-fit never shrinks one out of step. Move a headline only when it would cover the subject — move it, don't resize it.

**Sizing.** Verbatim subs ~90 px at 1920 height; 54–70 px reads as too small on a phone. Headlines 92–104 px.

**Pacing.** Something moves every 1–2 s. Long static chunks read as "no animation".

### 4. Render
```bash
python3 scripts/make_ass.py spec.json subs.ass
./scripts/render.sh in.mp4 subs.ass out_v1.mp4 none     # or crop | pad
```
H.264 CRF 19, `-preset fast`, yuv420p, AAC 192k, +faststart. Keep `fast`: `medium` pushes a 60 s 1080x1920 render past the 300 s command limit.

### 5. Cinematic cuts (meme / promo / montage)
`scripts/build_cinematic_cut.py` is a helper library for multi-segment edits: title cards on black, source fragments fitted to 9:16 with blurred pad + film grade (grain, vignette, contrast), freeze frames with stamps, slow-zoom stills. Build each segment as its own mp4 with identical encoding, then concat:
```bash
printf "file '%s'\n" seg1.mp4 seg2.mp4 > list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -c copy out_v1.mp4
```
Every segment MUST share resolution, fps, pixel format and audio layout (1080x1920, 30 fps, yuv420p, AAC 48 kHz stereo) or `-c copy` concat breaks.

Devices that work: hard cut to black; a beat of complete silence after a punchline; freeze frame + corner stamp; a counter badge that increments only on what actually happened; serif letterspaced title cards; slow zoom on a still for the closer.

### 6. Deliver
Copy to `/mnt/user-data/outputs/`, call `present_files`, summarize what was built and what still needs the user's input.

## ASS gotchas that cost time

- **Colours are `&HBBGGRR`, not RGB.** `&H00D9FF&` is gold, not cyan. Cyan #00E5FF is `&H00FFE500`. Verify a colour on a frame before building a spec around it.
- Escape user text: `{`/`}` break tag parsing; `\n` must become `\N`.
- In a glow/shadow duplicate layer under text, strip accent markers from the duplicate — otherwise the halo renders literal `*` and looks like doubled ghost text.
- `\clip` wipes need `\t(0,260,\clip(...))`; the static clip only sets the start state.
- Keep `ScaledBorderAndShadow: yes` in `[Script Info]`.
- Karaoke `\kf`: Primary = post-sweep colour, Secondary = pre-sweep colour.

## References

- `references/ass-tags.md` — override-tag cheatsheet for effects beyond the presets.
- Script docstrings — full CLI and JSON schemas.

## Troubleshooting

- Tofu boxes instead of Polish letters → set spec `"font"` to `"DejaVu Sans"` or `"Noto Sans"`; `Poppins` and `DejaVu Serif` both carry full Polish plus `ö`.
- `ass` filter can't find the file → avoid spaces/special characters in paths.
- Text too small/large on a non-1080p source → set `"resolution"` in the spec to the real output size.
- Render times out → `-preset fast`, or render in segments and concat.
