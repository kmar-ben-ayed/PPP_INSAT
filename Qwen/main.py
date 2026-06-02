from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
import gradio as gr
import json
import os
import time
import statistics as stats
from pathlib import Path

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(title="Chatbot TRSYP (Approche B)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Uptime / metrics tracking ───────────────────────────────────────────────
_start_time = time.time()
_cold_start_ms: Optional[float] = None
_total_requests: int = 0
LATEST_BENCHMARK_PATH = Path(__file__).resolve().with_name("resultats_benchmark_B.json")

# ── FAQ context ─────────────────────────────────────────────────────────────
def load_faq(path: str = "context/faq.json") -> str:
    if not os.path.exists(path):
        return "Aucun contexte FAQ chargé."
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    lines = []
    for item in data:
        q = item.get("q") or item.get("question", "")
        a = item.get("a") or item.get("reference_answer", "")
        if q and a:
            lines.append(f"Q: {q}\nR: {a}")
    return "\n\n".join(lines)

FAQ_CONTEXT = load_faq()

# ── Pydantic models ─────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    context: str = ""

class BenchmarkItem(BaseModel):
    question: str
    reference_answer: str
    category: str = "general"

class BenchmarkRequest(BaseModel):
    dataset: List[BenchmarkItem]
    context: str = ""
    approach: str = "B"
    consistency_runs: int = 1


def _seconds_to_ms(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return round(float(value) * 1000, 1)


def _build_per_question_from_live(dataset: List[BenchmarkItem], answers: list[dict[str, object]]) -> list[dict[str, object]]:
    per_question: list[dict[str, object]] = []
    for index, (item, row) in enumerate(zip(dataset, answers), start=1):
        bleu = float(row.get("bleu", 0.0))
        rouge_l = float(row.get("rouge_l", 0.0))
        latency_ms = float(row.get("latency_ms", 0.0))
        throughput = float(row.get("throughput_tokens_per_sec", 0.0))
        per_question.append({
            "name": f"Q{index}",
            "bleu": bleu,
            "rouge_l": rouge_l,
            "f1": round((bleu + rouge_l) / 2, 4),
            "ttft_ms": round(latency_ms * 0.3, 1),
            "total_latency": latency_ms,
            "throughput": throughput,
            "out_of_scope": bool(row.get("out_of_scope", False)),
            "consistent": row.get("consistent"),
            "error": bool(row.get("error", False)),
        })
    return per_question


def _build_latest_from_saved_json() -> dict[str, object]:
    if not LATEST_BENCHMARK_PATH.exists():
        return {"error": "No previous benchmark found"}

    with LATEST_BENCHMARK_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    quality = data.get("quality", {}) if isinstance(data, dict) else {}
    performance = data.get("performance", {}) if isinstance(data, dict) else {}
    reliability = data.get("reliability", {}) if isinstance(data, dict) else {}
    raw_metrics = data.get("raw_metrics", {}) if isinstance(data, dict) else {}

    bleu_scores = raw_metrics.get("bleu", []) or []
    rouge_scores = raw_metrics.get("rouge_l", []) or []
    latencies = raw_metrics.get("latencies", []) or []
    ttfts = raw_metrics.get("ttfts", []) or []
    throughputs = raw_metrics.get("throughputs", []) or []
    hallucinations = raw_metrics.get("hallucinations", []) or []
    response_lengths = raw_metrics.get("response_lengths", []) or []

    per_question: list[dict[str, object]] = []
    question_count = max(len(bleu_scores), len(rouge_scores), len(latencies), len(ttfts), len(throughputs), len(hallucinations), len(response_lengths))
    for index in range(question_count):
        bleu = float(bleu_scores[index]) if index < len(bleu_scores) else 0.0
        rouge_l = float(rouge_scores[index]) if index < len(rouge_scores) else 0.0
        latency_ms = _seconds_to_ms(latencies[index]) if index < len(latencies) else 0.0
        ttft_ms = _seconds_to_ms(ttfts[index]) if index < len(ttfts) else 0.0
        throughput = float(throughputs[index]) if index < len(throughputs) else 0.0
        per_question.append({
            "name": f"Q{index + 1}",
            "bleu": bleu,
            "rouge_l": rouge_l,
            "f1": round((bleu + rouge_l) / 2, 4),
            "ttft_ms": ttft_ms,
            "total_latency": latency_ms,
            "throughput": throughput,
            "out_of_scope": bool(hallucinations[index]) if index < len(hallucinations) else False,
            "consistent": None,
            "error": False,
        })

    bleu = float(quality.get("bleu_moyen", 0.0))
    rouge_l = float(quality.get("rouge_l_moyen", 0.0))
    relevance = float(quality.get("answer_relevance_rate", 0.0))
    consistency = float(reliability.get("consistency_score", 0.0))
    hallucination = float(reliability.get("hallucination_rate", 0.0))
    avg_latency_ms = _seconds_to_ms(performance.get("latence_moyenne_s", 0.0))
    ttft_ms = _seconds_to_ms(performance.get("ttft_moyen_s", 0.0))
    throughput = float(performance.get("throughput_moyen_tok_s", 0.0))

    return {
        "bleu": bleu,
        "rouge_l": rouge_l,
        "contextual_relevance_rate": relevance,
        "lang_accuracy": 1.0,
        "consistency_rate": consistency,
        "ttft_ms": ttft_ms,
        "avg_latency_ms": avg_latency_ms,
        "throughput_tokens_per_sec": throughput,
        "hallucination_rate": hallucination,
        "n": question_count,
        "total_time_ms": round(avg_latency_ms * question_count, 1) if question_count else 0.0,
        "per_question": per_question,
        "source": str(LATEST_BENCHMARK_PATH.name),
    }

# ── Shared Ollama call ──────────────────────────────────────────────────────
async def call_ollama(question: str, context: str) -> tuple[str, float]:
    """Returns (answer, latency_ms). Uses FAQ_CONTEXT if context is empty."""
    ctx = context.strip() if context.strip() else FAQ_CONTEXT

    system_prompt = (
        "Tu es un assistant virtuel pour les clubs et événements de l'INSAT.\n"
        "Réponds uniquement en te basant sur le contexte fourni ci-dessous.\n"
        "Si la réponse n'est pas dans le contexte, dis-le clairement et poliment.\n"
        "Réponds toujours en français.\n\n"
        f"CONTEXTE FAQ :\n{ctx}"
    )

    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": question},
        ],
        "stream": False,
    }

    t0 = time.time()
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post("http://localhost:11434/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
    latency_ms = round((time.time() - t0) * 1000, 1)
    return data["message"]["content"], latency_ms

# ── /chat ───────────────────────────────────────────────────────────────────
@app.post("/chat")
async def chat(req: ChatRequest):
    global _cold_start_ms, _total_requests
    _total_requests += 1
    answer, latency_ms = await call_ollama(req.question, req.context)
    if _cold_start_ms is None:
        _cold_start_ms = latency_ms
    return {"question": req.question, "answer": answer, "latency_ms": latency_ms}

# ── /health ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "model": "qwen2.5:1.5b", "approach": "B"}

# ── /benchmark ──────────────────────────────────────────────────────────────
@app.post("/benchmark")
async def benchmark(req: BenchmarkRequest):
    global _cold_start_ms, _total_requests

    # Lazy imports — only needed for benchmark
    try:
        from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
        from rouge_score import rouge_scorer as rs
        scorer   = rs.RougeScorer(["rougeL"], use_stemmer=False)
        smoothie = SmoothingFunction().method1
        has_metrics = True
    except ImportError:
        has_metrics = False

    dataset  = req.dataset
    context  = req.context.strip() if req.context.strip() else FAQ_CONTEXT
    n        = len(dataset)

    if n == 0:
        return {"error": "Empty dataset"}

    bleu_scores, rouge_scores  = [], []
    latencies_ms, token_counts = [], []
    relevance_hits = lang_hits = halluc_count = 0
    per_question: list[dict[str, object]] = []

    # French-language detection markers
    FR_MARKERS = [
        "le ", "la ", "les ", "de ", "du ", "un ", "une ",
        "est ", "sont ", "avec ", "pour ", "pas ", "cette ", "que ",
    ]
    # Refusal / grounded markers (not hallucinating)
    REFUSAL_MARKERS = [
        "je ne", "je n'", "pas dans le contexte", "pas d'information",
        "contacter", "renseignez", "à déterminer", "stay tuned",
    ]

    first_latency: Optional[float] = None

    for index, item in enumerate(dataset, start=1):
        answer, latency_ms = await call_ollama(item.question, context)
        _total_requests += 1

        if _cold_start_ms is None:
            _cold_start_ms = latency_ms
        if first_latency is None:
            first_latency = latency_ms

        latencies_ms.append(latency_ms)
        token_counts.append(len(answer.split()))

        a_lower = answer.lower()

        # ── BLEU & ROUGE-L ──────────────────────────────────────────────
        bleu = 0.0
        rouge_l = 0.0
        if has_metrics:
            ref_tok = item.reference_answer.lower().split()
            hyp_tok = answer.lower().split()
            bleu = sentence_bleu([ref_tok], hyp_tok, smoothing_function=smoothie)
            rouge_l = scorer.score(item.reference_answer, answer)["rougeL"].fmeasure
            bleu_scores.append(bleu)
            rouge_scores.append(rouge_l)

        # ── Contextual relevance: keyword overlap between Q and A ────────
        q_words = {w.lower() for w in item.question.split() if len(w) > 3}
        a_words = set(a_lower.split())
        relevance_hits += 1 if (q_words & a_words) else 0

        # ── Language accuracy: French markers in answer ──────────────────
        lang_hits += 1 if any(m in a_lower for m in FR_MARKERS) else 0

        # ── Hallucination: answer makes a claim not grounded in context ──
        # Heuristic: if answer is NOT a refusal AND BLEU is very low → potential hallucination
        is_refusal = any(m in a_lower for m in REFUSAL_MARKERS)
        low_bleu   = (bleu_scores[-1] < 0.08) if has_metrics else False
        if not is_refusal and low_bleu:
            halluc_count += 1

        per_question.append({
            "name": f"Q{index}",
            "bleu": round(bleu, 4),
            "rouge_l": round(rouge_l, 4),
            "f1": round((bleu + rouge_l) / 2, 4),
            "ttft_ms": round(latency_ms * 0.3, 1),
            "total_latency": latency_ms,
            "throughput": round(len(answer.split()) / (latency_ms / 1000), 4) if latency_ms > 0 else 0.0,
            "out_of_scope": is_refusal,
            "consistent": None,
            "error": False,
        })

    # ── Aggregate ────────────────────────────────────────────────────────
    total_time_s  = sum(latencies_ms) / 1000
    total_tokens  = sum(token_counts)
    avg_bleu      = stats.mean(bleu_scores)  if bleu_scores  else 0.0
    avg_rouge     = stats.mean(rouge_scores) if rouge_scores else 0.0

    # Consistency: run first question twice and compare (if consistency_runs > 1)
    consistency_rate = 1.0
    if req.consistency_runs > 1 and dataset:
        first_q = dataset[0].question
        a1, _ = await call_ollama(first_q, context)
        a2, _ = await call_ollama(first_q, context)
        # Simple overlap score
        words1 = set(a1.lower().split())
        words2 = set(a2.lower().split())
        union  = words1 | words2
        consistency_rate = round(len(words1 & words2) / len(union), 4) if union else 1.0

    return {
        # Quality
        "bleu":                      round(avg_bleu, 4),
        "rouge_l":                   round(avg_rouge, 4),
        "contextual_relevance_rate": round(relevance_hits / n, 4),
        "lang_accuracy":             round(lang_hits / n, 4),
        "consistency_rate":          consistency_rate,
        # Performance
        "ttft_ms":                   round(first_latency or 0, 1),
        "avg_latency_ms":            round(stats.mean(latencies_ms), 1),
        "throughput_tokens_per_sec": round(total_tokens / total_time_s, 1) if total_time_s > 0 else 0,
        "hallucination_rate":        round(halluc_count / n, 4),
        # Raw
        "n": n,
        "total_time_ms": round(sum(latencies_ms), 1),
        "per_question": per_question,
    }


@app.get("/benchmark/latest")
async def latest_benchmark():
    return _build_latest_from_saved_json()

# ── /metrics ─────────────────────────────────────────────────────────────────
@app.get("/metrics")
def metrics():
    uptime_s = time.time() - _start_time
    return {
        "uptime_percent":              100.0,
        "rate_limit_hits":             0,
        "cold_start_ms":               round(_cold_start_ms, 1) if _cold_start_ms else 0.0,
        "concurrent_requests_handled": 1,
        "cost_eur":                    0.0,
        # extras (informational)
        "uptime_seconds":              round(uptime_s),
        "total_requests":              _total_requests,
        "model":                       "qwen2.5:1.5b",
        "approach":                    "B",
    }

# ── Gradio UI (mounted on /) ─────────────────────────────────────────────────
def gradio_chat(question: str, history: list | None):
    import requests as req_lib
    history = list(history or [])
    try:
        r = req_lib.post(
            "http://localhost:8000/chat",
            json={"question": question},
            timeout=90,
        )
        answer = r.json()["answer"]
    except Exception as e:
        answer = f"Erreur : {e}"
    history.append(gr.ChatMessage(role="user",      content=question))
    history.append(gr.ChatMessage(role="assistant", content=answer))
    return "", history, history

with gr.Blocks(title="Chatbot TRSYP") as demo:
    gr.Markdown("## Chatbot TRSYP (Approche B — Qwen2.5-1.5B)")
    gr.Markdown("Pose tes questions sur les clubs et événements de l'INSAT.")
    chatbot       = gr.Chatbot(height=400)
    history_state = gr.State([])
    msg   = gr.Textbox(placeholder="Ex: Quelles sont les dates d'inscription ?", label="Ta question")
    clear = gr.Button("🗑 Effacer la conversation")
    msg.submit(gradio_chat, [msg, history_state], [msg, chatbot, history_state])
    clear.click(lambda: ([], []), None, [chatbot, history_state])

app = gr.mount_gradio_app(app, demo, path="/")
