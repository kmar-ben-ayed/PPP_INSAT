import requests
import time
import statistics
import json
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

def call_chat(question: str):
    t0 = time.time()
    r = requests.post(
        "http://localhost:8000/chat",
        json={"question": question},
        timeout=60
    )
    latency = time.time() - t0
    answer = r.json()["answer"]
    return answer, latency

def compute_bleu(reference: str, hypothesis: str) -> float:
    ref_tokens = reference.lower().split()
    hyp_tokens = hypothesis.lower().split()
    smoothie = SmoothingFunction().method1
    return sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoothie)

def compute_rouge(reference: str, hypothesis: str):
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=False)
    scores = scorer.score(reference, hypothesis)
    return scores['rougeL'].fmeasure


print("=" * 60)
print("BENCHMARK — Approche B (Ollama + Qwen2.5-1.5B)")
print("=" * 60)

latencies, bleu_scores, rouge_scores = [], [], []

for i, item in enumerate(TEST_DATASET):
    print(f"\nQuestion {i+1}: {item['question']}")
    answer, latency = call_chat(item["question"])
    bleu  = compute_bleu(item["reference_answer"], answer)
    rouge = compute_rouge(item["reference_answer"], answer)

    latencies.append(latency)
    bleu_scores.append(bleu)
    rouge_scores.append(rouge)

    print(f"  Réponse    : {answer[:100]}...")
    print(f"  Latence    : {latency:.2f}s")
    print(f"  BLEU       : {bleu:.4f}")
    print(f"  ROUGE-L    : {rouge:.4f}")


print("\n" + "=" * 60)
print("RÉSULTATS FINAUX — Approche B")
print("=" * 60)
print(f"Latence moyenne  : {statistics.mean(latencies):.2f}s")
print(f"Latence médiane  : {statistics.median(latencies):.2f}s")
print(f"Latence max      : {max(latencies):.2f}s")
print(f"BLEU moyen       : {statistics.mean(bleu_scores):.4f}")
print(f"ROUGE-L moyen    : {statistics.mean(rouge_scores):.4f}")
print("=" * 60)


results = {
    "approche": "B - Ollama + Cloudflare",
    "modele": "qwen2.5:1.5b",
    "latence_moyenne": round(statistics.mean(latencies), 2),
    "latence_mediane": round(statistics.median(latencies), 2),
    "latence_max": round(max(latencies), 2),
    "bleu_moyen": round(statistics.mean(bleu_scores), 4),
    "rouge_l_moyen": round(statistics.mean(rouge_scores), 4)
}
with open("resultats_benchmark_B.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nRésultats sauvegardés dans resultats_benchmark_B.json")