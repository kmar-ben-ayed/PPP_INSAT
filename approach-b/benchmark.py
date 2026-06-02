import requests
import time
import statistics
import json
import threading
import psutil
import os
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

TEST_DATASET = [
    {
        "question": "Quelles sont les dates d'inscription au TRYSP ?",
        "reference_answer": "Les inscriptions sont ouvertes du 1er au 30 mars 2025."
    },
    {
        "question": "Où se déroule l'événement TRYSP ?",
        "reference_answer": "L'événement se déroule à l'INSAT, campus universitaire de Tunis."
    },
    {
        "question": "Comment contacter le comité organisateur ?",
        "reference_answer": "Par email : trysp@insat.tn ou via Instagram @trysp_insat."
    },
    {
        "question": "Y a-t-il des opportunités de networking ?",
        "reference_answer": "Oui, des sessions de networking sont prévues avec des recruteurs partenaires."
    },
    {
        "question": "Quels sont les thèmes des panels ?",
        "reference_answer": "Les panels couvrent l'IA, l'entrepreneuriat, le développement durable et les carrières tech."
    },
]

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

# ── Performance Helpers (TTFT & Throughput via stream) ──
def call_chat_stream(question: str):
    t0 = time.time()
    ttft = None
    
    # We call the Ollama API directly to measure TTFT since our /chat endpoint is not streaming.
    # We simulate what main.py does to get accurate token-level metrics.
    system_prompt = (
        "Tu es un assistant virtuel pour les clubs et événements de l'INSAT.\n"
        "Réponds uniquement en te basant sur le contexte fourni ci-dessous.\n\n"
        f"CONTEXTE FAQ :\n{FAQ_CONTEXT}"
    )
    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": question}
        ],
        "stream": True
    }
    
    answer_chunks = []
    try:
        with requests.post("http://localhost:11434/api/chat", json=payload, stream=True, timeout=60) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line:
                    if ttft is None:
                        ttft = time.time() - t0
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        answer_chunks.append(data["message"]["content"])
    except Exception as e:
        return f"Erreur: {e}", 0, 0
    
    total_latency = time.time() - t0
    if ttft is None:
        ttft = total_latency
        
    full_answer = "".join(answer_chunks)
    num_tokens = len(full_answer.split())
    
    # Throughput (tokens per second) after the first token
    generation_time = total_latency - ttft
    throughput = num_tokens / generation_time if generation_time > 0 else 0
    
    return full_answer, total_latency, ttft, throughput

# ── Quality Metrics ──
def compute_bleu(reference: str, hypothesis: str) -> float:
    ref_tokens = reference.lower().split()
    hyp_tokens = hypothesis.lower().split()
    smoothie = SmoothingFunction().method1
    return sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoothie)

def compute_rouge(reference: str, hypothesis: str):
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=False)
    scores = scorer.score(reference, hypothesis)
    return scores['rougeL'].fmeasure

def compute_f1_token_overlap(reference: str, hypothesis: str) -> float:
    ref_tokens = set(reference.lower().split())
    hyp_tokens = set(hypothesis.lower().split())
    if not ref_tokens or not hyp_tokens:
        return 0.0
    intersection = len(ref_tokens & hyp_tokens)
    precision = intersection / len(hyp_tokens)
    recall = intersection / len(ref_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)

def compute_answer_relevance(question: str, hypothesis: str) -> float:
    q_words = {w.lower() for w in question.split() if len(w) > 3}
    a_words = set(hypothesis.lower().split())
    # Return 1.0 if there is at least one keyword overlap, else 0.0
    return 1.0 if (q_words & a_words) else 0.0

# ── Reliability Metrics ──
def is_hallucination(bleu: float, f1: float, hypothesis: str) -> float:
    # Heuristic: Very low overlap + NOT a standard refusal
    refusals = ["je ne", "pas dans le contexte", "pas d'information", "contacter", "désolé"]
    hyp_lower = hypothesis.lower()
    is_refusal = any(r in hyp_lower for r in refusals)
    
    if bleu < 0.1 and f1 < 0.1 and not is_refusal:
        return 1.0 # Probable hallucination
    return 0.0

