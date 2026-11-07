"""Faithful MOCK Gemini interpretations for policy evaluation (not live model output).

Written for the audit BEFORE any v2.1 policy code existed, and frozen with it
(evaluation/audit/mocks.sha256). Each entry is what a competent model is expected to
return for the message. They use the proposed v2.1 fields (`handover`, `destination`,
action `sign_in`/`change_settings`, stance `provided_to_recipient`); the v2.0 validator
drops unknown fields and maps unknown enum values with its own fallbacks, so the SAME
mock can be scored by both policies without hand-made adapters.

Error modes observed or plausible in live use are applied by `perturb()`, so the
policies are also compared when the model is wrong in realistic ways.
"""
import copy

KEEP, GIVE, UNCLEAR = "recipient_keeps_control", "to_sender_or_message_destination", "unclear"


def R(action, obj, sens, quote, stance="requested", handover=GIVE, dest=None):
    return {"action": action, "object": obj, "sensitivity": sens, "recipient": None, "stance": stance,
            "handover": handover, "destination": dest, "quote": quote}


def M(overall, mech="none", sender=None, stype="none", reqs=(), tac=(), thr=(), pro=(), dep=None, prot=(), lang="ro", squote=""):
    return {"message_language": lang, "claim_summary": "Rezumat.", "wants_summary": "Cere ceva.",
            "claimed_sender": {"name": sender, "type": stype, "quote": sender if squote == "" else squote},
            "requests": list(reqs),
            "promises": [{"kind": k, "quote": q} for k, q in pro],
            "threats": [{"kind": k, "quote": q} for k, q in thr],
            "dependency": {"present": bool(dep), "description": "Plata înaintea beneficiului." if dep else None, "quote": dep},
            "tactics": [{"tactic": t, "quote": q} for t, q in tac],
            "protective_context": [{"kind": k, "quote": q} for k, q in prot],
            "mechanism": {"category": mech, "description": "Descriere."}, "overall": overall, "uncertainties": []}


