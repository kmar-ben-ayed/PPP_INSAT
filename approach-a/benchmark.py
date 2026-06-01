"""
benchmark.py
─────────────────────────────────────────────────────────────────────────────
Benchmark the INSAT FAQ chatbot running on Hugging Face Spaces.

Measures:
  • Latency per question (and p50 / p95 across the suite)
  • Keyword-hit accuracy (simple but fast proxy for answer correctness)

Install dependency (once):
    pip install gradio_client

Run:
    python benchmark.py

Results are printed to the terminal and saved to benchmark_results.json.
─────────────────────────────────────────────────────────────────────────────
"""

import json
import time
import statistics
from datetime import datetime
from pathlib import Path
from gradio_client import Client

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG  ← change these two lines before running
# ─────────────────────────────────────────────────────────────────────────────
SPACE_URL = "elyes0007/phi3-mini-chat"
HF_TOKEN  = None       # set to "hf_xxxxxxxxxxxx" if your Space is private
# ─────────────────────────────────────────────────────────────────────────────


DATASET_PATH = Path(__file__).parent / "data" / "benchmark_dataset.json"
RESULTS_PATH = Path("benchmark_results.json")
CONSISTENCY_RUNS = 1  # >1 = re-run each question to measure consistency
TOKENIZER_NAME = "HuggingFaceTB/SmolLM2-1.7B-Instruct"