# ── Rate Limiting (Threading) ──
def simulate_concurrent_requests(n_users=5):
    print(f"\n[RATE LIMITING] Lancement de {n_users} requêtes simultanées...")
    success_count = 0
    lock = threading.Lock()
    
    def worker():
        nonlocal success_count
        try:
            r = requests.post("http://localhost:8000/chat", json={"question": "Test de charge"}, timeout=30)
            if r.status_code == 200:
                with lock:
                    success_count += 1
        except:
            pass

    threads = [threading.Thread(target=worker) for _ in range(n_users)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    print(f"  Succès : {success_count}/{n_users} ({success_count/n_users*100:.1f}%)")
    return success_count / n_users


if __name__ == "__main__":
    print("=" * 70)
    print("BENCHMARK COMPLET — Approche B (Ollama + Qwen2.5-1.5B)")
    print("=" * 70)

    # Track metrics
    metrics = {
        "latencies": [],
        "ttfts": [],
        "throughputs": [],
        "bleu": [],
        "rouge_l": [],
        "f1_overlap": [],
        "relevance": [],
        "hallucinations": [],
        "response_lengths": []
    }
    
    # 1. Main Quality & Performance Loop
    for i, item in enumerate(TEST_DATASET):
        print(f"\nQ{i+1}: {item['question']}")
        
        # Memory before
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / (1024 * 1024) # MB
        
        answer, latency, ttft, throughput = call_chat_stream(item["question"])
        
        # Memory after
        mem_after = process.memory_info().rss / (1024 * 1024) # MB
        
        # Compute scores
        bleu = compute_bleu(item["reference_answer"], answer)
        rouge = compute_rouge(item["reference_answer"], answer)
        f1 = compute_f1_token_overlap(item["reference_answer"], answer)
        relevance = compute_answer_relevance(item["question"], answer)
        hallucination = is_hallucination(bleu, f1, answer)
        resp_len = len(answer)
        
        # Store
        metrics["latencies"].append(latency)
        metrics["ttfts"].append(ttft)
        metrics["throughputs"].append(throughput)
        metrics["bleu"].append(bleu)
        metrics["rouge_l"].append(rouge)
        metrics["f1_overlap"].append(f1)
        metrics["relevance"].append(relevance)
        metrics["hallucinations"].append(hallucination)
        metrics["response_lengths"].append(resp_len)
        
        print(f"  Réponse : {answer[:75]}...")
        print(f"  TTFT : {ttft:.3f}s | Latence : {latency:.2f}s | Throughput : {throughput:.1f} tok/s")
        print(f"  BLEU : {bleu:.3f} | ROUGE-L : {rouge:.3f} | F1 : {f1:.3f}")

    # 2. Consistency Score
    print("\n[CONSISTENCY] Double vérification de la Q1...")
    q1 = TEST_DATASET[0]["question"]
    ans1, _, _, _ = call_chat_stream(q1)
    ans2, _, _, _ = call_chat_stream(q1)
    consistency_score = compute_f1_token_overlap(ans1, ans2)
    print(f"  F1 Overlap entre les 2 réponses : {consistency_score:.3f}")

    # 3. Rate Limiting Test
    rate_limit_success_rate = simulate_concurrent_requests(5)
    
    # 4. Final Memory Check
    final_mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

    # ── AGGREGATION ──
    print("\n" + "=" * 70)
    print("RÉSULTATS FINAUX")
    print("=" * 70)
    
    def avg(lst): return round(statistics.mean(lst), 4) if lst else 0.0

    results = {
        "approche": "B - Ollama + Cloudflare",
        "modele": "qwen2.5:1.5b",
        "quality": {
            "bleu_moyen": avg(metrics["bleu"]),
            "rouge_l_moyen": avg(metrics["rouge_l"]),
            "f1_overlap_moyen": avg(metrics["f1_overlap"]),
            "answer_relevance_rate": avg(metrics["relevance"]),
        },
        "performance": {
            "latence_moyenne_s": round(avg(metrics["latencies"]), 2),
            "ttft_moyen_s": round(avg(metrics["ttfts"]), 3),
            "throughput_moyen_tok_s": round(avg(metrics["throughputs"]), 1),
            "ram_usage_script_mb": round(final_mem, 1),
            "rate_limit_success_rate": rate_limit_success_rate
        },
        "reliability": {
            "hallucination_rate": avg(metrics["hallucinations"]),
            "consistency_score": round(consistency_score, 4),
            "response_length_moyen_chars": round(avg(metrics["response_lengths"]), 1)
        },
        "raw_metrics": metrics
    }
    
    print(json.dumps(results, indent=2, ensure_ascii=False))

    with open("resultats_benchmark_B.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nResultats sauvegardes dans resultats_benchmark_B.json")