MOCKS = {
    # ------------------------------------------------ the seven reported messages (faithful readings)
    "A-visa-gpay": M("ordinary_or_legitimate", sender="Visa", stype="bank", reqs=[
        R("call_number", "apel la *2000", "low", "contacteaza-ne la *2000", stance="hypothetical", dest="*2000")]),
    "B-fan-coordination": M("ordinary_or_legitimate", sender="FAN Courier", stype="courier", reqs=[
        R("call_number", "apel pentru livrare", "low", "Va rugam sa ne contactati la tel 0725724911", dest="0725724911")]),
    "C-orange-promo-1": M("marketing_or_spam", sender="Orange", stype="telecom_or_utility", reqs=[
        R("click_link", "intrarea în joc", "low", "Hai in Pinata Party aici", dest="https://orange.onelink.me/JgKP/gsa5cd2g"),
        R("change_settings", "preferințe GDPR", "low", "Afla cum poti modifica preferintele de prelucrare a datelor personale", stance="hypothetical", handover=KEEP)],
        pro=[("money_or_prize", "poti castiga prin tragere la sorti una din cele 10 trotinete")]),
    "D-cargus-pickup": M("ordinary_or_legitimate", sender="Cargus", stype="courier", reqs=[
        R("other", "PIN de ridicare", "secret_credential", "PIN 3168", stance="provided_to_recipient", handover=KEEP),
        R("click_link", "detalii colet", "low", "Vezi detalii", dest="https://my.cargus.ro/Sp8mscz3avjL")]),
    "E-orange-promo-2": M("marketing_or_spam", sender="Orange", stype="telecom_or_utility", reqs=[
        R("click_link", "intrarea în joc", "low", "Intra in Pinata Party aici", dest="https://orange.onelink.me/JgKP/8rrjf5o2")],
        pro=[("money_or_prize", "intri in tragerea la sorti pentru una din cele 10 trotinete")]),
    "F-cargus-delivery": M("ordinary_or_legitimate", sender="Cargus", stype="courier", squote=None, reqs=[
        R("other", "PIN livrare", "secret_credential", "PIN 5499", stance="provided_to_recipient", handover=KEEP),
        R("click_link", "detalii", "low", "Vezi detalii si optiuni", dest="https://my.cargus.ro/1xOlOnNcqtpa")]),
    "G-tursib-portal": M("ordinary_or_legitimate", sender="Tursib", stype="other_organization", reqs=[
        R("sign_in", "autentificare în portal", "secret_credential", "Va rugam sa va autentificati in Portal", handover=KEEP)]),

    # ------------------------------------------------ release holdout (independent author)
    "RH-001": M("ordinary_or_legitimate", sender="Atelierul de lectură", stype="online_service", reqs=[
        R("other", "cod de conectare", "secret_credential", "codul de conectare pe care tocmai l-ai cerut este 764 139", stance="provided_to_recipient", handover=KEEP),
        R("sign_in", "cod de conectare", "secret_credential", "Pune-l în caseta rămasă deschisă din ecranul tău de logare", stance="self_initiated", handover=KEEP)]),
    "RH-002": M("likely_scam", "card_data_theft", stype="unknown_person", reqs=[
        R("share_otp_or_code", "cifrele PIN-ului cardului", "secret_credential", "trimite aici primele 2 cifre pe un rând și ultimele 2 separat")],
        tac=[("trust_exploitation", "Îl am la mine, pot să-l scot din blocaj azi")]),
    "RH-003": M("likely_scam", "advance_fee", stype="buyer_or_seller", reqs=[
        R("transfer_money", "165 lei transport", "financial_asset", "Plătești întâi 165 lei transportul în contul pe care ți-l scrie șoferul pe chat")],
        dep="Plătești întâi 165 lei transportul", pro=[("delivery_or_goods", "Puiul de pisică e gratis")],
        tac=[("channel_switch", "în contul pe care ți-l scrie șoferul pe chat")]),
    "RH-004": M("protective_or_educational", reqs=[
        R("approve_authorization", "permisiunea de citire a mesajelor", "device_or_account_control",
          "Când vezi «Permite citirea și expedierea tuturor mesajelor», apasă Refuză", stance="discouraged", handover=KEEP)],
        prot=[("security_warning", "Acordul din reclama cu calendarul ajunge la o aplicație din afara firmei")]),
    "RH-005": M("likely_scam", "malicious_authorization", reqs=[
        R("approve_authorization", "acces la mesaje și trimitere", "device_or_account_control",
          "Bifează Citirea tuturor mesajelor, Trimiterea din căsuța ta și Acces chiar când ești offline, apoi dă Allow",
          dest="https://sincronizare-panel.test/connect")],
        tac=[("trust_exploitation", "Dacă apare «Acest editor nu a fost verificat», continuă")]),
    "RH-006": M("marketing_or_spam", sender="Plan de Hârtie", stype="other_organization", reqs=[
        R("other", "cod promo", "low", "treci codu promo SCHITA la pagina Abonament", handover=KEEP)],
        tac=[("scarcity", "E ultima zi de înscriere")]),
    "RH-007": M("likely_scam", "family_impersonation", sender="sor-ta", stype="family_or_friend", reqs=[
        R("transfer_money", "2.800 lei în plic", "financial_asset", "Pune-i pe toți, 2.800 lei, și dă plicul închis bărbatului cu casca galbenă de la intrare")],
        tac=[("family_impersonation", "Sunt sor-ta"), ("urgency", "A ajuns acu, nu-l lăsa să plece"),
             ("secrecy", "Pe nr meu de obicei nu verifica")]),
    "RH-008": M("ordinary_or_legitimate", stype="employer_or_recruiter", reqs=[
        R("send_documents_or_photos", "bonul și IBAN-ul", "personal_data", "Încarcă-le la Deconturi în intranet, acolo unde ai deschis cererea", handover=KEEP)]),
    "RH-009": M("likely_scam", "account_takeover", stype="unknown_person", reqs=[
        R("send_documents_or_photos", "poza cu QR-ul eSIM", "device_or_account_control", "Trimite-mi în schimb poza întreagă cu QR-ul")],
        tac=[("secrecy", "După aia poți să ștergi mesajul de la operator")]),
    "RH-010": M("likely_scam", "institution_impersonation", sender="Direcția de Transport Valea Frasinului", stype="government", reqs=[
        R("call_number", "apel la număr cu tarif special", "financial_asset", "Ține apelul deschis cel puțin 12 minute chiar dacă auzi numai muzică",
          dest="https://dispecer-traseu.test/T71")],
        thr=[("legal_or_fine", "altfel dosarul se clasează")], tac=[("authority", "proces-verbal T71")]),
    "RH-011": M("protective_or_educational", reqs=[
        R("send_documents_or_photos", "poza QR-ului", "device_or_account_control", "păstrează QR-ul la tine", stance="discouraged", handover=KEEP)],
        prot=[("security_warning", "Dacă cineva pretinde că are nevoie de o poză ca să facă «test de semnal», păstrează QR-ul la tine și oprește conversația")]),
    "RH-012": M("likely_scam", "advance_fee", reqs=[
        R("pay_fee", "taxa de eliberare 1.790 lei", "financial_asset", "Adu în numerar taxa de eliberare de 1.790 lei persoanei din parcarea pe care ți-o dau în privat")],
        dep="Îți arată ordinul de restituire doar după ce-i dai banii", pro=[("refund_or_compensation", "Recovery confirmat, 31.600 lei")],
        tac=[("secrecy", "Nu suna la banca ta")]),
    "RH-013": M("likely_scam", "credential_phishing", reqs=[
        R("share_password", "fișierul cu toate parolele", "secret_credential", "Trage-l în caseta de la https://profil-nou.test/import",
          dest="https://profil-nou.test/import")],
        tac=[("trust_exploitation", "așa ne asigurăm că datele rămân confidențiale")]),
    "RH-014": M("ordinary_or_legitimate", reqs=[
        R("transfer_money", "rata de 319,40 lei", "financial_asset", "În aplicația băncii alege beneficiarul pe care l-ai salvat la prima plată", handover=KEEP)]),
    "RH-015": M("likely_scam", "identity_document_theft", sender="Serviciul de Revizuire Pensii", stype="government", reqs=[
        R("send_documents_or_photos", "procura semnată în alb", "identity_document",
          "Trimiteți poza paginii semnate la dosar-personal@punct-indexare.test până la ora 14", dest="dosar-personal@punct-indexare.test")],
        tac=[("urgency", "până la ora 14")]),
    "RH-016": M("protective_or_educational", reqs=[
        R("send_documents_or_photos", "exportul parolelor", "secret_credential", "Exportă parolele în CSV și încarcă documentul pe formularul de migrare.",
          stance="reported_or_quoted", handover=KEEP)],
        prot=[("educational_example", "Asta era fraza pe care trebuia s-o sublinieze participanții în fișa de curs")]),
    "RH-017": M("likely_scam", "malicious_authorization", reqs=[
        R("approve_authorization", "cheltuire nelimitată din portofel", "device_or_account_control",
          "semnează «Allow unlimited spending» pentru toate jetoanele din sold", dest="https://ridicare-margele.test/claim")],
        pro=[("delivery_or_goods", "Așa primești obiectul")]),
    "RH-018": M("ordinary_or_legitimate", reqs=[
        R("sign_in", "PIN-ul cheii fizice", "secret_credential", "bagi PIN-ul cheii acolo, pe același laptop", stance="self_initiated", handover=KEEP)]),
    "RH-019": M("likely_scam", "account_takeover", reqs=[
        R("share_password", "parola de aplicație", "secret_credential", "Scrie codul ăla de 16 caractere în reply aici cu adresa ta de e-mail")],
        tac=[("trust_exploitation", "serviciul nostru trebuie să poată intra din nou")]),
    "RH-020": M("ordinary_or_legitimate", stype="retailer_or_marketplace", reqs=[
        R("pay_fee", "marfa la livrare", "financial_asset", "Marfa se plătește la livrare ca până acum", handover=KEEP)]),
    "RH-021": M("likely_scam", "payment_redirection", sender="Tatăl tău", stype="family_or_friend", reqs=[
        R("change_payment_details", "contul în care se virează chiria", "financial_asset",
          "Scrie-i să vireze chiria garsonierei în noul cont al lui M. S., îți dau IBAN separat")],
        tac=[("family_impersonation", "Tatăl tău aici"), ("secrecy", "Dacă primești răspuns la mailul meu vechi ignoră-l")]),
    "RH-022": M("protective_or_educational", reqs=[
        R("change_payment_details", "contul chiriei", "financial_asset", "«Schimbă plata tuturor lunilor în contul lui M. S.» e mesajul fals",
          stance="reported_or_quoted", handover=KEEP)],
        prot=[("quoted_scam", "e mesajul fals care a circulat de pe profilul copiat")]),
    "RH-023": M("likely_scam", "account_takeover", reqs=[
        R("other", "cheia de autentificare USB", "device_or_account_control", "Pune cheia ta de autentificare USB într-un plic și lasă-l curierului de la intrarea laterală"),
        R("share_password", "PIN-ul cheii", "secret_credential", "Scrie PIN-ul ei pe biletul din plic")],
        tac=[("secrecy", "Cererea e confidențială, nu deschide tichet IT")]),
    "RH-024": M("likely_scam", "job_scam", stype="employer_or_recruiter", reqs=[
        R("transfer_money", "95 lei pentru instructaj", "financial_asset", "pune 95 lei pentru instructaj în contul personal al coordonatoarei")],
        dep="Înainte să primești contractu, pune 95 lei pentru instructaj", pro=[("job_income", "ai prins tura de inventar")],
        tac=[("secrecy", "Nu te duce la magazin să întrebi")]),
    "RH-025": M("protective_or_educational", reqs=[
        R("change_settings", "dezactivarea redirecționării", "device_or_account_control",
          "Verifică în setările telefonului dacă e activă Redirecționare și dezactiveaz-o", handover=KEEP)],
        prot=[("security_warning", "vine de la cineva care vrea să preia convorbirile în locul tău")]),
    "RH-026": M("likely_scam", "account_takeover", reqs=[
        R("change_settings", "redirecționarea tuturor apelurilor către agent", "device_or_account_control",
          "pune Redirecționare > Toate apelurile spre numărul de mobil al agentului pe care ți-l trimit separat")],
        tac=[("trust_exploitation", "Am deschis intervenția pentru semnal")]),
    "RH-027": M("ordinary_or_legitimate", reqs=[
        R("transfer_money", "avans 30%", "financial_asset", "Le achităm 30% avans pe factura 827, cu beneficiarul firmei de pe deviz", handover=KEEP)]),
    "RH-028": M("likely_scam", "other_suspicious_mechanism", sender="Oficiul Județean de Achiziții", stype="government", reqs=[
        R("send_documents_or_photos", "contracte, prețuri și date de contact", "personal_data",
          "Trimiteți la revizie-dosare@evidenta-instant.test contractele în vigoare", dest="revizie-dosare@evidenta-instant.test")],
        tac=[("secrecy", "nu știu de audit și nu trebuie consultați"), ("urgency", "Primim arhiva doar în această seară")]),
    "RH-029": M("likely_scam", "credential_phishing", reqs=[
        R("share_password", "tokenul de publicare", "secret_credential", "pune valoarea completă a tokenului cu care faci deja release-uri",
          dest="https://verificator-pachete.test/probe")]),
    "RH-030": M("marketing_or_spam", sender="Sala Castan", stype="other_organization", reqs=[
        R("buy_or_subscribe", "bilet", "low", "Luați biletul de la casa sălii sau din pagina de evenimente", dest="https://sala-castan.example/program")],
        tac=[("scarcity", "Mai sunt 8 locurle libere")]),
    "RH-031": M("ordinary_or_legitimate", reqs=[
        R("other", "cod de ridicare", "low", "Arătați codul de ridicare din Rezervările mele bibliotecarei de la ghișeu", handover=KEEP)]),
    "RH-032": M("likely_scam", "advance_fee", reqs=[
        R("pay_fee", "920 lei asigurare", "financial_asset",
          "depune 920 lei la terminalul de plăți, la Alimentare portofel, pe identificatorul personal al brokerului din conversație")],
        dep="Ca să intre azi, depune 920 lei", pro=[("money_or_prize", "Credit de 9.800 lei aprobat fără acte")],
        tac=[("urgency", "oferta expiră în 15 min")]),
    "RH-033": M("likely_scam", "family_impersonation", sender="Unchiu Doru", stype="family_or_friend", reqs=[
        R("buy_or_subscribe", "credit de 30 euro", "financial_asset", "bagă-i credit de 30 euro pe numărul ăsta al lui")],
        tac=[("family_impersonation", "Mi s-a stins fonul, îți scriu de la un coleg"), ("secrecy", "nu-i da mesaj lui tanti")]),
    "RH-034": M("protective_or_educational", reqs=[
        R("call_number", "apel cu tarif special", "financial_asset", "«ține apelul deschis 12 minute chiar dacă auzi doar muzică»",
          stance="reported_or_quoted", handover=KEEP)],
        prot=[("security_warning", "Numărul cu tarif special de acolo nu e al Direcției")]),
    "RH-035": M("likely_scam", "credential_phishing", sender="Clinica Alun", stype="other_organization", reqs=[
        R("sign_in", "e-mailul și parola dosarului medical", "secret_credential",
          "În pagina deschisă introdu adresa de e-mail și aceeași parolă cu care intri de obicei la dosarul medical",
          dest="https://copie-analize.test/verifica#https://dosare.alun-medical.example/intrare")],
        tac=[("trust_exploitation", "Vezi că adresa oficială apare la final aici")]),
    "RH-036": M("ordinary_or_legitimate", reqs=[
        R("call_number", "apel la recepție", "low", "Ajunge numărul comenzii dacă ne suni la recepție", stance="hypothetical", handover=KEEP)],
        pro=[("refund_or_compensation", "Restituim 128 lei pe cardul cu care s-a făcut plata")]),
    "RH-037": M("likely_scam", "otp_or_authentication_theft", reqs=[
        R("share_otp_or_code", "codul de 8 caractere din e-mail", "secret_credential", "Pune caracterele exact în răspunsul la mesajul ăsta")],
        tac=[("trust_exploitation", "Ți-am cerut o conectare la dosarul de vânzări, pentru inventar")]),
    "RH-038": M("protective_or_educational", reqs=[
        R("share_otp_or_code", "codul de conectare", "secret_credential", "pune codul de conectare în răspuns și rămâi pe fir", stance="reported_or_quoted", handover=KEEP),
        R("other", "ajutor la închiderea sesiunilor", "low", "Mă ajuți să găsesc butonul Închide toate sesiunile în aplicația reală?", handover=KEEP)],
        prot=[("news_report", "Am făcut o prostie la inventar")]),
    "RH-039": M("ordinary_or_legitimate", reqs=[
        R("sign_in", "parola veche și cea nouă", "secret_credential", "completezi parola veche și pe cea nouă în cele două casete din cont", handover=KEEP)]),

    # ------------------------------------------------ fresh holdout v2.0
    "FH-01": M("likely_scam", "otp_or_authentication_theft", stype="online_service", reqs=[
        R("share_otp_or_code", "codul de 6 cifre", "secret_credential", "trimiteti-ne pe acest chat codul de 6 cifre care tocmai v-a venit")],
        thr=[("other", "Fara el migrarea esueaza")]),
    "FH-02": M("likely_scam", "credential_phishing", stype="tech_support", lang="en", reqs=[
        R("share_password", "parola curentă și cea nouă", "secret_credential", "Reply with your current login and new desired password")],
        thr=[("other", "otherwise mail will bounce")], tac=[("urgency", "before 5pm")]),
    "FH-03": M("likely_scam", "card_data_theft", reqs=[
        R("send_documents_or_photos", "poza cardului față-verso cu CVV", "secret_credential",
          "fă o poză clară cu fața și cu verso-ul cardului (să se vadă cele 3 cifre) și trimite-o aici pe WhatsApp")],
        pro=[("money_or_prize", "Pentru ridicarea premiului de fidelitate")]),
    "FH-04": M("likely_scam", "card_data_theft", sender="Clinica Medsana Plus", stype="other_organization", reqs=[
        R("share_card_data", "numărul cardului și data expirării", "secret_credential",
          "confirmă identitatea introducând numărul cardului și data expirării", dest="https://medsana-rezultate.example/acces")]),
    "FH-05": M("likely_scam", "otp_or_authentication_theft", stype="unknown_person", reqs=[
        R("share_otp_or_code", "codul primit", "secret_credential", "poti sa mi-l dai te rog?")],
        tac=[("urgency", "e urgent")]),
    "FH-06": M("likely_scam", "advance_fee", reqs=[
        R("pay_fee", "asigurare 350 lei", "financial_asset", "este necesară o asigurare de 350 lei, plătibilă azi în contul consultantului")],
        dep="Pentru virarea sumei este necesară o asigurare de 350 lei", pro=[("money_or_prize", "Cererea dvs. de credit de 40.000 lei a fost aprobată")]),
    "FH-07": M("likely_scam", "advance_fee", lang="en", reqs=[
        R("pay_fee", "taxă 120 EUR în carduri cadou", "financial_asset", "a clearance fee of 120 EUR must be paid via gift cards"),
        R("other", "codurile cardurilor cadou", "financial_asset", "Reply with the card codes")],
        dep="To release the 85,000 EUR prize, a clearance fee of 120 EUR must be paid via gift cards",
        pro=[("money_or_prize", "your email was selected in the Euro Digital Draw")]),
    "FH-08": M("likely_scam", "advance_fee", reqs=[
        R("transfer_money", "garanția de o lună", "financial_asset", "Dacă trimiți garanția de o lună prin transfer")],
        dep="Dacă trimiți garanția de o lună prin transfer, îți trimit cheile prin curier",
        pro=[("delivery_or_goods", "îți trimit cheile prin curier")]),
    "FH-09": M("likely_scam", "investment_fraud", sender="TradeNova", stype="investment_platform", reqs=[
        R("pay_fee", "taxa de validare 10%", "financial_asset", "Retragerea se deblochează după plata taxei de validare de 10% din câștig")],
        dep="Retragerea se deblochează după plata taxei de validare", pro=[("investment_return", "soldul tău a ajuns la 6.240 EUR")],
        tac=[("channel_switch", "Consultantul te așteaptă pe Telegram")]),
    "FH-10": M("likely_scam", "family_impersonation", stype="family_or_friend", reqs=[
        R("transfer_money", "1.800 lei", "financial_asset", "Poti sa-mi trimiti pe revolut-ul lui?")],
        tac=[("family_impersonation", "Tata, sunt eu, scriu de pe telefonul unui coleg"), ("secrecy", "Nu-i zice mamei")]),
    "FH-11": M("likely_scam", "family_impersonation", stype="family_or_friend", reqs=[
        R("buy_or_subscribe", "card cadou de 500 lei și codul lui", "financial_asset",
          "Îmi poți cumpăra un card cadou de 500 de lei de la benzinărie și să-mi trimiți poza cu codul?")],
        tac=[("family_impersonation", "Bunico, sunt nepotul tău"), ("secrecy", "îmi e rușine să-i spun lui tata")]),
    "FH-12": M("likely_scam", "payment_redirection", sender="Furnizorul tău de energie", stype="telecom_or_utility", reqs=[
        R("transfer_money", "214,60 lei în cont nou", "financial_asset", "Achită 214,60 lei în noul cont RO12BACX0000001234567890 până mâine",
          dest="RO12BACX0000001234567890")],
        thr=[("other", "pentru a evita deconectarea")], tac=[("urgency", "până mâine")]),
    "FH-13": M("likely_scam", "card_data_theft", stype="government", reqs=[
        R("share_card_data", "datele cardului", "secret_credential", "Completați formularul de restituire cu datele cardului pe portal-restituiri-fisc.example",
          dest="portal-restituiri-fisc.example")],
        pro=[("refund_or_compensation", "ați fost selectat pentru o rambursare de impozit de 1.284 lei")], tac=[("urgency", "în 48 de ore")]),
    "FH-14": M("likely_scam", "delivery_scam", stype="courier", reqs=[
        R("pay_fee", "taxa de reprogramare 2,99 lei", "financial_asset", "Taxa de reprogramare a livrării este 2,99 lei",
          dest="https://livrare-rapida-ro.example/plata")],
        thr=[("loss_of_goods_or_money", "e reținut în depozit")]),
    "FH-15": M("likely_scam", "payment_redirection", sender="Grupului Ardeal Construct", stype="other_organization", reqs=[
        R("change_payment_details", "contul nou de plată", "financial_asset", "Vă rugăm actualizați datele înainte de factura următoare")]),
    "FH-16": M("likely_scam", "remote_access", stype="bank", reqs=[
        R("install_or_grant_access", "AnyDesk și codul de acces", "device_or_account_control", "instalați aplicația AnyDesk și citiți-ne codul de 9 cifre afișat")],
        tac=[("authority", "Suntem de la securitatea băncii")]),
    "FH-17": M("likely_scam", "malicious_authorization", reqs=[
        R("approve_authorization", "gestionarea contului de către aplicație", "device_or_account_control",
          "apasă „Permite” pe pagina de contestație ca aplicația noastră să-ți gestioneze contul", dest="https://appeal-center-meta.example")],
        thr=[("account_block", "Contul tău de social media va fi închis")]),
    "FH-18": M("likely_scam", "account_takeover", sender="Operatorul tău", stype="telecom_or_utility", reqs=[
        R("change_settings", "redirecționarea apelurilor", "device_or_account_control", "formează *21* urmat de numărul 0749 000 111 și apasă apel",
          dest="0749 000 111")],
        pro=[("other", "pentru a primi bonusul de 50 GB")], tac=[("urgency", "Oferta expiră la miezul nopții")]),
    "FH-19": M("likely_scam", "malicious_authorization", lang="en", reqs=[
        R("approve_authorization", "aprobarea tranzacției din portofel", "device_or_account_control", "approve the transaction that appears",
          dest="walletsync-secure.example")]),
    "FH-20": M("likely_scam", "marketplace_scam", stype="buyer_or_seller", reqs=[
        R("share_card_data", "datele cardului inclusiv CVV", "secret_credential", "completează datele cardului tău, inclusiv codul de pe spate",
          dest="https://plata-sigura-livrare.example/primire")],
        pro=[("money_or_prize", "Ca să primești banii")]),
    "FH-21": M("protective_or_educational", stype="bank", reqs=[
        R("share_otp_or_code", "coduri, PIN, date card", "secret_credential", "nu îți vom cere niciodată prin telefon, SMS sau email codul de autorizare",
          stance="discouraged", handover=KEEP)],
        prot=[("security_warning", "Dacă cineva le cere în numele nostru, închide și sună la numărul de pe card")]),
    "FH-22": M("protective_or_educational", reqs=[
        R("transfer_money", "5.000 lei", "financial_asset", "trimite-mi 5.000 de lei", stance="reported_or_quoted", handover=KEEP)],
        prot=[("news_report", "Poliția avertizează asupra unei noi metode")]),
    "FH-23": M("ordinary_or_legitimate", reqs=[
        R("other", "cod de verificare", "secret_credential", "Codul tău de verificare este 482 913", stance="provided_to_recipient", handover=KEEP)],
        prot=[("account_security_instruction", "Nu îl comunica nimănui, nici angajaților noștri")]),
    "FH-24": M("ordinary_or_legitimate", stype="family_or_friend", reqs=[
        R("transfer_money", "87 lei", "financial_asset", "trimite-mi pe IBAN-ul pe care îl ai deja de la mine", handover=KEEP)]),
    "FH-25": M("ordinary_or_legitimate", sender="Digi", stype="telecom_or_utility", reqs=[
        R("pay_fee", "factura de 52,50 lei", "financial_asset", "O poți plăti din aplicația Digi sau de la orice ghișeu", handover=KEEP)]),
    "FH-26": M("ordinary_or_legitimate", stype="other_organization", reqs=[
        R("transfer_money", "întreținerea", "financial_asset", "Plata se face la administrator joi între 18 și 20 sau prin transfer în contul asociației", handover=KEEP)]),
    "FH-27": M("marketing_or_spam", sender="Librăria Cărturești", stype="retailer_or_marketplace", reqs=[
        R("buy_or_subscribe", "cărți", "low", "Vezi oferta în magazin sau pe site", handover=KEEP)]),
    "FH-28": M("ordinary_or_legitimate", sender="Spotify", stype="online_service", lang="en", reqs=[
        R("other", "gestionarea abonamentului", "low", "Manage your plan anytime in your account settings", stance="hypothetical", handover=KEEP)]),
    "FH-29": M("ordinary_or_legitimate", stype="other_organization", reqs=[
        R("reply_or_contact", "răspuns ANULEZ", "low", "răspunde cu ANULEZ", stance="hypothetical")]),
    "FH-30": M("ordinary_or_legitimate", stype="family_or_friend"),

    # ------------------------------------------------ fresh holdout v2.1 (written with the audit)
    "N01": M("ordinary_or_legitimate", sender="Sameday", stype="courier", reqs=[
        R("other", "cod de deschidere easybox", "secret_credential", "Codul de deschidere este 482910", stance="provided_to_recipient", handover=KEEP)]),
    "N02": M("likely_scam", "otp_or_authentication_theft", sender="Sameday", stype="courier", reqs=[
        R("share_otp_or_code", "codul de deschidere", "secret_credential", "trimite-ne prin SMS codul de deschidere primit de la noi")],
        thr=[("loss_of_goods_or_money", "Fara confirmare coletul se returneaza")]),
    "N03": M("ordinary_or_legitimate", sender="BCR", stype="bank", reqs=[
        R("sign_in", "autentificare în aplicația George", "secret_credential", "Autentifica-te in aplicatie pentru a o citi", handover=KEEP)]),
    "N04": M("likely_scam", "credential_phishing", sender="BCR", stype="bank", reqs=[
        R("sign_in", "datele de autentificare", "secret_credential", "Autentificati-va urgent pentru reactivare",
          dest="https://george-bcr.secure-acces.com/login")],
        thr=[("account_block", "Contul dvs. a fost restrictionat")], tac=[("urgency", "Autentificati-va urgent")]),
    "N05": M("marketing_or_spam", sender="Vodafone", stype="telecom_or_utility", reqs=[
        R("reply_or_contact", "SMS cu WEEKEND", "low", "trimite GRATIS la 333 un SMS cu textul WEEKEND", stance="hypothetical", dest="333")],
        pro=[("other", "Ai 20 GB cadou in weekend")]),
    "N06": M("likely_scam", "advance_fee", sender="Vodafone", stype="telecom_or_utility", reqs=[
        R("pay_fee", "taxa de procesare 4,99 lei", "financial_asset", "Pentru livrare achita doar taxa de procesare de 4,99 lei aici",
          dest="https://vodafone-premii.top/c")],
        dep="Pentru livrare achita doar taxa de procesare de 4,99 lei", pro=[("money_or_prize", "Ai castigat un iPhone 16 la tragerea lunara")],
        tac=[("reward_bait", "Felicitari! Ai castigat un iPhone 16")]),
    "N07": M("ordinary_or_legitimate", sender="eMAG", stype="retailer_or_marketplace", reqs=[
        R("click_link", "chestionar de satisfacție", "low", "completeaza chestionarul de 1 minut", dest="https://emag.page.link/feedback23")]),
    "N08": M("likely_scam", "card_data_theft", sender="eMAG", stype="retailer_or_marketplace", reqs=[
        R("share_card_data", "datele cardului", "secret_credential", "Introdu datele cardului pentru validare", dest="https://emag.page.link/vouch")],
        pro=[("money_or_prize", "Ai un voucher de 500 lei nerevendicat")], tac=[("reward_bait", "Ai un voucher de 500 lei nerevendicat")]),
    "N09": M("ordinary_or_legitimate", sender="DPD", stype="courier", reqs=[
        R("call_number", "apel pentru reprogramare", "low", "Va rugam sunati la 0731 123 456 pentru reprogramarea livrarii", dest="0731 123 456")]),
    "N10": M("likely_scam", "delivery_scam", sender="DPD", stype="courier", reqs=[
        R("call_number", "apel la număr cu tarif special", "financial_asset", "Sunati urgent la 0900 123 456 (tarif special) in 2 ore", dest="0900 123 456")],
        thr=[("loss_of_goods_or_money", "altfel coletul va fi distrus")], tac=[("urgency", "in 2 ore")]),
    "N11": M("protective_or_educational", sender="Revolut", stype="bank", reqs=[
        R("approve_authorization", "confirmarea conectării", "device_or_account_control", "Daca da, confirma in aplicatie", stance="hypothetical", handover=KEEP)],
        prot=[("account_security_instruction", "Daca nu, refuza si schimba parola")]),
    "N12": M("likely_scam", "malicious_authorization", sender="Revolut", stype="bank", reqs=[
        R("approve_authorization", "aprobarea notificării", "device_or_account_control", "apasa Aproba ca sa anulam plata frauduloasa")],
        tac=[("fear", "plata frauduloasa"), ("authority", "Un agent te va suna acum")]),
    "N13": M("ordinary_or_legitimate", stype="family_or_friend"),
    "N14": M("likely_scam", "family_impersonation", stype="family_or_friend", reqs=[
        R("transfer_money", "1.500 lei în contul prietenei", "financial_asset", "Trimite-mi te rog 1.500 lei in contul ei", dest="RO49AAAA1B31007593840000")],
        tac=[("family_impersonation", "Mama, sunt eu, telefonul mi s-a stricat si scriu de pe numarul unei prietene")]),
    "N15": M("ordinary_or_legitimate", sender="Enel", stype="telecom_or_utility", reqs=[
        R("pay_fee", "factura de 186,30 lei", "financial_asset", "Plata se poate face din aplicatie", stance="hypothetical", handover=KEEP)]),
    "N16": M("likely_scam", "payment_redirection", sender="Enel", stype="telecom_or_utility", reqs=[
        R("change_payment_details", "noul cont de plată", "financial_asset", "factura din noiembrie se plateste in noul cont RO12INGB0000999912345678",
          dest="RO12INGB0000999912345678")],
        thr=[("loss_of_goods_or_money", "Platile in contul vechi nu vor fi inregistrate")]),
    "N17": M("ordinary_or_legitimate", sender="ANAF", stype="government", reqs=[
        R("sign_in", "autentificare în SPV", "secret_credential", "Autentifica-te pe anaf.ro pentru a-l citi", handover=KEEP, dest="anaf.ro")]),
    "N18": M("likely_scam", "card_data_theft", sender="ANAF", stype="government", reqs=[
        R("share_card_data", "datele cardului", "secret_credential", "Completati datele cardului pentru restituire", dest="https://anaf-rambursare.info/r")],
        pro=[("refund_or_compensation", "Aveti o rambursare de 742 lei")], tac=[("urgency", "in 24h")]),
    "N19": M("ordinary_or_legitimate", sender="Glovo", stype="online_service", reqs=[
        R("other", "cod de autentificare", "secret_credential", "Codul tau de autentificare Glovo este 5521", stance="provided_to_recipient", handover=KEEP)],
        prot=[("account_security_instruction", "Nu il da nimanui")]),
    "N20": M("likely_scam", "otp_or_authentication_theft", sender="Glovo", stype="online_service", reqs=[
        R("share_otp_or_code", "codul de 4 cifre", "secret_credential", "Poti sa mi-l spui ca sa il anulez?")],
        tac=[("trust_exploitation", "ti-am trimis din greseala un cod de 4 cifre")]),
    "N21": M("ordinary_or_legitimate", stype="employer_or_recruiter", reqs=[
        R("reply_or_contact", "confirmare DA", "low", "Va rugam confirmati raspunzand DA")]),
    "N22": M("likely_scam", "job_scam", stype="employer_or_recruiter", reqs=[
        R("pay_fee", "taxa de înscriere 150 lei", "financial_asset", "achitati 150 lei taxa de inscriere pe Telegram @hr_job_ro", dest="@hr_job_ro")],
        dep="Pentru activarea contului de angajat achitati 150 lei", pro=[("job_income", "job remote 300 lei/zi")],
        tac=[("channel_switch", "pe Telegram @hr_job_ro")]),
    "N23": M("ordinary_or_legitimate", sender="OLX", stype="retailer_or_marketplace", reqs=[
        R("reply_or_contact", "răspuns cumpărătorului", "low", "Raspunde din aplicatia OLX", handover=KEEP)]),
    "N24": M("likely_scam", "marketplace_scam", stype="buyer_or_seller", reqs=[
        R("share_card_data", "datele cardului", "secret_credential", "completeaza datele cardului aici", dest="https://olx.ro-livrare.com/primire")],
        pro=[("money_or_prize", "Ca sa primesti banii")]),
    "N25": M("marketing_or_spam", sender="Digi", stype="telecom_or_utility", reqs=[
        R("click_link", "descărcarea aplicației", "low", "Descarca noua aplicatie Digi Online", dest="https://digionline.app.link/meci")]),
    "N26": M("likely_scam", "card_data_theft", sender="Digi", stype="telecom_or_utility", reqs=[
        R("share_card_data", "datele cardului", "secret_credential", "Actualizeaza cardul pentru a evita suspendarea", dest="https://digi-ro.web.app/plata")],
        thr=[("account_block", "pentru a evita suspendarea")]),
    "N27": M("protective_or_educational", sender="ING", stype="bank", reqs=[
        R("install_or_grant_access", "aplicații la cererea altora", "device_or_account_control",
          "Nu instalati aplicatii la cererea unor persoane care spun ca sunt de la banca", stance="discouraged", handover=KEEP)],
        prot=[("security_warning", "ING nu va cere niciodata acces la telefon")]),
    "N28": M("likely_scam", "remote_access", sender="ING Securitate", stype="bank", reqs=[
        R("install_or_grant_access", "RustDesk și ID-ul de acces", "device_or_account_control", "instalati aplicatia RustDesk si comunicati-ne ID-ul afisat")],
        tac=[("fear", "Am detectat o tranzactie suspecta")]),
    "N29": M("ordinary_or_legitimate", sender="Sameday", stype="courier", reqs=[
        R("other", "PIN de deschidere", "secret_credential", "PIN deschidere 773201", stance="provided_to_recipient", handover=KEEP),
        R("click_link", "detalii", "low", "Detalii: https://sameday.ro/awb/9912", stance="hypothetical", dest="https://sameday.ro/awb/9912")]),
    "N30": M("likely_scam", "delivery_scam", sender="Sameday", stype="courier", reqs=[
        R("pay_fee", "taxa de deblocare 1,99 lei", "financial_asset", "Plateste taxa de 1,99 lei pentru deblocare", dest="https://sameday-easybox.net/pin")]),
    "N31": M("ordinary_or_legitimate", sender="Raiffeisen", stype="bank", reqs=[
        R("call_number", "apel pentru întrebări", "low", "Pentru intrebari suna la 021 306 3002", stance="hypothetical", dest="021 306 3002")]),
    "N32": M("likely_scam", "otp_or_authentication_theft", sender="Raiffeisen", stype="bank", reqs=[
        R("share_otp_or_code", "codul primit prin SMS", "secret_credential", "comunica operatorului care te va suna codul primit prin SMS")],
        thr=[("account_block", "Cardul tau a fost blocat preventiv")]),
    "N33": M("ordinary_or_legitimate", sender="Bolt", stype="online_service", lang="en"),
    "N34": M("likely_scam", "identity_document_theft", stype="unknown_person", reqs=[
        R("send_documents_or_photos", "poza buletinului și selfie", "identity_document", "Trimite-le pe WhatsApp la 0755 111 222", dest="0755 111 222")],
        pro=[("money_or_prize", "Te-am adaugat ca beneficiar pentru o mostenire")]),
    "N35": M("protective_or_educational", reqs=[
        R("share_otp_or_code", "codul din SMS", "secret_credential", "Trimite-mi codul din SMS, e urgent", stance="reported_or_quoted", handover=KEEP)],
        prot=[("quoted_scam", "E teapa, nu?")]),
    "N36": M("likely_scam", "otp_or_authentication_theft", sender="BT", stype="bank", reqs=[
        R("share_otp_or_code", "codul OTP", "secret_credential", "Trimite codul OTP primit la acest numar pentru deblocare")],
        thr=[("account_block", "Contul tau a fost blocat")]),
}


