import sys
from pathlib import Path
import benchmark_nli as bench_nli

alternates = {
    "request_money": "Destinatarului i se cere să vireze bani.",
    "request_credentials": "Expeditorul vrea ca destinatarul să îi comunice date secrete de autentificare.",
    "request_sensitive_documents": "Destinatarului i se cere să trimită o copie a unui act de identitate.",
    "request_card_photo": "Destinatarului i se cere să trimită o poză cu datele cardului bancar.",
    "promise_payout": "Mesajul spune că destinatarul urmează să primească bani.",
    "advance_fee_condition": "Pentru a primi banii promiși, destinatarul trebuie mai întâi să plătească o taxă.",
    "family_impersonation": "Expeditorul spune că este o rudă și că și-a schimbat numărul de telefon.",
    "organization_impersonation_claim": "Expeditorul susține că scrie în numele unei organizații.",
    "account_verification_request": "Destinatarului i se cere să își verifice sau să își confirme contul.",
    "urgency_or_pressure": "Mesajul pune presiune pe destinatar să acționeze repede.",
    "protective_warning": "Mesajul îl avertizează pe destinatar să păstreze secrete datele de autentificare sau ale cardului.",
    "educational_example": "Mesajul citează o tentativă de înșelăciune ca exemplu didactic.",
    "commercial_solicitation": "Mesajul face reclamă unui produs de vânzare.",
    "reward_offer": "Mesajul promite un produs gratuit sau un premiu.",
    "unavailable_for_call": "Expeditorul spune că nu poate vorbi la telefon în acest moment.",
}
bench_nli.HYPOTHESES = {label: (original[0], alternates[label]) for label, original in bench_nli.HYPOTHESES.items()}
path = Path(sys.argv[1])
bench_nli.run(path, [1])
(path.parent / f"{path.name}-ro.json").rename(path.parent / f"{path.name}-alt.json")
