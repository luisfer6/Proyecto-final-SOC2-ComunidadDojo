from contextlib import asynccontextmanager
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analysis import analyze
from .assistant import assist, ollama_status
from .ingest import MAX_UPLOAD, read_workbook
from .report import make_pdf

ROOT = Path(__file__).resolve().parent.parent
TTL = 3600
MAX_SESSIONS = 4
STORE = {}
LOCK = threading.Lock()
ANALYSIS_LOCK = asyncio.Lock()


def expire():
    with LOCK:
        for token in list(STORE):
            if time.monotonic() - STORE[token]["created"] > TTL:
                del STORE[token]


@asynccontextmanager
async def lifespan(app):
    async def cleanup():
        while True:
            await asyncio.sleep(60)
            expire()
    task = asyncio.create_task(cleanup())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    with LOCK:
        STORE.clear()


app = FastAPI(title="SOC Lens", version="1.0.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])


class UploadTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        total = 0

        async def limited():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > MAX_UPLOAD + 1024 * 1024:
                raise UploadTooLarge()
            return message
        try:
            await self.app(scope, limited, send)
        except UploadTooLarge:
            await JSONResponse({"detail": "Carga demasiado grande; máximo 10 MB."}, status_code=413)(scope, receive, send)


app.add_middleware(BodyLimitMiddleware)


@app.middleware("http")
async def local_security(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if origin and origin != expected:
            return JSONResponse({"detail": "Origen no autorizado."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    return response


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "ai": "Isolation Forest local", **(await ollama_status())}


@app.post("/api/analyze")
async def upload(file: UploadFile = File(...), timezone_offset: int | None = Form(None)):
    try:
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "Máximo 10 MB por archivo.")
        # No client path is used as a filesystem path.
        filename = (file.filename or "export.xlsx").replace("\\", "/").split("/")[-1][:200]
        async with ANALYSIS_LOCK:
            expire()
            with LOCK:
                if len(STORE) >= MAX_SESSIONS:
                    raise HTTPException(429, "Hay 4 análisis en memoria. Elimina un caso o espera su vencimiento (1 hora).")
            try:
                events, metadata = await run_in_threadpool(read_workbook, data, filename, timezone_offset)
                result = await run_in_threadpool(analyze, events, metadata)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            except Exception as exc:
                # Invalid XML/OOXML should not leak a traceback or filesystem paths.
                raise HTTPException(422, "No fue posible procesar el libro. Revisa su estructura y vuelve a exportarlo como XLSX con valores.") from exc
            token = str(uuid4())
            result["id"] = token
            with LOCK:
                STORE[token] = {"created": time.monotonic(), "result": result}
        return result
    finally:
        await file.close()


def get_case(token):
    expire()
    with LOCK:
        item = STORE.get(token)
        if not item:
            raise HTTPException(404, "El caso no existe o venció. Carga de nuevo el Excel.")
        return item["result"]


@app.get("/api/cases/{token}/report.pdf")
def pdf(token: str):
    result = deepcopy(get_case(token))
    return Response(make_pdf(result), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="SOC-Lens-informe.pdf"'})


@app.get("/api/cases/{token}/evidence.json")
def evidence(token: str):
    return Response(json.dumps(get_case(token), ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="SOC-Lens-evidencias.json"'})


@app.post("/api/cases/{token}/assistant")
async def assistant(token: str):
    result = deepcopy(get_case(token))
    try:
        narrative = await assist(result)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Ollama local no respondió con una selección válida. El informe verificable sigue disponible.") from exc
    with LOCK:
        if token not in STORE:
            raise HTTPException(404, "El caso venció o fue eliminado.")
        STORE[token]["result"]["narrative"] = narrative
    return narrative


@app.delete("/api/cases/{token}")
def delete_case(token: str):
    with LOCK:
        STORE.pop(token, None)
    return {"deleted": True}


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
