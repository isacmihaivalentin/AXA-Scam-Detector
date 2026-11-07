"""Faithful MOCK readings for sealed_holdout_v21b.json (not live Gemini).

Written after policy tuning was finished and frozen with sealed_v21b.sha256 before the
first evaluation run. Scored once against v2.0 and v2.1; no code changes follow from it.
"""
from mock_interpretations import GIVE, KEEP, M, R  # noqa: F401

SEALED = {
    "S01": M("ordinary_or_legitimate", sender="TAROM", stype="other_organization", reqs=[
        R("sign_in", "check-in", "low", "Il poti face in aplicatia TAROM sau pe tarom.ro", stance="hypothetical", handover=KEEP, dest="tarom.ro")]),
    "S02": M("likely_scam", "card_data_theft", sender="TAROM", stype="other_organization", reqs=[
        R("share_card_data", "datele cardului", "secret_credential", "introdu datele cardului in 12 ore", dest="https://tarom-refund.online/r")],
        pro=[("refund_or_compensation", "Pentru rambursarea biletului")], tac=[("urgency", "in 12 ore")]),
    "S03": M("ordinary_or_legitimate", sender="Netflix", stype="online_service", reqs=[
        R("other", "cod de acces", "secret_credential", "Codul tau de acces temporar pentru televizorul din casa este 7391",
          stance="provided_to_recipient", handover=KEEP),
        R("sign_in", "cod pe televizor", "secret_credential", "Il introduci pe ecranul televizorului", handover=KEEP)]),
    "S04": M("likely_scam", "otp_or_authentication_theft", sender="Netflix", stype="online_service", reqs=[
        R("share_otp_or_code", "codul de 4 cifre", "secret_credential", "Spune-mi-l aici ca sa nu se suspende abonamentul")],
        thr=[("account_block", "ca sa nu se suspende abonamentul")]),
    "S05": M("ordinary_or_legitimate", sender="Allianz-Tiriac", stype="other_organization", reqs=[
        R("pay_fee", "reînnoire RCA", "financial_asset", "Poti reinnoi polita din contul tau Allianz-Tiriac sau la agentul tau obisnuit",
          stance="hypothetical", handover=KEEP)]),
    "S06": M("likely_scam", "advance_fee", reqs=[
        R("pay_fee", "taxa de dosar 180 lei", "financial_asset", "plateste azi taxa de dosar de 180 lei pe Revolut la @asig_despagubiri",
          dest="@asig_despagubiri")],
        dep="Ca sa intre banii, plateste azi taxa de dosar de 180 lei", pro=[("refund_or_compensation", "Ai primit o despagubire de 2.400 lei")]),
    "S07": M("ordinary_or_legitimate", sender="Scoala Gimnaziala nr. 5", stype="other_organization"),
    "S08": M("likely_scam", "other_suspicious_mechanism", stype="other_organization", reqs=[
        R("transfer_money", "1.200 lei", "financial_asset", "trimiteti-i pe contul meu personal RO77BTRL0000123456789012",
          dest="RO77BTRL0000123456789012")],
        tac=[("fear", "Ioana s-a lovit la ora de sport si e la urgente"), ("urgency", "Trebuie achitati acum 1.200 lei")]),
    "S09": M("marketing_or_spam", sender="Carturesti", stype="retailer_or_marketplace", reqs=[
        R("click_link", "detalii lansare", "low", "Detalii si inscriere", dest="https://carturesti.us12.list-manage.com/track/click?u=ab12")]),
    "S10": M("likely_scam", "institution_impersonation", sender="CNAIR", stype="government", reqs=[
        R("pay_fee", "rovinieta 28 lei", "financial_asset", "achitand acum 28 lei pe https://rovinieta-plata.site/ro",
          dest="https://rovinieta-plata.site/ro")],
        thr=[("legal_or_fine", "Evitati amenda de 1.500 lei")], tac=[("urgency", "achitand acum")]),
    "S11": M("ordinary_or_legitimate", sender="Steam Guard", stype="online_service", reqs=[
        R("other", "cod de conectare", "secret_credential", "codul de conectare pentru contul tau este 4F7KQ", stance="provided_to_recipient", handover=KEEP)],
        prot=[("account_security_instruction", "Daca nu ai incercat tu sa te conectezi, schimba-ti parola")]),
    "S12": M("likely_scam", "account_takeover", reqs=[
        R("sign_in", "contul Steam", "secret_credential", "conecteaza-te cu Steam pe https://steamcommunlty-gift.com", dest="https://steamcommunlty-gift.com"),
        R("approve_authorization", "acces la inventar", "device_or_account_control", "aproba accesul aplicatiei la inventar",
          dest="https://steamcommunlty-gift.com")],
        pro=[("delivery_or_goods", "ai primit un skin rar")], tac=[("reward_bait", "Felicitari, ai primit un skin rar")]),
    "S13": M("ordinary_or_legitimate", sender="Policlinica Sanador", stype="other_organization", reqs=[
        R("call_number", "anulare", "low", "Pentru anulare sunati la 021 9699 sau raspundeti NU", stance="hypothetical", dest="021 9699")]),
    "S14": M("likely_scam", "identity_document_theft", sender="Sanador", stype="other_organization", reqs=[
        R("send_documents_or_photos", "poza cărții de identitate", "identity_document", "Trimiteti o poza cu cartea de identitate"),
        R("share_otp_or_code", "codul primit prin SMS", "secret_credential", "codul primit prin SMS la acest numar")]),
    "S15": M("ordinary_or_legitimate", sender="E.ON", stype="telecom_or_utility"),
    "S16": M("likely_scam", "remote_access", sender="Microsoft Support", stype="tech_support", reqs=[
        R("install_or_grant_access", "AnyDesk și ID-ul", "device_or_account_control", "Descarca instrumentul de diagnostic AnyDesk si da-i tehnicianului ID-ul"),
        R("pay_fee", "99 lei", "financial_asset", "Sesiunea costa 99 lei")],
        tac=[("fear", "Calculatorul tau trimite erori de securitate")]),
    "S17": M("ordinary_or_legitimate", sender="Revolut", stype="bank"),
    "S18": M("likely_scam", "advance_fee", reqs=[
        R("transfer_money", "comision 300 lei", "financial_asset", "imi platesti comisionul de 300 lei in contul RO11INGB0000999900001111",
          dest="RO11INGB0000999900001111")],
        dep="Contractul ti-l trimit dupa ce imi platesti comisionul de 300 lei", pro=[("money_or_prize", "Iti ofer un credit de 20.000 lei fara verificare")]),
    "S19": M("protective_or_educational", sender="Politia Romana", stype="government", reqs=[
        R("transfer_money", "bani", "financial_asset", "cer bani pentru a 'rezolva' un dosar", stance="reported_or_quoted", handover=KEEP)],
        prot=[("security_warning", "Nicio institutie nu cere bani prin telefon")]),
    "S20": M("likely_scam", "institution_impersonation", sender="Politia Romana", stype="government", reqs=[
        R("pay_fee", "cauțiune", "financial_asset", "contactati urgent agentul Popa pe WhatsApp la 0766 222 333 si achitati cautiunea", dest="0766 222 333")],
        thr=[("legal_or_fine", "Pe numele dvs. a fost deschis un dosar penal")], tac=[("urgency", "contactati urgent")]),
    "S21": M("ordinary_or_legitimate", sender="Mega Image", stype="retailer_or_marketplace", reqs=[
        R("other", "cod de ridicare", "low", "cu codul de ridicare 8841", stance="provided_to_recipient", handover=KEEP)]),
    "S22": M("likely_scam", "card_data_theft", sender="Mega Image", stype="retailer_or_marketplace", reqs=[
        R("share_card_data", "numărul cardului și CVV", "secret_credential", "introdu numarul cardului si codul CVV",
          dest="https://mega-image.voucher-ro.xyz")],
        pro=[("money_or_prize", "Ai castigat un voucher de 300 lei")], tac=[("urgency", "in 24 de ore")]),
    "S23": M("ordinary_or_legitimate", stype="employer_or_recruiter", lang="en"),
    "S24": M("likely_scam", "other_suspicious_mechanism", sender="CEO", stype="employer_or_recruiter", lang="en", reqs=[
        R("buy_or_subscribe", "carduri cadou Google Play", "financial_asset", "buy 5 Google Play gift cards of 100 EUR"),
        R("other", "codurile cardurilor", "financial_asset", "Send me the codes here")],
        tac=[("authority", "it's the CEO"), ("secrecy", "keep this between us"), ("urgency", "for a client today")]),
}
