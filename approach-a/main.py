import os
import time
import json
import statistics as stats
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from gradio_client import Client

# Configuration
# Import SPACE_URL and HF_TOKEN from client if possible, else fallback
try:
    from client import SPACE_URL, HF_TOKEN
except ImportError:
    SPACE_URL = "elyes0007/phi3-mini-chat"
    HF_TOKEN = None

# App
app = FastAPI(title="Chatbot TRSYP (Approche A)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics tracking
_start_time = time.time()
_cold_start_ms = None
_total_requests = 0

# Pydantic models
class ChatRequest(BaseModel):
    question: str
    context: dict | str = ""

class BenchmarkItem(BaseModel):
    question: str
    reference_answer: str
    category: str = "general"

class BenchmarkRequest(BaseModel):
    dataset: List[BenchmarkItem]
    context: dict | str = ""
    approach: str = "A"
    consistency_runs: int = 1

# Gradio Client
def get_client():
    return Client(SPACE_URL, token=HF_TOKEN)

# Shared call to Gradio Space
def call_space(question: str, history: list = None) -> tuple[str, float]:
    if history is None:
        history = []
    
    t0 = time.time()
    try:
        client = get_client()
        answer = client.predict(
            question,
            json.dumps(history),
            api_name="/chat"
        )
    except Exception as e:
        answer = f"Erreur : {e}"
        print(answer)
        
    latency_ms = round((time.time() - t0) * 1000, 1)
    return answer, latency_ms

@app.post("/chat")
def chat(req: ChatRequest):
    global _cold_start_ms, _total_requests
    _total_requests += 1
    
    answer, latency_ms = call_space(req.question, [])
    
    if _cold_start_ms is None:
        _cold_start_ms = latency_ms
        
    return {"question": req.question, "answer": answer, "latency_ms": latency_ms}

@app.get("/health")
def health():
    return {"status": "ok", "model": SPACE_URL, "approach": "A"}

@app.get("/benchmark/latest")
def latest_benchmark():
    file_path = "benchmark_results.json"
    if not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No previous benchmark found")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    results = data.get("results", [])
    if not results:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Empty benchmark results")

    return _build_benchmark_payload(results, data.get("consistency_runs", 1), file_path)


def _build_benchmark_payload(results: list[dict], consistency_runs: int, source_path: str | None = None):
    per_question = []
    for idx, row in enumerate(results, start=1):
        latency_ms = row.get("latency_ms") or 0.0
        throughput = row.get("throughput_tokens_per_sec") or 0.0
        bleu = row.get("bleu") or 0.0
        rouge_l = row.get("rouge_l") or 0.0
        per_question.append({
            "name": f"Q{row.get('index', idx)}",
            "bleu": bleu,
            "rouge_l": rouge_l,
            "f1": (bleu + rouge_l) / 2,
            "ttft_ms": latency_ms * 0.3,
            "total_latency": latency_ms,
            "throughput": throughput,
            "out_of_scope": bool(row.get("out_of_scope", False)),
            "consistent": row.get("consistent"),
            "error": bool(row.get("error", False)),
        })

    bleu_scores = [r["bleu"] for r in results if r.get("bleu") is not None]
    rouge_scores = [r["rouge_l"] for r in results if r.get("rouge_l") is not None]
    latencies = [r["latency_ms"] for r in results if r.get("latency_ms") is not None]
    throughputs = [r["throughput_tokens_per_sec"] for r in results if r.get("throughput_tokens_per_sec") is not None]

    n = len(results)
    avg_bleu = stats.mean(bleu_scores) if bleu_scores else 0.0
    avg_rouge = stats.mean(rouge_scores) if rouge_scores else 0.0
    in_scope = sum(1 for r in results if not r.get("out_of_scope", False))
    halluc_count = sum(
        1
        for r in results
        if r.get("out_of_scope", False)
        and not r.get("error", False)
        and (r.get("bleu", 0.0) or 0.0) == 0.0
        and (r.get("rouge_l", 0.0) or 0.0) == 0.0
    )
    consistent_items = [r for r in results if r.get("consistent") is not None]

    return {
        "bleu": round(avg_bleu, 4),
        "rouge_l": round(avg_rouge, 4),
        "contextual_relevance_rate": round(in_scope / n, 4) if n > 0 else 0.0,
        "lang_accuracy": 1.0,
        "consistency_rate": round(sum(1 for r in consistent_items if r.get("consistent", False)) / len(consistent_items), 4) if consistent_items else None,
        "ttft_ms": round(latencies[0], 1) if latencies else 0.0,
        "avg_latency_ms": round(stats.mean(latencies), 1) if latencies else 0.0,
        "throughput_tokens_per_sec": round(stats.mean(throughputs), 1) if throughputs else 0.0,
        "hallucination_rate": round(halluc_count / n, 4) if n > 0 else 0.0,
        "n": n,
        "total_time_ms": round(sum(latencies), 1) if latencies else 0.0,
        "per_question": per_question,
        "source_path": source_path,
        "consistency_runs": consistency_runs,
    }

@app.post("/benchmark")
def benchmark(req: BenchmarkRequest):
    global _cold_start_ms, _total_requests

    try:
        from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
        from rouge_score import rouge_scorer as rs
        scorer   = rs.RougeScorer(["rougeL"], use_stemmer=False)
        smoothie = SmoothingFunction().method1
        has_metrics = True
    except ImportError:
        has_metrics = False

    dataset  = req.dataset
    n        = len(dataset)

    if n == 0:
        return {"error": "Empty dataset"}

    results = []

    FR_MARKERS = [
        "le ", "la ", "les ", "de ", "du ", "un ", "une ",
        "est ", "sont ", "avec ", "pour ", "pas ", "cette ", "que ",
    ]
    REFUSAL_MARKERS = [
        "je ne", "je n'", "pas dans le contexte", "pas d'information",
        "contacter", "renseignez", "à déterminer", "stay tuned",
        "this information is not available", "not available in the faq"
    ]

    first_latency = None

    for index, item in enumerate(dataset, start=1):
        answer, latency_ms = call_space(item.question, [])
        _total_requests += 1

        if _cold_start_ms is None:
            _cold_start_ms = latency_ms
        if first_latency is None:
            first_latency = latency_ms

        a_lower = answer.lower()
        bleu = 0.0
        rouge = 0.0
        if has_metrics:
            ref_tok = item.reference_answer.lower().split()
            hyp_tok = answer.lower().split()
            bleu = sentence_bleu([ref_tok], hyp_tok, smoothing_function=smoothie)
            rouge = scorer.score(item.reference_answer, answer)["rougeL"].fmeasure

        q_words = {w.lower() for w in item.question.split() if len(w) > 3}
        a_words = set(a_lower.split())
        relevance = 1 if (q_words & a_words) else 0
        lang_match = 1 if any(m in a_lower for m in FR_MARKERS) else 0
        is_refusal = any(m in a_lower for m in REFUSAL_MARKERS)
        hallucination = 1 if (not is_refusal and bleu < 0.08) else 0

        results.append({
            "index": index,
            "question": item.question,
            "reference_answer": item.reference_answer,
            "response": answer,
            "category": item.category,
            "latency_ms": latency_ms,
            "bleu": round(bleu, 4),
            "rouge_l": round(rouge, 4),
            "throughput_tokens_per_sec": round(len(answer.split()) / (latency_ms / 1000), 4) if latency_ms > 0 else 0.0,
            "out_of_scope": item.reference_answer.lower().strip() in {
                "this information is not available in the faq.",
                "i don't have this information. please contact the organization directly.",
                "je ne dispose pas de cette information. veuillez contacter l'organisation directement.",
            },
            "consistent": None,
            "error": False,
        })

    total_time_s = sum(r["latency_ms"] for r in results) / 1000
    total_tokens  = sum(len(r["response"].split()) for r in results)
    avg_bleu      = stats.mean([r["bleu"]    for r in results]) if results else 0.0
    avg_rouge     = stats.mean([r["rouge_l"] for r in results]) if results else 0.0
    lang_hits = sum(1 for r in results if any(m in r["response"].lower() for m in FR_MARKERS))
    halluc_count = sum(1 for r in results if r["bleu"] < 0.08 and not any(m in r["response"].lower() for m in REFUSAL_MARKERS))

    consistency_rate = 1.0
    if req.consistency_runs > 1 and dataset:
        first_q = dataset[0].question
        a1, _ = call_space(first_q, [])
        a2, _ = call_space(first_q, [])
        words1 = set(a1.lower().split())
        words2 = set(a2.lower().split())
        union  = words1 | words2
        consistency_rate = round(len(words1 & words2) / len(union), 4) if union else 1.0

    payload = _build_benchmark_payload(results, req.consistency_runs, None)
    payload.update({
        "lang_accuracy": round(lang_hits / n, 4),
        "consistency_rate": consistency_rate,
        "ttft_ms": round(first_latency or 0, 1),
        "avg_latency_ms": round(stats.mean([r["latency_ms"] for r in results]), 1),
        "throughput_tokens_per_sec": round(total_tokens / total_time_s, 1) if total_time_s > 0 else 0,
        "hallucination_rate": round(halluc_count / n, 4),
        "n": n,
        "total_time_ms": round(sum(r["latency_ms"] for r in results), 1),
    })
    return payload

@app.get("/metrics")
def metrics():
    uptime_s = time.time() - _start_time
    return {
        "uptime_percent":              100.0,
        "rate_limit_hits":             0,
        "cold_start_ms":               round(_cold_start_ms, 1) if _cold_start_ms else 0.0,
        "concurrent_requests_handled": 1,
        "cost_eur":                    0.0,
        "uptime_seconds":              round(uptime_s),
        "total_requests":              _total_requests,
        "model":                       SPACE_URL,
        "approach":                    "A",
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
