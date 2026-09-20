#!/usr/bin/env bash
# render.sh — Fit a video to 9:16 (optional) and burn an .ass subtitle file.
#
# Usage:
#   ./render.sh INPUT.mp4 SUBS.ass OUTPUT.mp4 [FIT]
#
#   FIT (how to reach 9:16 1080x1920 if the source isn't already vertical):
#     none  - keep source resolution as-is (default; use when source is already 9:16)
#     crop  - center-crop to 9:16 (loses sides of horizontal footage)
#     pad   - blurred-background pad (keeps full frame, fills top/bottom with blur)
#
# Encoding follows short-form best practices: H.264 High, CRF 19, yuv420p,
# AAC 192k, +faststart. Audio is re-encoded only if not already AAC.
set -euo pipefail

IN="$1"; SUBS="$2"; OUT="$3"; FIT="${4:-none}"

case "$FIT" in
  none) VF="ass='${SUBS}'" ;;
  crop) VF="crop=ih*9/16:ih,scale=1080:1920,ass='${SUBS}'" ;;
  pad)  VF="split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=25[bg];[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,ass='${SUBS}'" ;;
  *) echo "Unknown FIT: $FIT (use none|crop|pad)"; exit 1 ;;
esac

if [ "$FIT" = "pad" ]; then
  ffmpeg -y -i "$IN" -filter_complex "$VF" \
    -c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -movflags +faststart "$OUT"
else
  ffmpeg -y -i "$IN" -vf "$VF" \
    -c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -movflags +faststart "$OUT"
fi

echo "Done: $OUT"
