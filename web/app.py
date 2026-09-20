"""Videomat Studio — API edytora (FastAPI, tylko localhost).

Uruchomienie: `videomat studio` albo `python -m videomat.cli studio`.
Frontend budowany z katalogu studio/ trafia do web/static i jest montowany NA KOŃCU, żeby API
miało pierwszeństwo nad ścieżkami plików.
"""
from __future__ import annotations

import json
import threading
import traceback
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from videomat import config, jobs as jobslib, projects, render, speech
from videomat.timeline import Film

app = FastAPI(title="Videomat Studio")
config.ensure_dirs()
projects.PROJECTS.mkdir(exist_ok=True)
QUEUE = jobslib.JobQueue()
STATIC = Path(__file__).parent / "static"
LEGACY = Path(__file__).parent / "templates" / "index.html"
PROPOSALS: dict[str, dict] = {}

app.mount("/out", StaticFiles(directory=str(config.OUT)), name="out")
app.mount("/work", StaticFiles(directory=str(config.WORK)), name="work")
app.mount("/media", StaticFiles(directory=str(projects.PROJECTS)), name="media")


def _renderer(pid: str) -> render.Renderer:
    film = projects.load(pid)
    return render.Renderer(film, projects.project_dir(pid), projects.work_dir(pid))


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc) or exc.__class__.__name__)