def _load_dataset(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        dataset = json.load(fh)
    if not isinstance(dataset, list):
        raise ValueError("Dataset must be a JSON array")
    return dataset


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _tokenize(text: str) -> list[str]:
    return [t for t in _normalize(text).replace("\n", " ").split(" ") if t]


def _lcs_len(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    rows = len(a) + 1
    cols = len(b) + 1
    dp = [[0] * cols for _ in range(rows)]
    for i in range(1, rows):
        for j in range(1, cols):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[-1][-1]


def _rouge_l(reference: str, candidate: str) -> float:
    ref_tokens = _tokenize(reference)
    cand_tokens = _tokenize(candidate)
    if not ref_tokens or not cand_tokens:
        return 0.0
    lcs = _lcs_len(ref_tokens, cand_tokens)
    recall = lcs / len(ref_tokens)
    precision = lcs / len(cand_tokens)
    if recall + precision == 0:
        return 0.0
    return (2 * recall * precision) / (recall + precision)


def _bleu_1(reference: str, candidate: str) -> float:
    ref_tokens = _tokenize(reference)
    cand_tokens = _tokenize(candidate)
    if not cand_tokens:
        return 0.0
    ref_counts = {}
    for t in ref_tokens:
        ref_counts[t] = ref_counts.get(t, 0) + 1
    match = 0
    for t in cand_tokens:
        if ref_counts.get(t, 0) > 0:
            match += 1
            ref_counts[t] -= 1
    precision = match / len(cand_tokens)
    bp = 1.0
    if len(cand_tokens) < len(ref_tokens):
        bp = pow(2.718281828, 1 - (len(ref_tokens) / max(1, len(cand_tokens))))
    return bp * precision


def _get_token_count(text: str) -> int:
    try:
        from transformers import AutoTokenizer
        if not hasattr(_get_token_count, "_tok"):
            _get_token_count._tok = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
        return len(_get_token_count._tok.encode(text))
    except Exception:
        return len(_tokenize(text))


def _is_out_of_scope(reference: str) -> bool:
    return "not available in the faq" in _normalize(reference)


def _response_is_out_of_scope(response: str) -> bool:
    return "not available in the faq" in _normalize(response)


def run_benchmark() -> None:
    dataset = _load_dataset(DATASET_PATH)
    print(f"\n🔗  Connecting to {SPACE_URL} …")
    client = Client(SPACE_URL, token=HF_TOKEN)
    print("✅  Connected\n")

    total = len(dataset)
    bar   = "═" * 72

    print(bar)
    print(f"  INSAT FAQ Chatbot — Benchmark   ({total} questions)")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(bar)

    results = []

    for i, test in enumerate(dataset, start=1):
        question = test.get("question", "").strip()
        reference = test.get("reference_answer", "").strip()
        category = test.get("category", "")
        expected_oos = _is_out_of_scope(reference)

        print(f"\n[{i:02d}/{total}]  Q: {question}")

        if not question:
            results.append({
                "index": i,
                "question": "",
                "reference_answer": reference,
                "response": "ERROR: empty question",
                "category": category,
                "latency_ms": None,
                "bleu": 0.0,
                "rouge_l": 0.0,
                "throughput_tokens_per_sec": 0.0,
                "out_of_scope": expected_oos,
                "consistent": None,
                "error": True,
            })
            continue

        # ── Call the Space ──
        responses = []
        latencies = []
        error = False
        for _ in range(max(1, CONSISTENCY_RUNS)):
            t0 = time.perf_counter()
            try:
                response: str = client.predict(
                    question,
                    "[]",              # fresh conversation per question
                    api_name="/chat",
                )
            except Exception as exc:
                print(f"        ❌  Request failed: {exc}")
                responses.append(f"ERROR: {exc}")
                latencies.append(None)
                error = True
                break
            latency = time.perf_counter() - t0
            responses.append(response)
            latencies.append(latency)

        if error:
            results.append({
                "index": i,
                "question": question,
                "reference_answer": reference,
                "response": responses[0],
                "category": category,
                "latency_ms": None,
                "bleu": 0.0,
                "rouge_l": 0.0,
                "throughput_tokens_per_sec": 0.0,
                "out_of_scope": expected_oos,
                "consistent": False if CONSISTENCY_RUNS > 1 else None,
                "error": True,
            })
            continue

        response = responses[0]
        latency_ms = statistics.mean([l for l in latencies if l is not None]) * 1000
        token_count = _get_token_count(response)
        throughput = token_count / max(1e-9, (latency_ms / 1000))
        bleu = _bleu_1(reference, response)
        rouge = _rouge_l(reference, response)
        predicted_oos = _response_is_out_of_scope(response)
        consistent = None
        if CONSISTENCY_RUNS > 1:
            normalized = [_normalize(r) for r in responses]
            consistent = all(n == normalized[0] for n in normalized[1:])

        # ── Pretty-print ──
        preview = response[:110] + ("…" if len(response) > 110 else "")
        print(f"        A: {preview}")
        print(f"        ⏱  {latency_ms:.0f}ms  |  BLEU {bleu:.3f}  ROUGE-L {rouge:.3f}")

        results.append({
            "index": i,
            "question": question,
            "reference_answer": reference,
            "response": response,
            "category": category,
            "latency_ms": round(latency_ms, 1),
            "bleu": round(bleu, 4),
            "rouge_l": round(rouge, 4),
            "throughput_tokens_per_sec": round(throughput, 2),
            "out_of_scope": predicted_oos,
            "consistent": consistent,
            "error": False,
        })

    # ── Aggregate stats (skip failed requests) ────────────────────────────
    ok_results = [r for r in results if not r["error"]]

    print(f"\n{bar}")
    print("  📊  BENCHMARK SUMMARY")
    print(bar)

    if ok_results:
        latencies_ms = [r["latency_ms"] for r in ok_results if r["latency_ms"] is not None]
        lat_sorted = sorted(latencies_ms)

        avg_lat = statistics.mean(latencies_ms)
        p50_lat = statistics.median(latencies_ms)
        p95_idx = max(0, int(len(lat_sorted) * 0.95) - 1)
        p95_lat = lat_sorted[p95_idx]
        min_lat = min(latencies_ms)
        max_lat = max(latencies_ms)

        avg_bleu = statistics.mean(r["bleu"] for r in ok_results)
        avg_rouge = statistics.mean(r["rouge_l"] for r in ok_results)
        avg_tp = statistics.mean(r["throughput_tokens_per_sec"] for r in ok_results)
        oos_rate = (
            sum(1 for r in ok_results if r["out_of_scope"]) / len(ok_results)
            if ok_results else 0.0
        )
        consistency_rate = None
        if CONSISTENCY_RUNS > 1:
            consistency_rate = (
                sum(1 for r in ok_results if r.get("consistent")) / len(ok_results)
                if ok_results else 0.0
            )

        print(f"  Questions run       : {len(results)}")
        print(f"  Successful          : {len(ok_results)}   Failed: {len(results) - len(ok_results)}")
        print(f"  ─")
        print(f"  BLEU                : {avg_bleu:.4f}")
        print(f"  ROUGE-L             : {avg_rouge:.4f}")
        print(f"  Latency  min        : {min_lat:.1f}ms")
        print(f"  Latency  avg        : {avg_lat:.1f}ms")
        print(f"  Latency  p50        : {p50_lat:.1f}ms")
        print(f"  Latency  p95        : {p95_lat:.1f}ms")
        print(f"  Latency  max        : {max_lat:.1f}ms")
        print(f"  TTFT (ms)           : n/a (non-streaming /chat)")
        print(f"  Throughput (tok/s)  : {avg_tp:.2f}")
        print(f"  Out-of-scope rate   : {oos_rate:.4f}")
        if consistency_rate is not None:
            print(f"  Consistency rate    : {consistency_rate:.4f}")
    else:
        print("  All requests failed — check SPACE_URL and your HF token.")

    print(bar)

    # ── Save full report ──────────────────────────────────────────────────
    report = {
        "space_url":   SPACE_URL,
        "timestamp":   datetime.now().isoformat(),
        "dataset_path": str(DATASET_PATH),
        "consistency_runs": CONSISTENCY_RUNS,
        "total":       len(results),
        "successful":  len(ok_results),
        "results":     results,
    }
    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  💾  Full report saved to {RESULTS_PATH}\n")


if __name__ == "__main__":
    run_benchmark()
