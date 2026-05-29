import requests
import time
import statistics
import json
import threading
from datetime import datetime


QUESTIONS = [
    "Quelles sont les dates d'inscription au TRYSP ?",
    "Où se déroule l'événement TRYSP ?",
    "Comment contacter le comité organisateur ?",
    "Y a-t-il des opportunités de networking ?",
    "Quels sont les thèmes des panels ?",
]

BASE_URL = "http://localhost:8000/chat"


def simulate_user(user_id: int, question: str, results: list, lock: threading.Lock):
    t0 = time.time()
    status = "success"
    answer = ""

    try:
        r = requests.post(
            BASE_URL,
            json={"question": question},
            timeout=120
        )
        r.raise_for_status()
        answer = r.json()["answer"]
    except requests.exceptions.Timeout:
        status = "timeout"
    except Exception as e:
        status = f"error: {e}"

    latency = time.time() - t0

    with lock:
        results.append({
            "user_id":  user_id,
            "question": question,
            "answer":   answer[:80] + "..." if len(answer) > 80 else answer,
            "latency":  round(latency, 2),
            "status":   status
        })
        print(f"  [User {user_id:02d}] {status} — {latency:.2f}s — {question[:45]}...")

def run_concurrent_test(n_users: int) -> dict:

    print(f"\n{'='*60}")
    print(f"TEST CONCURRENT — {n_users} utilisateur(s) simultané(s)")
    print(f"{'='*60}")

    results = []
    lock    = threading.Lock()
    threads = []

    for i in range(n_users):
        question = QUESTIONS[i % len(QUESTIONS)]  
        t = threading.Thread(
            target=simulate_user,
            args=(i + 1, question, results, lock)
        )
        threads.append(t)

   
    t_start = time.time()
    for t in threads:
        t.start()

  
    for t in threads:
        t.join()
    t_total = time.time() - t_start
    successful = [r for r in results if r["status"] == "success"]
    failed     = [r for r in results if r["status"] != "success"]
    latencies  = [r["latency"] for r in successful]

    summary = {
        "n_users":          n_users,
        "total_time":       round(t_total, 2),
        "success_count":    len(successful),
        "failure_count":    len(failed),
        "success_rate":     round(len(successful) / n_users * 100, 1),
        "latence_moyenne":  round(statistics.mean(latencies), 2)    if latencies else None,
        "latence_mediane":  round(statistics.median(latencies), 2)  if latencies else None,
        "latence_max":      round(max(latencies), 2)                if latencies else None,
        "latence_min":      round(min(latencies), 2)                if latencies else None,
    }

    print(f"\n  Résultats pour {n_users} utilisateur(s) :")
    print(f"  Temps total         : {summary['total_time']}s")
    print(f"  Succès / Échecs     : {summary['success_count']} / {summary['failure_count']}")
    print(f"  Taux de succès      : {summary['success_rate']}%")
    if latencies:
        print(f"  Latence moyenne     : {summary['latence_moyenne']}s")
        print(f"  Latence médiane     : {summary['latence_mediane']}s")
        print(f"  Latence max         : {summary['latence_max']}s")
        print(f"  Latence min         : {summary['latence_min']}s")

    return summary

if __name__ == "__main__":
    print("=" * 60)
    print("BENCHMARK CONCURRENT — Approche B (Ollama + Qwen2.5-1.5B)")
    print(f"Démarré le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    
    scenarios  = [1, 3, 5, 10]
    all_results = []

    for n in scenarios:
        summary = run_concurrent_test(n)
        all_results.append(summary)
        if n != scenarios[-1]:
            print(f"\n  Pause de 5s avant le prochain scénario...")
            time.sleep(5)

   
    print("\n" + "=" * 60)
    print("TABLEAU COMPARATIF — Impact de la charge")
    print("=" * 60)
    print(f"{'Users':<8} {'Lat.Moy':>10} {'Lat.Max':>10} {'Succès':>10} {'Taux':>8}")
    print("-" * 60)
    for r in all_results:
        lat_moy = f"{r['latence_moyenne']}s" if r['latence_moyenne'] else "N/A"
        lat_max = f"{r['latence_max']}s"     if r['latence_max']     else "N/A"
        print(f"{r['n_users']:<8} {lat_moy:>10} {lat_max:>10} "
              f"{r['success_count']:>6}/{r['n_users']:<3} {r['success_rate']:>7}%")

    output = {
        "approche":   "B - Ollama + Cloudflare",
        "modele":     "qwen2.5:1.5b",
        "date":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scenarios":  all_results
    }
    with open("resultats_concurrent_B.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\nRésultats sauvegardés dans resultats_concurrent_B.json")