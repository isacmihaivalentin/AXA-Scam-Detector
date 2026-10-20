import os
import re
import ssl
import socket
import json
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import List, Optional, Dict, Any

import requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    import whois
except ImportError:
    whois = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

app = FastAPI(title="AXA Scam Detector API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Domenii oficiale din Romania frecvent clonate in atacuri de phishing
OFFICIAL_DOMAINS = [
    "bcr.ro", "george.bcr.ro", "bancatransilvania.ro", "ing.ro", "homebank.ro",
    "raiffeisen.ro", "cec.ro", "unicredit.ro", "revolut.com", "salt.bank",
    "sameday.ro", "fancourier.ro", "cargus.ro", "posta-romana.ro", "dhl.ro",
    "olx.ro", "emag.ro", "anaf.ro", "ghiseul.ro", "enel.ro", "ppcenergy.ro",
    "hidroelectrica.ro", "electricafurnizare.ro", "eon.ro", "digi.ro", "orange.ro", "vodafone.ro"
]

SUSPICIOUS_TLDS = {
    ".top", ".xyz", ".click", ".link", ".work", ".buzz", ".loan", ".vip",
    ".shop", ".online", ".live", ".site", ".icu", ".cc", ".tk", ".ml", ".ga", ".cf"
}


class AnalyzeRequest(BaseModel):
    text: str
    api_key: Optional[str] = None


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def normalize_leetspeak(domain_str: str) -> str:
    replacements = {'0': 'o', '1': 'l', '3': 'e', '4': 'a', '5': 's', '8': 'b', '@': 'a'}
    for k, v in replacements.items():
        domain_str = domain_str.replace(k, v)
    return domain_str


def detect_typosquatting(domain: str) -> Dict[str, Any]:
    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]

    if domain in OFFICIAL_DOMAINS:
        return {"is_official": True, "is_typosquatting": False, "target": domain, "similarity": 100}

    domain_base = domain.split('.')[0]
    norm_base = normalize_leetspeak(domain_base)

    best_match = None
    highest_sim = 0.0
    reason = ""

    for official in OFFICIAL_DOMAINS:
        off_base = official.split('.')[0]

        # 1. Verificare daca numele brandului oficial este inclus intr-un domeniu compus (ex: bcr-online-ro.top, sameday-livrare.com)
        if len(off_base) >= 3 and off_base in norm_base and domain != official:
            return {
                "is_official": False,
                "is_typosquatting": True,
                "target": official,
                "similarity": 92,
                "reason": f"Domeniul contine numele brandului '{off_base}' combinat cu cuvinte aditionale sau alt TLD."
            }

        # 2. Distanta Levenshtein pe numele de baza (ex: o1x.ro vs olx.ro, samday.ro vs sameday.ro)
        dist = levenshtein_distance(norm_base, off_base)
        max_len = max(len(norm_base), len(off_base))
        sim = round((1 - dist / max_len) * 100) if max_len > 0 else 0

        if sim > highest_sim:
            highest_sim = sim
            best_match = official

    if highest_sim >= 70 and best_match:
        return {
            "is_official": False,
            "is_typosquatting": True,
            "target": best_match,
            "similarity": highest_sim,
            "reason": f"Similaritate ridicata ({highest_sim}%) cu domeniul oficial '{best_match}' (posibil Typosquatting)."
        }

    return {"is_official": False, "is_typosquatting": False, "target": None, "similarity": highest_sim}


def extract_urls(text: str) -> List[str]:
    pattern = r'(?:https?://|www\.)[^\s<>"]+|(?<![a-zA-Z0-9@])(?:[a-zA-Z0-9-]+\.)+(?:ro|com|net|org|info|top|xyz|click|link|online|site|shop|live|cc|io|ly|gl|me)(?:/[^\s<>"]*)?'
    matches = re.findall(pattern, text, re.IGNORECASE)
    cleaned = []
    for m in matches:
        m = m.rstrip('.,;:!?)')
        if not m.startswith(('http://', 'https://')):
            m = 'http://' + m
        cleaned.append(m)
    return list( dict.fromkeys(cleaned) )