# ------------------------------------------------------------------ perturbations --
SUSPICIOUS_GUESS = {"courier": "delivery_scam", "bank": "credential_phishing", "telecom_or_utility": "reward_or_lottery"}


def perturb(mock, mode, truth):
    """Return a copy of the faithful mock with one realistic model error applied."""
    m = copy.deepcopy(mock)
    benign = truth != "scam"
    if mode == "faithful":
        return m
    if mode == "over_suspicious" and benign and m["overall"] != "protective_or_educational":
        # Observed live: ordinary notices read as "suspicious" (cases A, B, D, F).
        m["overall"] = "suspicious"
        m["mechanism"]["category"] = SUSPICIOUS_GUESS.get(m["claimed_sender"]["type"], "other_suspicious_mechanism")
    elif mode == "direction_errors" and benign:
        # Observed live: an own sign-in read as a secret request (case G); a supplied code read as requested.
        for r in m["requests"]:
            if r["stance"] in {"provided_to_recipient", "self_initiated"} or r["action"] == "sign_in":
                # The new direction fields are wrong; the action label itself is kept.
                r["stance"], r["handover"] = "requested", "to_sender_or_message_destination"
    elif mode == "under_suspicious" and not benign:
        m["overall"] = "suspicious"
    elif mode == "handover_lenient" and not benign:
        for r in m["requests"]:
            r["handover"] = "unclear"
    elif mode == "ungrounded":
        for r in m["requests"]:
            r["quote"] = "«" + r["quote"][::-1][:20] + "»"  # cannot be located in the text
        for key in ("tactics", "promises", "threats", "protective_context"):
            for item in m[key]:
                item["quote"] = "parafrază: " + item["quote"][:8]
        if m["dependency"]["quote"]:
            m["dependency"]["quote"] = "parafrază"
    elif mode == "reading_only" and not benign:
        # The model recognises the scam but itemises nothing concrete (unfamiliar scheme, terse output).
        m["requests"] = [r for r in m["requests"] if r["sensitivity"] == "low"]
        m["dependency"] = {"present": False, "description": None, "quote": None}
    return m


MODES = ("faithful", "over_suspicious", "direction_errors", "under_suspicious", "handover_lenient", "ungrounded", "reading_only")
