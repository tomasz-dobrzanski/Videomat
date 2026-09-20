"""CLI Videomat.  Uruchamianie:  python -m videomat.cli <komenda>  (lub videomat.cmd <komenda>)"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # konsola Windows cp1252 vs polskie znaki
console = Console()


def _show(result: dict) -> None:
    t = Table(show_header=False)
    for k, v in result.items():
        if isinstance(v, list):
            v = "\n".join(str(x) for x in v) if v else "-"
        t.add_row(str(k), str(v))
    console.print(t)


@click.group()
def cli():
    """Videomat — napisy, lektor, muzyka, avatar, rough cut dla 9:16."""
    config.ensure_dirs()


@cli.command()
def doctor():
    """Sprawdź środowisko: ffmpeg, enkoder, GPU, klucze, fonty."""
    import shutil
    rows = {"ffmpeg": shutil.which("ffmpeg") or "BRAK", "encoder": config.encoder(),
            "fonts": ", ".join(p.name for p in config.FONTS.glob("*.ttf")) or "BRAK"}
    try:
        import torch
        rows["cuda"] = f"{torch.cuda.is_available()} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-'})"
    except Exception as e:
        rows["cuda"] = f"torch niedostępny: {e}"
    for k in ("ELEVENLABS_API_KEY", "GEMINI_API_KEY", "ELEVENLABS_VOICE_ID"):
        rows[k] = "ustawiony" if config.env(k) else "BRAK (.env)"
    _show(rows)


@cli.command()
@click.argument("video", type=click.Path(exists=True))
@click.option("--fit", type=click.Choice(["none", "crop", "pad"]), default="none")
@click.option("--theme", type=click.Choice(["hitech", "clean", "bold"]), default="hitech")
@click.option("--anim", default="highlight", help="highlight|word_blast|pop|fade|slide_up|typewriter")
@click.option("--words", type=click.Path(exists=True), help="words.json z TTS (pomija ASR)")
@click.option("--srt", type=click.Path(exists=True), help="gotowe napisy SRT")
@click.option("--lang", default="pl")
@click.option("--model", default=None, help="whisper: tiny|base|small|medium|large-v3")
@click.option("--font", default=None)
@click.option("--no-render", is_flag=True, help="tylko spec.json (do ręcznej edycji)")
def captions(video, fit, theme, anim, words, srt, lang, model, font, no_render):
    """Transkrybuj i wypal animowane napisy; zapisz klatki weryfikacyjne."""
    from .captions import run_captions
    r = run_captions(video, fit=fit, theme=theme, animation=anim, words_json=words, srt=srt,
                     language=lang, model=model, font=font, render=not no_render)
    _show(r)
    if r.get("uncertain"):
        console.print("[yellow]Słowa o niskiej pewności (sprawdź w spec.json):[/] " +
                      ", ".join(f"{u['w']}@{u['t']}s" for u in r["uncertain"][:30]))
    console.print("[bold]Obejrzyj klatki w out/verify/ przed oddaniem.[/]")


@cli.command()
@click.argument("video", type=click.Path(exists=True))
@click.argument("spec", type=click.Path(exists=True))
@click.option("--fit", type=click.Choice(["none", "crop", "pad"]), default="none")
@click.option("--tag", default="")
def render(video, spec, fit, tag):
    """Wyrenderuj wideo z (poprawionego) spec.json."""
    from .captions import render_spec
    _show(render_spec(video, spec, fit=fit, tag=tag))


@cli.command()
@click.argument("video", type=click.Path(exists=True))
@click.option("--lang", default="pl")
@click.option("--model", default=None)
def transcribe(video, lang, model):
    """Sama transkrypcja -> work/<name>_transcript.json"""
    from .transcribe import transcribe as tr
    out = config.WORK / f"{Path(video).stem}_transcript.json"
    r = tr(video, out, language=lang, model_size=model)
    for s in r["segments"]:
        console.print(f"{s['start']:7.2f}-{s['end']:7.2f}  {s['text']}")
    console.print(f"-> {out}  (niepewne słowa: {len(r['uncertain'])})")


@cli.command()
@click.argument("text")
@click.option("--out", default=None, help="plik mp3 (domyślnie work/vo.mp3)")
@click.option("--voice", default=None, help="voice_id (domyślnie ELEVENLABS_VOICE_ID)")
@click.option("--model", default="eleven_multilingual_v2")
@click.option("--speed", default=1.0, type=float)
@click.option("--no-timestamps", is_flag=True)
def tts(text, out, voice, model, speed, no_timestamps):
    """Lektor ElevenLabs. TEXT = tekst albo ścieżka do pliku .txt"""
    from .tts import tts as _tts
    if Path(text).is_file():
        text = Path(text).read_text(encoding="utf-8")
    out = out or config.WORK / "vo.mp3"
    _show(_tts(text, out, voice_id=voice, model_id=model, speed=speed, timestamps=not no_timestamps))


@cli.command()
def voices():
    """Lista głosów ElevenLabs dostępnych na koncie."""
    from .elevenlabs_client import list_voices
    t = Table("voice_id", "name", "labels")
    for v in list_voices():
        t.add_row(v["voice_id"], str(v["name"]), ", ".join(f"{k}={x}" for k, x in v["labels"].items()))
    console.print(t)


@cli.command()
@click.argument("prompt")
@click.option("--out", default=None)
@click.option("--length", default=30.0, type=float, help="sekundy 3–600")
@click.option("--vocals", is_flag=True, help="pozwól na wokal (domyślnie instrumental)")
@click.option("--model", default="music_v2", type=click.Choice(["music_v1", "music_v2", "music_v2_5"]))
@click.option("--normalize/--no-normalize", default=True, help="loudnorm do -14 LUFS")
def music(prompt, out, length, vocals, model, normalize):
    """Muzyka z ElevenLabs Music."""
    from .music import music as _music, loudnorm, measure_lufs
    out = Path(out) if out else config.WORK / "music.mp3"
    p = _music(prompt, out, length_s=length, instrumental=not vocals, model_id=model)
    r = {"audio": p, "lufs": measure_lufs(p)}
    if normalize:
        n = loudnorm(p, p.with_name(p.stem + "_norm.wav"))
        r.update({"normalized": n, "lufs_norm": measure_lufs(n)})
    _show(r)


@cli.command()
@click.argument("text")
@click.option("--out", default=None)
@click.option("--duration", default=None, type=float)
@click.option("--loop", is_flag=True)
def sfx(text, out, duration, loop):
    """Efekt dźwiękowy z ElevenLabs."""
    from .music import sfx as _sfx
    out = out or config.WORK / "sfx.mp3"
    _show({"audio": _sfx(text, out, duration_s=duration, loop=loop)})


@cli.command()
@click.argument("photo", type=click.Path(exists=True))
@click.option("--script", "script_", required=True, help="tekst lub plik .txt")
@click.option("--mode", type=click.Choice(["veo-voice", "eleven-voice"]), default="veo-voice")
@click.option("--tier", type=click.Choice(["fast", "standard"]), default="fast")
@click.option("--res", type=click.Choice(["720p", "1080p"]), default="720p")
@click.option("--seconds", type=click.Choice(["4", "6", "8"]), default="8")
@click.option("--style", default="nowoczesne biuro technologiczne, styl korporacyjny")
@click.option("--dry-run", is_flag=True, help="pokaż prompty i koszt, nic nie generuj")
@click.option("--yes", is_flag=True, help="nie pytaj o potwierdzenie kosztu")
def avatar(photo, script_, mode, tier, res, seconds, style, dry_run, yes):
    """Mówiący avatar z fotki przez Veo 3.1 (płatne!)."""
    from .avatar import generate_clips
    if Path(script_).is_file():
        script_ = Path(script_).read_text(encoding="utf-8")

    def confirm(plan):
        console.print_json(json.dumps(plan, ensure_ascii=False))
        return yes or click.confirm(f"Szacowany koszt ~${plan['cost_estimate_usd']}. Generować?", default=False)

    r = generate_clips(photo, script_, config.WORK / "avatar", mode=mode, tier=tier, resolution=res,
                       seconds=int(seconds), style=style, dry_run=dry_run, confirm=confirm)
    if dry_run:
        console.print_json(json.dumps(r["plan"], ensure_ascii=False))
    else:
        _show({"clips": r["clips"], "cancelled": r.get("cancelled", False)})


@cli.command()
@click.argument("prompt")
@click.option("--out", default=None)
@click.option("--ref", type=click.Path(exists=True), help="obraz referencyjny (edycja)")
@click.option("--ar", default="9:16")
def image(prompt, out, ref, ar):
    """Plansza / B-roll still z Gemini (płatne)."""
    from .images import generate_image
    out = out or config.WORK / "image.png"
    _show({"image": generate_image(prompt, out, reference=ref, aspect_ratio=ar)})


@cli.command()
@click.argument("video", type=click.Path(exists=True))
@click.option("--silence", default=-30.0, type=float, help="próg dB")
@click.option("--min", "min_sil", default=0.4, type=float, help="min długość ciszy [s]")
@click.option("--pad", default=0.08, type=float)
@click.option("--export", default="edl,fcpxml")
@click.option("--transcript", type=click.Path(exists=True), help="transcript.json do flagowania powtórek")
@click.option("--drop-repeats", is_flag=True)
@click.option("--no-render", is_flag=True)
def roughcut(video, silence, min_sil, pad, export, transcript, drop_repeats, no_render):
    """Wycięcie cisz + EDL/FCPXML do DaVinci Resolve / Premiere."""
    from .roughcut import roughcut as _rc
    tr = json.loads(Path(transcript).read_text(encoding="utf-8")) if transcript else None
    _show(_rc(video, silence_db=silence, min_silence=min_sil, pad=pad,
              export=tuple(x for x in export.split(",") if x), transcript=tr,
              drop_repeats=drop_repeats, render=not no_render))


@cli.command()
@click.option("--video", required=True, type=click.Path(exists=True), help="wideo lub kilka po przecinku (sklejone)")
@click.option("--vo", type=click.Path(exists=True))
@click.option("--music", "music_", type=click.Path(exists=True))
@click.option("--subs", type=click.Path(exists=True), help=".ass")
@click.option("--fit", type=click.Choice(["none", "crop", "pad"]), default="none")
@click.option("--music-db", default=-14.0, type=float)
@click.option("--no-original-audio", is_flag=True)
@click.option("--vo-offset", default=0.0, type=float)
@click.option("--tag", default="final")
def assemble(video, vo, music_, subs, fit, music_db, no_original_audio, vo_offset, tag):
    """Miks: wideo + lektor + muzyka (ducking) + napisy -> out/<name>_final_vN.mp4"""
    from .assemble import assemble as _asm, concat_clips
    vids = [v for v in video.split(",") if v]
    if len(vids) > 1:
        video = concat_clips(vids, config.WORK / "joined.mp4", fit=fit)
        fit = "none"
    out = _asm(video, vo=vo, music=music_, subs=subs, fit=fit, music_db=music_db,
               keep_original_audio=not no_original_audio, vo_offset=vo_offset, tag=tag)
    _show({"video": out})


@cli.command()
@click.argument("video", type=click.Path(exists=True))
@click.argument("times", nargs=-1, type=float)
def frames(video, times):
    """Wyciągnij klatki w podanych sekundach do out/verify/."""
    from .verify import frames_at
    _show({"frames": frames_at(video, list(times) or [1.0])})


@cli.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8000, type=int)
def serve(host, port):
    """Panel web (FastAPI) — tylko localhost."""
    import uvicorn
    uvicorn.run("web.app:app", host=host, port=port, reload=False)


@cli.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8000, type=int)
@click.option("--build/--no-build", default=True, help="Zbuduj frontend, jeśli go brakuje.")
def studio(host, port, build):
    """Videomat Studio — edytor filmow w przegladarce (tylko localhost)."""
    import subprocess
    import uvicorn
    static = config.ROOT / "web" / "static" / "index.html"
    source = config.ROOT / "studio"
    if build and not static.exists() and source.exists():
        console.print("[cyan]Buduje frontend studia (pierwsze uruchomienie)...[/]")
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        if not (source / "node_modules").exists():
            subprocess.run([npm, "install", "--no-fund", "--no-audit"], cwd=source, check=True)
        subprocess.run([npm, "run", "build"], cwd=source, check=True)
    console.print(f"[bold]Studio:[/] http://{host}:{port}")
    uvicorn.run("web.app:app", host=host, port=port, reload=False)


@cli.command("film")
@click.argument("film_json", type=click.Path(exists=True))
@click.option("--quality", type=click.Choice(["proxy", "final"]), default="final")
@click.option("--frame", type=float, default=None, help="Zamiast filmu wyrenderuj jedna klatke (sekunda).")
def film_cmd(film_json, quality, frame):
    """Render filmu z deklaratywnego film.json."""
    from videomat.render import Renderer, load_film
    path = Path(film_json)
    movie = load_film(path)
    renderer = Renderer(movie, path.parent, log=lambda m: console.print(f"[dim]{m}[/]"))
    if frame is not None:
        _show({"klatka": renderer.render_frame(frame, quality=quality)})
        return
    result = renderer.render_film(quality=quality)
    _show(result)


@cli.command()
@click.argument("source")
@click.option("--title", default=None, help="Tytul dokumentu")
@click.option("--subtitle", default="")
@click.option("--lang", default="pl")
@click.option("--model", default="large-v3", help="tiny|base|small|medium|large-v3")
@click.option("--speakers", default=None, type=int, help="Znana liczba mowcow")
@click.option("--max-speakers", default=None, type=int)
@click.option("--no-diarize", is_flag=True, help="Bez rozpoznawania mowcow")
@click.option("--names", default=None, help='Mapowanie, np. "SPEAKER_00=Jan Kowalski;SPEAKER_01=Anna Nowak"')
@click.option("--formats", default="docx,md,txt,csv,json")
@click.option("--out", default=None, type=click.Path())
def stenogram(source, title, subtitle, lang, model, speakers, max_speakers, no_diarize,
              names, formats, out):
    """Stenogram z adresu YouTube albo pliku: transkrypcja + mowcy + dokumenty."""
    from videomat.stenogram import Options, run
    mapping = {}
    if names:
        for pair in names.split(";"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                mapping[key.strip()] = value.strip()
    options = Options(title=title or "Stenogram", subtitle=subtitle, language=lang, model=model,
                      speakers=speakers, max_speakers=max_speakers, diarize=not no_diarize,
                      speaker_names=mapping,
                      formats=tuple(f.strip() for f in formats.split(",") if f.strip()))
    result = run(source, options, out_dir=Path(out) if out else None,
                 on_progress=lambda p, m: console.print(f"[dim]{int(p * 100):3d}%  {m}[/]"))
    _show({"wypowiedzi": result["utterances"], "dlugosc": result["duration"],
           "status QC": result["qc"]["status"],
           "niskiej pewnosci": result["qc"]["low_confidence"], **result["files"]})
    if result["speakers"]:
        t = Table("mowca", "czas [s]", "wypowiedzi", "slowa")
        for row in result["speakers"]:
            t.add_row(row["speaker"], str(row["seconds"]), str(row["turns"]), str(row["words"]))
        console.print(t)


@cli.command()
@click.option("--source", default="mic", help='"mic" albo adres transmisji / sciezka pliku')
@click.option("--device", default=None, type=int, help="Numer wejscia dzwieku")
@click.option("--lang", default="pl")
@click.option("--model", default="small", help="Na zywo oplaca sie mniejszy model")
@click.option("--seconds", default=0, type=int, help="Zakoncz po tylu sekundach (0 = do Ctrl+C)")
@click.option("--finalize/--no-finalize", default=True,
              help="Po zakonczeniu przepusc nagranie przez pelny stenogram z mowcami")
def live(source, device, lang, model, seconds, finalize):
    """Stenogram na zywo: mikrofon albo transmisja, tekst w trakcie mowienia."""
    import time
    from videomat.live import LiveSession

    def show(event):
        kind = event.get("type")
        if kind == "utterance":
            console.print(f"[bold]{int(event['start'] // 60):02d}:{int(event['start'] % 60):02d}[/]  "
                          f"{event['text']}")
        elif kind == "draft":
            console.print(f"[dim]… {event['text']}[/]")
        elif kind == "error":
            console.print(f"[red]{event['message']}[/]")
        else:
            console.print(f"[dim]· {event.get('message', kind)}[/]")

    session = LiveSession(on_update=show, source=source, device=device,
                          language=lang, model=model)
    session.start()
    console.print("[cyan]Nasluch wlaczony. Ctrl+C konczy.[/]")
    try:
        start = time.time()
        while not session.error and (seconds <= 0 or time.time() - start < seconds):
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    final = session.stop()
    _show({"wypowiedzi": len(final), **session.save()})
    if finalize and final:
        console.print("[cyan]Skladam pelny stenogram z rozpoznaniem mowcow...[/]")
        try:
            _show(session.finalize()["files"])
        except Exception as exc:
            console.print(f"[yellow]Pelny stenogram pominiety: {str(exc)[:160]}[/]")


@cli.command("audio-devices")
def audio_devices():
    """Lista wejsc dzwieku do stenogramu na zywo."""
    from videomat.live import list_devices
    t = Table("nr", "nazwa", "kanaly", "domyslne")
    for d in list_devices():
        t.add_row(str(d["index"]), d["name"], str(d["channels"]), "tak" if d["default"] else "")
    console.print(t)


@cli.command("voice-split")
@click.argument("film_json", type=click.Path(exists=True))
@click.argument("recording", type=click.Path(exists=True))
@click.option("--model", default="medium")
def voice_split(film_json, recording, model):
    """Jedno nagranie lektora -> osobne pliki linii (work/<projekt>/<id>.mp3), wyrownane do skryptu."""
    from videomat import speech
    from videomat.render import load_film
    path = Path(film_json)
    movie = load_film(path)
    work = config.WORK / path.parent.name
    report = speech.split_recording(Path(recording), movie, work, model_size=model)
    t = Table("linia", "od", "do", "dlugosc", "zgodnosc", "ok")
    for row in report:
        t.add_row(row["id"], str(row.get("start", "-")), str(row.get("end", "-")),
                  str(row.get("duration", "-")), str(row.get("coverage", "-")),
                  "tak" if row.get("ok") else "[red]SPRAWDZ[/]")
    console.print(t)
    console.print(f"[dim]raport: {work / 'split_report.json'}[/]")


@cli.group()
def project():
    """Projekty studia."""


@project.command("list")
def project_list():
    """Lista projektow."""
    from videomat import projects as pr
    t = Table("id", "nazwa", "sceny", "lektor")
    for row in pr.listing():
        t.add_row(row["id"], row["name"], str(row["scenes"]), str(row["narration"]))
    console.print(t)


@project.command("new")
@click.argument("name")
def project_new(name):
    """Nowy projekt."""
    from videomat import projects as pr
    _show(pr.create(name))


if __name__ == "__main__":
    cli()