def analyze_single_url(url: str) -> Dict[str, Any]:
    result = {
        "original_url": url,
        "final_url": url,
        "domain": "",
        "redirect_count": 0,
        "is_shortened": False,
        "suspicious_tld": False,
        "tld": "",
        "typosquatting": {},
        "domain_age_days": None,
        "has_https": url.startswith("https://"),
        "has_login_or_card_form": False,
        "page_title": None,
        "risk_points": 0,
        "flags": []
    }

    shorteners = {"bit.ly", "tinyurl.com", "t.co", "rb.gy", "is.gd", "cutt.ly", "shorturl.at", "tiny.cc"}
    parsed_init = urlparse(url)
    init_domain = parsed_init.netloc.lower()
    if init_domain.startswith("www."):
        init_domain = init_domain[4:]

    if init_domain in shorteners:
        result["is_shortened"] = True
        result["risk_points"] += 20
        result["flags"].append(f"Link scurtat ({init_domain}) folosit pentru a ascunde destinatia reala.")

    # Incercam rezolvarea redirecturilor si inspectia HTML intr-un mod sigur
    try:
        resp = requests.get(
            url,
            timeout=3.5,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (SecurityAudit-ScamAutopsy/1.0)"}
        )
        result["final_url"] = resp.url
        result["redirect_count"] = len(resp.history)
        result["has_https"] = resp.url.startswith("https://")

        html_lower = resp.text[:15000].lower()
        title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text[:10000], re.IGNORECASE | re.DOTALL)
        if title_match:
            result["page_title"] = title_match.group(1).strip()[:80]

        if 'type="password"' in html_lower or "type='password'" in html_lower or 'cvv' in html_lower or 'cardnumber' in html_lower:
            result["has_login_or_card_form"] = True
    except Exception:
        pass

    parsed_final = urlparse(result["final_url"])
    final_domain = parsed_final.netloc.lower().split(':')[0]
    if final_domain.startswith("www."):
        final_domain = final_domain[4:]
    result["domain"] = final_domain

    # Verificare TLD
    for tld in SUSPICIOUS_TLDS:
        if final_domain.endswith(tld):
            result["suspicious_tld"] = True
            result["tld"] = tld
            result["risk_points"] += 25
            result["flags"].append(f"Extensie de domeniu cu risc ridicat ({tld}), frecvent utilizata in campanii de phishing.")
            break

    # Verificare Typosquatting
    typo = detect_typosquatting(final_domain)
    result["typosquatting"] = typo
    if typo.get("is_typosquatting"):
        result["risk_points"] += 45
        result["flags"].append(typo.get("reason", "Domeniu clonat / Typosquatting detectat."))
    elif typo.get("is_official"):
        result["flags"].append(f"Domeniu oficial verificat ({final_domain}).")

    if result["has_login_or_card_form"] and not typo.get("is_official"):
        result["risk_points"] += 30
        result["flags"].append("Pagina contine formulare care solicita parola sau datele cardului bancar.")

    if not result["has_https"] and not typo.get("is_official"):
        result["risk_points"] += 15
        result["flags"].append("Conexiune nesecurizata (fara HTTPS/SSL).")

    # Verificare WHOIS (vechime domeniu)
    if whois and final_domain and not typo.get("is_official"):
        try:
            w = whois.whois(final_domain)
            creation_date = w.creation_date
            if isinstance(creation_date, list):
                creation_date = creation_date[0]
            if isinstance(creation_date, datetime):
                if creation_date.tzinfo is None:
                    creation_date = creation_date.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - creation_date).days
                result["domain_age_days"] = max(0, age_days)
                if age_days < 30:
                    result["risk_points"] += 35
                    result["flags"].append(f"Domeniu inregistrat foarte recent ({age_days} zile in urma) - indicator clasic de frauda.")
        except Exception:
            pass

    result["risk_points"] = min(100, result["risk_points"])
    return result


