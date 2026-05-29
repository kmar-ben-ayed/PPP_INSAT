import requests
import time
import statistics
import json
import threading
import subprocess
import sys
from datetime import datetime


BASE_URL  = "http://localhost:8000/chat"

QUESTIONS = [
    "Quelles sont les dates d'inscription au TRYSP ?",
    "Où se déroule l'événement TRYSP ?",
    "Comment contacter le comité organisateur ?",
    "Y a-t-il des opportunités de networking ?",
    "Quels sont les thèmes des panels ?",
]

def get_gpu_stats() -> dict:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True, text=True, timeout=5
        )
        parts = result.stdout.strip().split(", ")
        return {
            "gpu_util":    int(parts[0]),
            "vram_used":   int(parts[1]),
            "vram_total":  int(parts[2]),
            "temperature": int(parts[3])
        }
    except Exception:
        return {"gpu_util": 0, "vram_used": 0, "vram_total": 0, "temperature": 0}

def simulate_user(user_id: int, question: str, results: list, lock: threading.Lock):
    t0     = time.time()
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
            "latency":  round(latency, 2),
            "status":   status,
            "answer":   answer[:60] + "..." if len(answer) > 60 else answer
        })
        print(f"    [User {user_id:02d}] {status:8s} — {latency:.2f}s")

def run_concurrent_test(n_users: int, mode_label: str) -> dict:
    print(f"\n  → {n_users} utilisateur(s) simultané(s)")

    gpu_before = get_gpu_stats()
    results    = []
    lock       = threading.Lock()
    threads    = []

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

    gpu_after = get_gpu_stats()

    successful = [r for r in results if r["status"] == "success"]
    latencies  = [r["latency"] for r in successful]

    return {
        "mode":            mode_label,
        "n_users":         n_users,
        "total_time":      round(t_total, 2),
        "success_count":   len(successful),
        "failure_count":   n_users - len(successful),
        "success_rate":    round(len(successful) / n_users * 100, 1),
        "latence_moyenne": round(statistics.mean(latencies), 2)   if latencies else None,
        "latence_max":     round(max(latencies), 2)               if latencies else None,
        "latence_min":     round(min(latencies), 2)               if latencies else None,
        "gpu_util_avant":  gpu_before["gpu_util"],
        "gpu_util_apres":  gpu_after["gpu_util"],
        "vram_used_mb":    gpu_after["vram_used"],
        "temperature_c":   gpu_after["temperature"]
    }

def run_full_benchmark(mode_label: str) -> list:
    print(f"\n{'='*60}")
    print(f"MODE : {mode_label}")
    print(f"{'='*60}")

    gpu_stats = get_gpu_stats()
    print(f"  GPU actuel : {gpu_stats['vram_used']}MB VRAM utilisés, "
          f"{gpu_stats['gpu_util']}% utilisation")

    scenarios = [1, 3, 5, 10]
    results   = []

    for n in scenarios:
        summary = run_concurrent_test(n, mode_label)
        results.append(summary)
        if n != scenarios[-1]:
            print(f"  Pause 5s...")
            time.sleep(5)

    return results

def print_comparison_table(cpu_results: list, gpu_results: list):
    print(f"\n{'='*70}")
    print("COMPARAISON CPU vs GPU — Impact de la charge")
    print(f"{'='*70}")
    print(f"{'Users':<6} {'CPU Lat.Moy':>12} {'CPU Lat.Max':>12} "
          f"{'GPU Lat.Moy':>12} {'GPU Lat.Max':>12} {'Gain':>8}")
    print("-" * 70)

    for cpu, gpu in zip(cpu_results, gpu_results):
        cpu_moy = cpu["latence_moyenne"] or 0
        gpu_moy = gpu["latence_moyenne"] or 0
        gain    = round((cpu_moy - gpu_moy) / cpu_moy * 100, 1) if cpu_moy > 0 else 0

        print(f"{cpu['n_users']:<6} "
              f"{str(cpu_moy)+'s':>12} "
              f"{str(cpu['latence_max'])+'s':>12} "
              f"{str(gpu_moy)+'s':>12} "
              f"{str(gpu['latence_max'])+'s':>12} "
              f"{gain:>7}%")

    print(f"{'='*70}")

if __name__ == "__main__":
    print("=" * 60)
    print("BENCHMARK GPU vs CPU — Approche B")
    print(f"Modèle  : qwen2.5:1.5b")
    print(f"GPU     : NVIDIA GeForce RTX 3050 6GB")
    print(f"Date    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    
    print("\n*** PHASE 1 : Mode CPU ***")
    print("Configure Ollama pour forcer le CPU...")
    print("  → Définis OLLAMA_GPU_LAYERS=0 et redémarre Ollama manuellement")
    print("  → Appuie sur ENTRÉE quand Ollama est redémarré en mode CPU")
    input()

    cpu_results = run_full_benchmark("CPU")


    print("\n*** PHASE 2 : Mode GPU ***")
    print("Configure Ollama pour utiliser le GPU...")
    print("  → Définis OLLAMA_GPU_LAYERS=99 et redémarre Ollama")
    print("  → Appuie sur ENTRÉE quand Ollama est redémarré en mode GPU")
    input()

    gpu_results = run_full_benchmark("GPU (RTX 3050)")


    print_comparison_table(cpu_results, gpu_results)

    
    output = {
        "date":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "modele":      "qwen2.5:1.5b",
        "gpu":         "NVIDIA GeForce RTX 3050 6GB",
        "cpu_results": cpu_results,
        "gpu_results": gpu_results
    }
    with open("resultats_gpu_vs_cpu.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\nRésultats sauvegardés dans resultats_gpu_vs_cpu.json")