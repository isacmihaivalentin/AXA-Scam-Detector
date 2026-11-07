"""FastAPI routes. The analysis pipeline lives in engine.py."""
import logging
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import engine
import gemini_client

app = FastAPI(title="AXA Scam Detector API", version="2.1.1")
logger = logging.getLogger("axa")
ROOT = Path(__file__).resolve().parent
MAX_TEXT = engine.MAX_TEXT
MAX_IMAGE_BYTES = 5 * 1024 * 1024
REQUEST_LIMITS = {"/api/analyze": 256 * 1024, "/api/analyze-image": MAX_IMAGE_BYTES + 64 * 1024}
ASSETS = {"axa.css": "text/css; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
          # AXA for Education landing page (static, no API calls)
          "education.css": "text/css; charset=utf-8", "education.js": "text/javascript; charset=utf-8"}
# Self-hosted OFL fonts (licences alongside in assets/fonts). Fixed allow-list, no path traversal.
FONTS = {"bricolage-bold.woff": "font/woff", "worksans-regular.woff": "font/woff", "worksans-bold.woff": "font/woff"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "font-src 'self'; img-src 'self' data: blob:; connect-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
}


class AnalyzeRequest(BaseModel):
    text: str = Field(max_length=MAX_TEXT)
    ocr_reviewed: bool | None = None


class LimitRequestBody:
    """Reject oversized bodies before parsing; add security headers to every response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend((k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items())
                message = {**message, "headers": headers}
            await send(message)

        limit = REQUEST_LIMITS.get(scope.get("path")) if scope.get("method") == "POST" else None
        if limit is None:
            await self.app(scope, receive, send_with_headers)
            return
        detail = "Corpul cererii depășește limita acceptată."
        length = dict(scope["headers"]).get(b"content-length", b"").lstrip(b"0") or b"0"
        if length.isdigit() and (len(length) > 9 or int(length) > limit):
            await JSONResponse({"detail": detail}, status_code=413)(scope, receive, send_with_headers)
            return
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                raise HTTPException(status_code=413, detail=detail)
            return message

        await self.app(scope, bounded_receive, send_with_headers)


app.add_middleware(LimitRequestBody)


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return (ROOT / "index.html").read_text(encoding="utf-8")


@app.get("/assets/{name}", include_in_schema=False)
def serve_asset(name: str):
    if name not in ASSETS:  # fixed allow-list, no path traversal
        raise HTTPException(status_code=404)
    return FileResponse(ROOT / "assets" / name, media_type=ASSETS[name])


@app.get("/assets/fonts/{name}", include_in_schema=False)
def serve_font(name: str):
    if name not in FONTS:
        raise HTTPException(status_code=404)
    return FileResponse(ROOT / "assets" / "fonts" / name, media_type=FONTS[name],
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/education", response_class=HTMLResponse, include_in_schema=False)
async def serve_education():
    """AXA for Education: a static "coming soon" preview page. It calls no API."""
    return (ROOT / "education.html").read_text(encoding="utf-8")


# --- AXA în chat: messaging-style concept page (additive; the main interface and routes are unchanged).
CHAT_ASSETS = {"chat.css": "text/css; charset=utf-8", "chat.js": "text/javascript; charset=utf-8"}


@app.get("/chat", response_class=HTMLResponse, include_in_schema=False)
async def serve_chat():
    return (ROOT / "chat.html").read_text(encoding="utf-8")


@app.get("/chat-assets/{name}", include_in_schema=False)
def serve_chat_asset(name: str):
    if name not in CHAT_ASSETS:  # fixed allow-list, no path traversal
        raise HTTPException(status_code=404)
    return FileResponse(ROOT / "assets" / name, media_type=CHAT_ASSETS[name])


@app.get("/api/status")
def status():
    """What the server can do right now (no secrets)."""
    key = engine.gemini_key()
    return {"semantic_ai": "configured" if key else "not_configured",
            "model": gemini_client.model_id() if key else None,
            "ocr": "configured" if key else "not_configured",
            "reputation": "configured" if os.environ.get("AXA_WEB_RISK_API_KEY", "").strip() else "not_configured",
            "local_semantic_model": os.environ.get("AXA_LOCAL_MODEL", "0").lower() in {"1", "on", "true"}}


@app.post("/api/analyze")
def analyze_message(req: AnalyzeRequest):
    text = req.text
    if not text.strip():
        raise HTTPException(status_code=400, detail="Textul mesajului nu poate fi gol.")
    try:
        text.encode("utf-8")
    except UnicodeError:
        raise HTTPException(status_code=422, detail="Textul conține caractere Unicode invalide.")
    return engine.analyze_text(text, ocr_reviewed=req.ocr_reviewed)


def valid_image_signature(content, mime):
    if mime == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    return content.startswith(b"RIFF") and content[8:12] == b"WEBP"


@app.post("/api/analyze-image")
async def analyze_screenshot(file: UploadFile = File(...)):
    api_key = engine.gemini_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="Citirea capturilor necesită Gemini configurat pe server. Lipește textul manual.")
    mime = file.content_type
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="Format acceptat: PNG, JPEG sau WebP.")
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Imagine prea mare (maxim 5 MB).")
    if not content:
        raise HTTPException(status_code=400, detail="Imaginea este goală.")
    if not valid_image_signature(content, mime):
        raise HTTPException(status_code=415, detail="Conținutul nu corespunde formatului de imagine declarat.")
    try:
        text = await run_in_threadpool(engine.ocr_image, content, mime, api_key)
    except gemini_client.ProviderError as error:
        logger.warning("Gemini OCR unavailable (%s)", error.kind)
        raise HTTPException(status_code=502, detail="Nu am putut citi captura acum. Încearcă din nou sau lipește textul.")
    if not text.strip():
        raise HTTPException(status_code=422, detail="Nu am găsit text lizibil în imagine.")
    return await run_in_threadpool(lambda: engine.analyze_text(text, api_key, from_ocr=True))