def heuristic_text_analysis(text: str, url_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    highlights = []
    tactics = set()
    score = 0

    rules = [
        (r"(?:in\s+maxim\s+\d+\s*(?:ore|zile)|24\s*h|24\s+de\s+ore|urgent|imediat|expira\s+astazi|ultima\s+notificare|suspendat\s+temporar|blocat)",
         "Urgenta Artificiala",
         "Atacatorii creeaza presiune de timp pentru a te determina sa actionezi impulsiv, fara sa verifici sursa.",
         25),
        (r"(?:coletul\s+(?:tau|dvs)|livrare\s+esuata|adresa\s+incompleta|taxa\s+vamala|taxa\s+de\s+reexpediere|sameday|fan\s*courier|posta\s+romana|cargus)",
         "Pretext Livrare / Curier",
         "Folosirea unui colet fals este cea mai raspandita metoda de phishing prin SMS (Smishing) in Romania.",
         20),
        (r"(?:bcr|banca\s+transilvania|ing|raiffeisen|revolut|anaf|contul\s+(?:tau|dvs)\s+a\s+fost|actualizati\s+datele|validare\s+cont| Reactivare)",
         "Impersonare Autoritate / Banca",
         "Mesajul pretinde ca vine de la o institutie financiara sau de stat pentru a castiga increderea victimei.",
         25),
        (r"(?:datele\s+cardului|codul\s+pin|cvv|parola| plateste\s+taxa|achita\s+\d+|formularul\s+de\s+incasare|primesti\s+banii\s+pe\s+card)",
         "Solicitare Date Financiare",
         "Nicio banca sau firma de curierat sau platforma de anunturi (OLX) nu cere datele cardului printr-un link primit pe SMS/WhatsApp pentru a incasa bani.",
         35),
        (r"(?:ai\s+castigat|felicitari|premiu|voucher|investitie\s+garantata|profit\s+zilnic|director\s+de\s+resurse\s+umane|job\s+part-time\s+pe\s+whatsapp)",
         "Recompensa Falsa / Scam Financiar",
         "Promisiunea unui castig rapid sau a unui job usor pe WhatsApp/Telegram este folosita pentru a atrage victima intr-o schema frauduloasa.",
         30)
    ]

    for pattern, category, explanation, pts in rules:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matched_str = match.group(0)
            if not any(h["phrase"].lower() == matched_str.lower() for h in highlights):
                highlights.append({
                    "phrase": matched_str,
                    "category": category,
                    "explanation": explanation
                })
                tactics.add(category)
                score += pts

    max_url_risk = max((u["risk_points"] for u in url_reports), default=0)
    total_score = min(99, max(score, max_url_risk) + (20 if (score > 0 and max_url_risk > 30) else 0))

    if total_score >= 70:
        verdict = "PERICOL CRITIC DE FRAUDA (PHISHING / SCAM)"
        summary = "Acest mesaj prezinta indicatori severi de inginerie sociala si/sau link-uri periculoase care imita institutii oficiale."
        recommendations = [
            "NU da click pe link-ul din mesaj si nu introduce date personale sau bancare.",
            "Daca mesajul pare de la banca sau curier, intra manual in aplicatia oficiala sau pe site-ul oficial tastand adresa direct in browser.",
            "Blocheaza numarul de telefon sau expeditorul si raporteaza mesajul ca Spam/Phishing."
        ]
    elif total_score >= 35:
        verdict = "MESAJ SUSPECT - NECESITA VERIFICARE"
        summary = "Mesajul contine elemente de presiune psihologica sau link-uri care necesita verificare suplimentara inainte de orice actiune."
        recommendations = [
            "Verifica expeditorul pe un canal separat si oficial.",
            "Evita completarea oricaror formulare accesate direct din acest mesaj."
        ]
    else:
        verdict = "RISC SCAZUT (PARE LEGITIM)"
        summary = "Nu au fost detectate tehnici evidente de manipulare sau domenii clonate in acest mesaj."
        recommendations = [
            "Pastreaza totusi vigilenta daca ti se cer ulterior informatii confidantiale."
        ]

    return {
        "risk_score": total_score,
        "verdict": verdict,
        "summary": summary,
        "tactics_detected": list(tactics),
        "highlights": highlights,
        "recommendations": recommendations,
        "engine_used": "Heuristic + OSINT Forensics Engine"
    }


def gemini_ai_analysis(text: str, url_reports: List[Dict[str, Any]], api_key: str) -> Dict[str, Any]:
    client = genai.Client(api_key=api_key)
    prompt = f"""Esti un expert in Cybersecurity si Social Engineering din Romania.
Analizeaza urmatorul mesaj suspect si rapoartele tehnice ale link-urilor extrase din el.

MESAJ UTILIZATOR:
"""{text}"""

RAPOARTE TEHNICE LINK-URI (OSINT & Typosquatting):
{json.dumps(url_reports, ensure_ascii=False)}

Returneaza STRICT un obiect JSON valid cu urmatoarea structura:
{{
  "risk_score": <numar intreg 0-100>,
  "verdict": "<titlu scurt al verdictului in romana>",
  "summary": "<explicatie clara in 1-2 propozitii in romana despre ce incearca sa faca acest mesaj>",
  "tactics_detected": ["<Tactica 1>", "<Tactica 2>"],
  "highlights": [
    {{
      "phrase": "<secventa exacta de cuvinte din mesajul utilizatorului>",
      "category": "<Urgenta Artificiala | Impersonare Autoritate | Amenintare / Frica | Solicitare Date Sensibile | Recompensa Falsa | Link Suspect>",
      "explanation": "<de ce aceasta expresie este o tehnica de manipulare>"
    }}
  ],
  "recommendations": ["<Sfat concret 1>", "<Sfat concret 2>", "<Sfat concret 3>"]
}}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    data = json.loads(response.text)
    data["engine_used"] = "Gemini 2.5 Flash AI + OSINT Forensics Engine"
    return data


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/analyze")
async def analyze_message(req: AnalyzeRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Textul mesajului nu poate fi gol.")

    urls = extract_urls(text)
    url_reports = [analyze_single_url(u) for u in urls]

    api_key = (req.api_key or os.environ.get("GEMINI_API_KEY", "")).strip()

    if api_key and genai is not None:
        try:
            ai_result = gemini_ai_analysis(text, url_reports, api_key)
        except Exception as e:
            ai_result = heuristic_text_analysis(text, url_reports)
            ai_result["engine_used"] += f" (Fallback activat: {str(e)[:60]})"
    else:
        ai_result = heuristic_text_analysis(text, url_reports)

    return {
        "text": text,
        "url_reports": url_reports,
        "analysis": ai_result
    }


@app.post("/api/analyze-image")
async def analyze_screenshot(
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None)
):
    effective_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not effective_key or genai is None:
        raise HTTPException(
            status_code=400,
            detail="Pentru extragerea automata a textului din Screenshot (Vision OCR) introdu o cheie gratuita Gemini API in campul din dreapta sus."
        )

    img_bytes = await file.read()
    client = genai.Client(api_key=effective_key)
    ocr_resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type=file.content_type or "image/png"),
            "Extrage exact tot textul si toate link-urile vizibile in aceasta captura de ecran cu un mesaj/SMS/conversatie. Returneaza doar textul transcris, fara comentarii."
        ]
    )
    extracted_text = (ocr_resp.text or "").strip()
    if not extracted_text:
        raise HTTPException(status_code=400, detail="Nu s-a putut extrage text din imagine.")

    urls = extract_urls(extracted_text)
    url_reports = [analyze_single_url(u) for u in urls]
    ai_result = gemini_ai_analysis(extracted_text, url_reports, effective_key)
    ai_result["engine_used"] = "Gemini Vision OCR + OSINT Forensics Engine"

    return {
        "text": extracted_text,
        "url_reports": url_reports,
        "analysis": ai_result
    }
