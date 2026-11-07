import argparse
import json
import math
import re
import resource
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HYPOTHESES = {
    "request_money": ("The sender asks the recipient to send money or make a payment.", "Expeditorul îi cere destinatarului să trimită bani sau să facă o plată."),
    "request_credentials": ("The sender asks the recipient to share their password, secret code or bank card details.", "Expeditorul îi cere destinatarului să divulge parola, un cod secret sau datele cardului."),
    "request_sensitive_documents": ("The sender asks the recipient to upload a copy of a sensitive identity document.", "Expeditorul cere să i se trimită o copie a unui act personal de identitate."),
    "request_card_photo": ("The sender asks for a photo or screenshot showing the recipient's bank card information.", "Expeditorul cere o fotografie sau o captură cu informațiile de pe cardul bancar al destinatarului."),
    "promise_payout": ("The message promises that the recipient will receive money.", "Mesajul îi promite destinatarului că va primi bani."),
    "advance_fee_condition": ("The sender says the recipient has to send money before they can receive a payout.", "Expeditorul spune că destinatarul trebuie să plătească înainte de a primi bani."),
    "family_impersonation": ("The sender claims to be a family member writing from a new phone number.", "Expeditorul pretinde că este o rudă care scrie de la un număr nou."),
    "organization_impersonation_claim": ("The sender presents themselves as a representative of a company or institution.", "Expeditorul se prezintă ca reprezentantul unei firme sau instituții."),
    "account_verification_request": ("The sender asks the recipient to verify activity on their account or confirm their account.", "Expeditorul cere destinatarului să verifice activitatea contului sau să își confirme contul."),
    "urgency_or_pressure": ("The sender asks the recipient to act urgently or within a short time limit.", "Expeditorul cere destinatarului să acționeze urgent sau într-un termen scurt."),
    "protective_warning": ("The sender warns the recipient not to share passwords, secret codes, or sensitive payment information.", "Expeditorul îi spune destinatarului să nu divulge parole, coduri secrete sau date bancare."),
    "educational_example": ("The text presents an example of a scam for illustration or education.", "Textul prezintă un exemplu de fraudă cu scop ilustrativ sau educativ."),
    "commercial_solicitation": ("The sender advertises a product or service and asks the recipient to buy it.", "Expeditorul face reclamă unui produs sau serviciu și cere destinatarului să îl cumpere."),
    "reward_offer": ("The sender offers the recipient a free gift or a reward.", "Expeditorul îi oferă destinatarului un cadou gratuit sau o recompensă."),
    "unavailable_for_call": ("The sender says they cannot talk on the phone.", "Expeditorul spune că nu poate vorbi la telefon."),
}
LOCAL = {"request_money", "request_credentials", "request_sensitive_documents", "request_card_photo",
         "protective_warning", "educational_example", "account_verification_request",
         "commercial_solicitation", "reward_offer"}

def memory():
    import sys
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2**20 if sys.platform == "darwin" else 2**10)

def run(model_path, languages):
    started = time.perf_counter()
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, use_fast=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_path, local_files_only=True, use_safetensors=True, trust_remote_code=False).to("cpu").eval()
    indices = {key.casefold(): value for key, value in model.config.label2id.items()}
    model_startup = time.perf_counter() - started
    rss_load = memory()
    zero_shot = pipeline("zero-shot-classification", model=model, tokenizer=tokenizer, device=-1)
    print("HF pipeline sanity", zero_shot("Îmi poți vira suma în cont, te rog?",
          candidate_labels=[HYPOTHESES["request_money"][1], HYPOTHESES["protective_warning"][1]],
          hypothesis_template="{}", multi_label=True), flush=True)

    cases = json.loads((ROOT / "observed.json").read_text()) + json.loads((ROOT / "smoke.json").read_text())
    for lang in languages:
        results, latencies = [], []
        for case in cases:
            t0 = time.perf_counter()
            text = case["text"]
            masked = re.sub(r"https?://\S+", "[link]", text)
            fragments = [part.strip() for part in re.split(r"[.!?\n]+", masked) if len(part.strip()) > 9][:7]
            def classify(entries, allowed):
                pairs = [(i, p, name, variants[lang]) for i, p in enumerate(entries)
                         for name, variants in HYPOTHESES.items() if name in allowed]
                output = [{} for _ in entries]
                for start in range(0, len(pairs), 16):
                    batch = pairs[start:start+16]
                    encoded = tokenizer([p for _, p, _, _ in batch], [h for _, _, _, h in batch],
                                        padding=True, truncation="only_first", max_length=256, return_tensors="pt")
                    with torch.inference_mode():
                        values = model(**encoded).logits.softmax(dim=-1).tolist()
                    for (i, _, name, _), probs in zip(batch, values):
                        output[i][name] = [round(probs[indices[label]], 5)
                                            for label in ("entailment", "neutral", "contradiction")]
                return output
            whole = classify([masked], HYPOTHESES)[0]
            clause = classify(fragments, LOCAL)
            elapsed = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed)
            want = case.get("want", [case.get("intent")])
            top = ", ".join(f"{label} {val[0]:.2f}" for label, val in
                            sorted(whole.items(), key=lambda x: -x[1][0])[:4])
            clause_max = {label: max((row[label][0] for row in clause), default=0) for label in LOCAL}
            print(f"{lang} {case['id']:24s} {elapsed:6.0f} ms expected {want} whole {top} "
                  f"clauses {sorted(clause_max.items(), key=lambda x:-x[1])[:3]}", flush=True)
            results.append(dict(id=case["id"], want=want, whole=whole, fragments=fragments,
                                clause=clause, ms=round(elapsed, 2)))
        measurement = dict(startup_s=round(model_startup, 3), peak_after_load_mib=round(rss_load, 1),
                           peak_end_mib=round(memory(), 1), median_ms=round(statistics.median(latencies), 1),
                           p95_ms=round(sorted(latencies)[math.ceil(0.95*len(latencies))-1], 1),
                           case_count=len(cases), torch_version=torch.__version__)
        print(measurement, flush=True)
        (ROOT / f"{Path(model_path).name}-{'ro' if lang else 'en'}.json").write_text(
            json.dumps({"measurement": measurement, "rows": results}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("model", type=Path)
    cli.add_argument("--language", choices=["ro", "en", "both"], default="both")
    args = cli.parse_args()
    run(args.model, [1, 0] if args.language == "both" else [int(args.language == "ro")])
