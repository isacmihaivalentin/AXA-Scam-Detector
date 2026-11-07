# GDPR: informare și acord înainte de verificare

**Ce s-a adăugat**
- **Secțiunea „Protecția datelor personale (GDPR)”**, în josul paginii principale (`#gdpr`), înainte de subsol. Conține:
  - cine prelucrează datele;
  - ce date;
  - scopul și temeiul legal (consimțământ, art. 6 alin. (1) lit. a));
  - destinatarii (serverul AXA, Google Gemini, Google Web Risk dacă e configurat);
  - durata de păstrare;
  - drepturile utilizatorului, inclusiv plângerea la ANSPDCP;
  - starea acordului, cu butonul **Retrage acordul**.
- Link „Protecția datelor (GDPR)” în subsol și „Detalii GDPR” în caseta de verificare.
- **Fereastra de acord.** Apare la prima verificare, fie că e text, link, captură încărcată, trasă sau lipită, ori un exemplu. Apare pe ambele pagini, `/` și `/chat`, care folosesc același acord.
  - **„Sunt de acord, verifică”**: acordul se salvează pe dispozitiv cu data și versiunea (`axa_consent_v1`), iar verificarea continuă.
  - **„Nu sunt de acord”**, tasta Escape sau închiderea ferestrei: **nu se trimite nimic**, verificarea se oprește și textul rămâne doar pe dispozitiv. Refuzul nu se salvează, așa că acordul se cere din nou la următoarea încercare.
  - **„Citește mai întâi informarea completă”**: nu se trimite nimic, iar pagina duce la secțiunea GDPR.
  - Cele două butoane au aceeași greutate vizuală, ca să nu împingă spre „da”.
- Ce afișa pagina până acum nu s-a schimbat (verdict, scală, explicații). Detecția și API-ul sunt neschimbate.

**Verificat (Chromium headless, `tools/consent_check.js`): 18/18 PASS.** Testele confirmă că:
- nicio cerere nu ajunge la `/api/analyze*` înainte de „da”;
- refuzul, tasta Escape și „Citește mai întâi” nu trimit nimic;
- o captură refuzată nu se trimite;
- acordul continuă verificarea, nu se mai cere a doua oară și se poate retrage, după care fereastra reapare;
- acordul dat în chat este valabil și pe pagina principală.

Fereastra încape fără derulare orizontală la 320 și 1440 px, în ambele teme. Sweep-urile existente rulează cu acordul deja dat: 65 de rulări pe pagina principală și 34 în chat, toate fără probleme. 107 teste unitare OK.

**Limite (de rezolvat înainte de lansarea publică)**
- Textul informării este pregătit pentru prototip, **nu este o consultanță juridică**. Trebuie revizuit de un specialist în protecția datelor.
- **Datele operatorului** (denumire, adresă, contact DPO) sunt marcate pe pagină ca „se completează înainte de lansarea publică”.
- **Acordul e verificat în browser, nu pe server.** Cineva care apelează API-ul direct îl ocolește. În plus, înregistrarea acordului există doar pe dispozitivul utilizatorului, iar GDPR (art. 7 alin. (1)) cere ca operatorul să poată demonstra consimțământul. O soluție simplă: fiecare cerere trimite versiunea acordului, serverul refuză cererile fără el și păstrează un jurnal minimal (versiune + oră, fără text).
- Perioada de păstrare a jurnalelor tehnice ale serverului depinde de găzduire și trebuie stabilită concret.
