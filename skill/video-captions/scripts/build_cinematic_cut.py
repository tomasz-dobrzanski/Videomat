#!/usr/bin/env python3
"""Build a cinematic political-meme cut from three source clips."""
import subprocess, sys, os

W, H, FPS = 1080, 1920, 30
ENC = ["-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
       "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
SERIF = "DejaVu Serif"
SANS = "Poppins"

# fit any source into 9:16 with blurred pad + cinematic grade
FIT = (f"split[a][b];"
       f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
       f"gblur=sigma=30,eq=brightness=-0.12:saturation=0.5[bg];"
       f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
       f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
       f"eq=contrast=1.10:saturation=0.85:gamma=0.97,"
       f"noise=alls=7:allf=t,vignette=PI/4.5,setsar=1")

GRADE_STILL = ("eq=contrast=1.10:saturation=0.85:gamma=0.97,"
               "noise=alls=7:allf=t,vignette=PI/4.5,setsar=1")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(" ".join(cmd)[:400]); print(r.stderr[-1500:]); sys.exit(1)


def ass(path, events, playres=(W, H)):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {playres[0]}
PlayResY: {playres[1]}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{SERIF},96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,14,0,1,0,0,5,60,60,0,1
Style: Sub,{SANS},58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,6,0,1,3,0,5,60,60,0,1
Style: Quote,{SANS},74,&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,70,70,0,1
Style: Stamp,{SANS},46,&H0000D9FF,&H0000D9FF,&H00101010,&H00000000,-1,0,0,0,100,100,8,0,1,3,0,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Text
"""
    open(path, "w", encoding="utf-8").write(head + "\n".join(events) + "\n")


def ts(s):
    cs = max(0, int(round(s * 100)))
    h, r = divmod(cs, 360000); m, r = divmod(r, 6000); sec, c = divmod(r, 100)
    return f"{h}:{m:02d}:{sec:02d}.{c:02d}"


def D(layer, a, b, style, text):
    return f"Dialogue: {layer},{ts(a)},{ts(b)},{style},,0,0,0,{text}"


def black(dur, subs_file, out, audio="anullsrc=r=48000:cl=stereo"):
    vf = f"ass='{subs_file}',noise=alls=5:allf=t,vignette=PI/5"
    run(["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={dur}",
         "-f", "lavfi", "-i", audio, "-t", str(dur),
         "-vf", vf, "-shortest"] + ENC + [out])


def clipseg(src, a, b, subs_file, out, extra=""):
    vf = FIT + (("," + extra) if extra else "") + f",ass='{subs_file}'"
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(a), "-to", str(b), "-i", src,
         "-vf", vf, "-af", "aformat=sample_rates=48000:channel_layouts=stereo"] + ENC + [out])


def freeze(src, t, dur, subs_file, out):
    png = out + ".png"
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", src, "-frames:v", "1",
         "-vf", FIT.replace("setsar=1", "setsar=1"), png])
    vf = f"{GRADE_STILL},ass='{subs_file}'"
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", str(dur), "-i", png,
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(dur),
         "-vf", vf, "-shortest"] + ENC + [out])


# ---------------------------------------------------------------- segments
def seg_cold():
    e = [
        D(0, 0.30, 4.00, "Title", r"{\an5\pos(540,900)\fs104\fsp18\fad(600,300)\c&HFFFFFF&}OJCIEC CHRZESTNY"),
        D(0, 2.30, 4.00, "Sub",   r"{\an5\pos(540,1050)\fs54\fsp14\fad(300,250)\c&H9F9F9F&}POLSKA. 2026."),
    ]
    ass("s_cold.ass", e)
    black(4.0, "s_cold.ass", "seg1.mp4")


def seg_quote(src, a, b, quote, counter, stamp, idx):
    """clip + freeze frame with date stamp"""
    dur = b - a
    e = [D(0, 0.0, dur, "Quote",
           r"{\an2\pos(540,1560)\fad(200,150)}" + quote),
         D(1, 0.25, dur, "Stamp",
           r"{\an9\pos(1030,150)\fs40\c&H00D9FF&\fad(250,0)}OJCIEC CHRZESTNY \N{\an9\fs78\b1}x" + str(counter))]
    ass(f"s_q{idx}.ass", e)
    clipseg(src, a, b, f"s_q{idx}.ass", f"seg_q{idx}.mp4")
    f = [D(0, 0.0, 0.9, "Stamp",
           r"{\an5\pos(540,1700)\fs62\c&HFFFFFF&\fsp10\fad(80,0)}" + stamp),
         D(1, 0.0, 0.9, "Stamp",
           r"{\an5\pos(540,1620)\fs34\c&H00D9FF&\fsp12}ZAREJESTROWANO")]
    ass(f"s_f{idx}.ass", f)
    freeze(src, b - 0.05, 0.9, f"s_f{idx}.ass", f"seg_f{idx}.mp4")