# ------------------------------------------------------------------ stan
@app.get("/api/status")
def status():
    return {
        "encoder": config.encoder(),
        "keys": {name: bool(config.env(name)) for name in
                 ("ELEVENLABS_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "ELEVENLABS_VOICE_ID")},
        "features": {"tts": bool(config.env("ELEVENLABS_API_KEY")),
                     "prompt": bool(config.env("OPENAI_API_KEY")),
                     "avatar": False},
        "notes": {"avatar": "Klucz Gemini ma zablokowaną usługę — generowanie awatara wyłączone.",
                  "music": "ElevenLabs Music wymaga płatnego planu; podkład wgrywasz jako plik."},
    }


# ------------------------------------------------------------------ projekty
@app.get("/api/projects")
def list_projects():
    return projects.listing()


@app.post("/api/projects")
def create_project(name: str = Body(..., embed=True)):
    try:
        return projects.create(name)
    except projects.ProjectError as exc:
        raise _fail(exc)


@app.get("/api/projects/{pid}/film")
def get_film(pid: str):
    try:
        film = projects.load(pid)
    except Exception as exc:
        raise _fail(exc)
    return json.loads(film.model_dump_json())


@app.put("/api/projects/{pid}/film")
def put_film(pid: str, payload: dict = Body(...)):
    try:
        film = Film.model_validate(payload)
        projects.save(pid, film)
    except Exception as exc:
        raise _fail(exc)
    return {"ok": True}


@app.get("/api/projects/{pid}/timeline")
def get_timeline(pid: str):
    try:
        resolved = _renderer(pid).resolved(refresh=True)
    except Exception as exc:
        raise _fail(exc)
    return json.loads(resolved.model_dump_json())


@app.get("/api/projects/{pid}/assets")
def get_assets(pid: str):
    try:
        return projects.assets_overview(pid)
    except Exception as exc:
        raise _fail(exc)


@app.post("/api/projects/{pid}/assets")
async def upload_asset(pid: str, file: UploadFile = File(...), transcribe: bool = Form(True)):
    try:
        data = await file.read()
        info = projects.add_asset(pid, file.filename or "plik", data)
    except Exception as exc:
        raise _fail(exc)
    if transcribe and info["kind"] == "clip":
        key = info["key"]

        def work(job: jobslib.Job):
            job.step(0.1, f"transkrypcja {key}")
            result = projects.transcribe_asset(pid, key)
            job.step(1.0, f"gotowe: {result['segments']} segmentów")
            return result

        info["job"] = QUEUE.submit("transcribe", work, slot=f"{pid}:transcribe:{key}").id
    return info


@app.post("/api/projects/{pid}/transcribe/{key}")
def transcribe(pid: str, key: str, language: str = Body("pl", embed=True)):
    def work(job: jobslib.Job):
        job.step(0.1, f"transkrypcja {key}")
        return projects.transcribe_asset(pid, key, language=language)

    return {"job": QUEUE.submit("transcribe", work, slot=f"{pid}:transcribe:{key}").id}


@app.get("/api/projects/{pid}/history")
def get_history(pid: str):
    try:
        return projects.history(pid)
    except Exception as exc:
        raise _fail(exc)


@app.post("/api/projects/{pid}/restore")
def restore(pid: str, file: str = Body(..., embed=True)):
    try:
        film = projects.restore(pid, file)
    except Exception as exc:
        raise _fail(exc)
    return json.loads(film.model_dump_json())


# ------------------------------------------------------------------ render
@app.post("/api/projects/{pid}/render")
def start_render(pid: str, quality: str = Body("proxy", embed=True),
                 scene: str | None = Body(None, embed=True)):
    if quality not in render.QUALITY:
        raise HTTPException(400, f"Nieznana jakość: {quality}")

    def work(job: jobslib.Job):
        renderer = _renderer(pid)
        resolved = renderer.resolved(refresh=True)
        if scene:
            entry = resolved.scene(scene)
            setattr(job, "_expected", entry.duration)
            job.step(0.1, f"scena {scene}")
            path = renderer.render_scene(renderer.film.scene(scene), entry.duration, quality)
            return {"video": f"/work/{projects.slug(pid)}/cache/{path.name}", "scene": scene}
        setattr(job, "_expected", resolved.total)
        result = renderer.render_film(quality=quality,
                                      on_progress=lambda p, m: job.step(p, m))
        video = Path(result["video"])
        return {"video": f"/out/{video.name}", "total": round(result["total"], 2),
                "cache_hits": result["cache_hits"], "cache_misses": result["cache_misses"]}

    slot = f"{pid}:render:{scene or 'all'}:{quality}"
    return {"job": QUEUE.submit("render", work, slot=slot).id}


@app.get("/api/projects/{pid}/frame")
def frame(pid: str, t: float = Query(0.0), quality: str = Query("final")):
    try:
        renderer = _renderer(pid)
        path = renderer.render_frame(t, quality=quality)
    except Exception as exc:
        raise _fail(exc)
    return FileResponse(path, media_type="image/png",
                        headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ lektor
@app.post("/api/projects/{pid}/tts")
def make_tts(pid: str, ids: list[str] | None = Body(None, embed=True),
             regenerate: bool = Body(False, embed=True)):
    def work(job: jobslib.Job):
        film = projects.load(pid)
        work_dir = projects.work_dir(pid)
        job.step(0.1, "synteza lektora")
        try:
            files = speech.ensure_lines(film, work_dir, only=ids, regenerate=regenerate)
        except speech.SpeechUnavailable as exc:
            raise RuntimeError(str(exc))
        job.step(0.9, f"gotowe {len(files)} linii")
        return {"lines": {k: round(speech.ffmpeg.duration(v), 2) for k, v in files.items()}}

    return {"job": QUEUE.submit("tts", work, slot=f"{pid}:tts").id}


@app.get("/api/voices")
def voices():
    try:
        from videomat.elevenlabs_client import list_voices
        return list_voices()
    except Exception as exc:
        raise _fail(exc)


# ------------------------------------------------------------------ prompt
@app.post("/api/projects/{pid}/prompt")
def prompt(pid: str, instruction: str = Body(..., embed=True)):
    def work(job: jobslib.Job):
        from videomat import agent
        job.step(0.2, "pytam model")
        film = projects.load(pid)
        overview = projects.assets_overview(pid)
        plan = agent.propose(film, overview, instruction)
        job.step(0.8, "sprawdzam plan")
        updated, changes = agent.apply_plan(film, plan)
        token = uuid.uuid4().hex[:8]
        PROPOSALS[token] = {"pid": pid, "film": json.loads(updated.model_dump_json())}
        return {"proposal": token, "changes": changes, "notes": plan.notes,
                "film": PROPOSALS[token]["film"]}

    return {"job": QUEUE.submit("prompt", work, slot=f"{pid}:prompt").id}


@app.post("/api/projects/{pid}/apply")
def apply_proposal(pid: str, proposal: str = Body(..., embed=True)):
    entry = PROPOSALS.get(proposal)
    if not entry or entry["pid"] != pid:
        raise HTTPException(404, "Ta propozycja wygasła.")
    try:
        film = Film.model_validate(entry["film"])
        projects.save(pid, film, note="prompt")
    except Exception as exc:
        raise _fail(exc)
    return {"ok": True}


# ------------------------------------------------------------------ stenogram
@app.post("/api/stenogram")
def start_stenogram(source: str = Body(..., embed=True), title: str = Body("Stenogram", embed=True),
                    model: str = Body("large-v3", embed=True), language: str = Body("pl", embed=True),
                    speakers: int | None = Body(None, embed=True),
                    diarize: bool = Body(True, embed=True),
                    section: list[float] | None = Body(None, embed=True)):
    from videomat.stenogram import Options, run

    def work(job: jobslib.Job):
        options = Options(title=title, model=model, language=language, speakers=speakers,
                          diarize=diarize,
                          section=(section[0], section[1]) if section and len(section) == 2 else None)
        return run(source, options, on_progress=lambda p, m: job.step(p, m))

    return {"job": QUEUE.submit("stenogram", work, slot="stenogram").id}


@app.get("/api/audio-devices")
def audio_devices():
    try:
        from videomat.live import list_devices
        return list_devices()
    except Exception as exc:
        raise _fail(exc)


LIVE: dict = {"session": None}


@app.post("/api/live/start")
def live_start(source: str = Body("mic", embed=True), device: int | None = Body(None, embed=True),
               model: str = Body("small", embed=True), language: str = Body("pl", embed=True)):
    from videomat.live import LiveSession

    if LIVE["session"] is not None:
        raise HTTPException(409, "Sesja na żywo już trwa.")
    session = LiveSession(on_update=lambda event: QUEUE.publish({"type": "live", **event}),
                          source=source, device=device, model=model, language=language)
    try:
        session.start()
    except Exception as exc:
        raise _fail(exc)
    LIVE["session"] = session
    return {"started": True, "source": source, "work": str(session.work)}


@app.post("/api/live/stop")
def live_stop(finalize: bool = Body(False, embed=True), title: str = Body("Stenogram na żywo", embed=True)):
    session = LIVE.get("session")
    if session is None:
        raise HTTPException(404, "Nie ma trwającej sesji.")
    utterances = session.stop()
    LIVE["session"] = None
    result = {"utterances": utterances, "files": session.save()}
    if finalize and utterances:
        def work(job: jobslib.Job):
            job.step(0.1, "pełny stenogram z rozpoznaniem mówców")
            return session.finalize(title=title)

        result["job"] = QUEUE.submit("stenogram", work, slot="stenogram").id
    return result


@app.get("/api/live/status")
def live_status():
    session = LIVE.get("session")
    if session is None:
        return {"running": False}
    return {"running": True, "source": session.source, "error": session.error,
            "utterances": [u.as_dict() for u in session.utterances]}


# ------------------------------------------------------------------ zadania
@app.get("/api/jobs")
def list_jobs():
    return QUEUE.listing()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = QUEUE.get(job_id)
    if not job:
        raise HTTPException(404, "Nie ma takiego zadania.")
    return job.public()


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    return {"cancelled": QUEUE.cancel(job_id)}


@app.get("/api/events")
def events():
    def stream():
        for event in QUEUE.stream():
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ dawny panel (zachowany)
JOBS: dict[str, dict] = {}
_lock = threading.Lock()
UPLOADS = config.WORK / "uploads"
UPLOADS.mkdir(exist_ok=True)


def _set(job_id: str, **kw):
    with _lock:
        JOBS[job_id].update(kw)


def _run(job_id: str, fn, *args, **kwargs):
    _set(job_id, status="running")
    try:
        r = fn(*args, **kwargs)
        r = {k: (str(v) if isinstance(v, Path) else [str(x) for x in v] if isinstance(v, list) else v)
             for k, v in r.items()} if isinstance(r, dict) else {"result": str(r)}
        _set(job_id, status="done", result=r)
    except BaseException as e:
        _set(job_id, status="error", error=f"{e}", trace=traceback.format_exc()[-2000:])


def _save_upload(f: UploadFile) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in (f.filename or "plik"))
    p = UPLOADS / f"{uuid.uuid4().hex[:8]}_{safe}"
    p.write_bytes(f.file.read())
    return p


@app.get("/classic", response_class=HTMLResponse)
def classic():
    return LEGACY.read_text(encoding="utf-8")


@app.post("/api/captions")
def api_captions(bg: BackgroundTasks, video: UploadFile = File(...), fit: str = Form("none"),
                 theme: str = Form("hitech"), anim: str = Form("highlight"), lang: str = Form("pl")):
    from videomat.captions import run_captions
    p = _save_upload(video)
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"type": "captions", "status": "queued", "input": p.name}
    bg.add_task(_run, job_id, run_captions, p, fit=fit, theme=theme, animation=anim, language=lang)
    return {"job": job_id}


@app.post("/api/roughcut")
def api_roughcut(bg: BackgroundTasks, video: UploadFile = File(...), silence: float = Form(-30.0),
                 min_sil: float = Form(0.4)):
    from videomat.roughcut import roughcut
    p = _save_upload(video)
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"type": "roughcut", "status": "queued", "input": p.name}
    bg.add_task(_run, job_id, roughcut, p, silence_db=silence, min_silence=min_sil)
    return {"job": job_id}


@app.get("/api/outputs")
def outputs():
    files = sorted(config.OUT.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": str(p.relative_to(config.OUT)).replace("\\", "/"), "size": p.stat().st_size}
            for p in files if p.is_file()][:100]


# ------------------------------------------------------------------ frontend (montowany na końcu)
if STATIC.exists():
    app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="studio")
else:
    @app.get("/", response_class=HTMLResponse)
    def missing_build():
        return ("<h1 style='font:16px system-ui;padding:40px'>Frontend studia nie jest zbudowany."
                "<br>W katalogu <code>studio/</code> uruchom <code>npm install</code> i "
                "<code>npm run build</code>, albo otwórz <a href='/classic'>stary panel</a>.</h1>")
