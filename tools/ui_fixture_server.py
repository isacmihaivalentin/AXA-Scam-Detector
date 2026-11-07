"""TEST-ONLY UI fixture server. Never deploy.

Serves the real index.html / assets and runs the REAL analysis pipeline (URL forensics,
catalog, rules, decision, presentation). Only the Gemini call is replaced by deterministic
MOCK readings keyed by message text, so every UI state can be rendered without a key.
Failure modes are switched with POST /__fixture {"mode": ...}:

  normal | ai_timeout | ai_not_configured | server_error | slow | ocr_fail | ocr_empty

Run:  python -m uvicorn tools.ui_fixture_server:app --port 8765
(FastAPI itself is not required; Starlette ships with FastAPI.)
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation" / "audit"))
os.environ.setdefault("AXA_SQLITE_PATH", str(Path(tempfile.mkdtemp()) / "fixture.sqlite3"))
os.environ.pop("AXA_WEB_RISK_API_KEY", None)

from starlette.applications import Starlette  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import FileResponse, HTMLResponse, JSONResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402

import database  # noqa: E402
import engine  # noqa: E402
import semantic_gemini  # noqa: E402
from mock_interpretations import KEEP, M, MOCKS, R  # noqa: E402

database.initialize_sqlite(os.environ["AXA_SQLITE_PATH"])
SEVEN = {c["id"]: c["text"] for c in json.loads((ROOT / "evaluation/audit/seven_cases.json").read_text(encoding="utf-8"))}

LONG_URL = ("https://www.bcr.ro@secure-george-verificare.example/autentificare/clienti/persoane-fizice/"
            "validare-identitate-card?session=8f2a1c9e7b6d5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d&ref=sms&utm=campanie-noiembrie")

FIXTURES = {
    # text -> mock reading (MOCK, not live Gemini)
    SEVEN["D-cargus-pickup"]: MOCKS["D-cargus-pickup"],
    SEVEN["E-orange-promo-2"]: MOCKS["E-orange-promo-2"],
    SEVEN["G-tursib-portal"]: MOCKS["G-tursib-portal"],
    SEVEN["A-visa-gpay"]: MOCKS["A-visa-gpay"],
    "DPD: Livrarea a esuat. Sunati urgent la 0900 123 456 (tarif special) in 2 ore, altfel coletul va fi distrus.":
        MOCKS["N10"],
    ("ALERTĂ BCR: Stimate client, contul dvs. a fost suspendat în urma unei tranzacții suspecte. Pentru deblocare "
     f"imediată validați identitatea și introduceți datele cardului aici: {LONG_URL} Nu spuneți nimănui despre această verificare."):
        M("likely_scam", "card_data_theft", sender="BCR", stype="bank", reqs=[
            R("share_card_data", "datele cardului", "secret_credential", "introduceți datele cardului aici", dest=LONG_URL)],
            thr=[("account_block", "contul dvs. a fost suspendat")],
            tac=[("urgency", "Pentru deblocare imediată"), ("secrecy", "Nu spuneți nimănui despre această verificare")]),
    "Salut mami, mi-am schimbat numărul, telefonul meu s-a stricat. Te rog urgent să faci un transfer de 2.300 lei în contul pe care ți-l dau acum. Nu spune nimănui.":
        M("likely_scam", "family_impersonation", stype="family_or_friend", reqs=[
            R("transfer_money", "2.300 lei", "financial_asset", "să faci un transfer de 2.300 lei în contul pe care ți-l dau acum")],
            tac=[("family_impersonation", "mi-am schimbat numărul, telefonul meu s-a stricat"), ("secrecy", "Nu spune nimănui"),
                 ("urgency", "Te rog urgent")]),
    "Nu trimite parola nimanui, nici celor care pretind ca sunt de la banca.":
        M("likely_scam", "credential_phishing", reqs=[R("share_password", "parola", "secret_credential", "trimite parola nimanui")]),
    "Atenție: angajații băncii nu vă vor cere niciodată codul primit prin SMS, PIN-ul sau parola. Dacă cineva vi le cere, închideți și sunați la numărul de pe spatele cardului.":
        M("protective_or_educational", stype="bank", reqs=[
            R("share_otp_or_code", "coduri, PIN, parolă", "secret_credential", "nu vă vor cere niciodată codul primit prin SMS",
              stance="discouraged", handover=KEEP)],
            prot=[("security_warning", "Dacă cineva vi le cere, închideți și sunați la numărul de pe spatele cardului")]),
    "Verifică https://[bad și spune-mi dacă merge.":
        M("insufficient_information", reqs=[R("click_link", "link", "low", "Verifică https://[bad")]),
}
OCR_TEXT = SEVEN["D-cargus-pickup"]
STATE = {"mode": "normal"}


def interpret(text, key):
    mode = STATE["mode"]
    if mode == "ai_not_configured":
        return semantic_gemini.interpret(text, "")
    if mode == "ai_timeout":
        return None, {"provider": "gemini", "model": "gemini-3.5-flash-lite", "status": "failed", "failure": "timeout",
                      "truncated": False, "elapsed_ms": 20000.0}
    reading = FIXTURES.get(text)
    if reading is None:  # unknown text: honest "not configured" fallback, never an invented reading
        return semantic_gemini.interpret(text, "")
    raw = json.dumps(reading, ensure_ascii=False)
    return semantic_gemini.interpret(text, key, generate=lambda *a, **k: raw)


async def home(request):
    return HTMLResponse((ROOT / "index.html").read_text(encoding="utf-8"))


async def asset(request):
    name = request.path_params["name"]
    allowed = {"axa.css": "text/css; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
               "education.css": "text/css; charset=utf-8", "education.js": "text/javascript; charset=utf-8"}
    if name not in allowed:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return FileResponse(ROOT / "assets" / name, media_type=allowed[name])


async def font(request):
    fonts = {"bricolage-bold.woff": "font/woff", "worksans-regular.woff": "font/woff", "worksans-bold.woff": "font/woff"}
    name = request.path_params["name"]
    if name not in fonts:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return FileResponse(ROOT / "assets" / "fonts" / name, media_type=fonts[name])


async def status(request):
    on = STATE["mode"] != "ai_not_configured"
    return JSONResponse({"semantic_ai": "configured" if on else "not_configured", "model": "gemini-3.5-flash-lite (MOCK)" if on else None,
                         "ocr": "configured" if on else "not_configured", "reputation": "not_configured", "local_semantic_model": False})


async def analyze(request: Request):
    if STATE["mode"] == "server_error":
        return JSONResponse({"detail": "Serverul nu a putut finaliza analiza."}, status_code=500)
    if STATE["mode"] == "slow":
        await asyncio.sleep(2.5)
    body = await request.json()
    text = body.get("text", "")
    if not text.strip():
        return JSONResponse({"detail": "Textul mesajului nu poate fi gol."}, status_code=400)
    return JSONResponse(await run_in_threadpool(engine.analyze_text, text, "mock", ocr_reviewed=body.get("ocr_reviewed"),
                                                interpret=interpret))


async def analyze_image(request: Request):
    form = await request.form()
    upload = form.get("file")
    await upload.read() if upload else b""
    if STATE["mode"] == "ai_not_configured":
        return JSONResponse({"detail": "Citirea capturilor necesită Gemini configurat pe server. Lipește textul manual."}, status_code=503)
    if STATE["mode"] == "ocr_fail":
        return JSONResponse({"detail": "Nu am putut citi captura acum. Încearcă din nou sau lipește textul."}, status_code=502)
    if STATE["mode"] == "ocr_empty":
        return JSONResponse({"detail": "Nu am găsit text lizibil în imagine."}, status_code=422)
    return JSONResponse(await run_in_threadpool(engine.analyze_text, OCR_TEXT, "mock", from_ocr=True, interpret=interpret))


async def education_page(request):  # AXA for Education (static)
    return HTMLResponse((ROOT / "education.html").read_text(encoding="utf-8"))


async def chat_page(request):  # AXA în chat concept page (additive)
    return HTMLResponse((ROOT / "chat.html").read_text(encoding="utf-8"))


async def chat_asset(request):
    allowed = {"chat.css": "text/css; charset=utf-8", "chat.js": "text/javascript; charset=utf-8"}
    name = request.path_params["name"]
    if name not in allowed:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return FileResponse(ROOT / "assets" / name, media_type=allowed[name])


async def fixture(request: Request):
    STATE["mode"] = (await request.json()).get("mode", "normal")
    return JSONResponse(STATE)


async def fixtures_list(request):
    return JSONResponse({"texts": list(FIXTURES), "ocr_text": OCR_TEXT})


app = Starlette(routes=[
    Route("/", home), Route("/assets/fonts/{name}", font), Route("/assets/{name}", asset), Route("/api/status", status),
    Route("/api/analyze", analyze, methods=["POST"]), Route("/api/analyze-image", analyze_image, methods=["POST"]),
    Route("/__fixture", fixture, methods=["POST"]), Route("/__fixtures", fixtures_list),
    Route("/chat", chat_page), Route("/education", education_page), Route("/chat-assets/{name}", chat_asset),
])
