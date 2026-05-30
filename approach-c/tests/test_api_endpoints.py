"""End-to-end tests for API endpoints and metrics."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from nltk import data
import pytest
import requests

from src import api_server
from src.faq_responder import AnswerResult
from src.metrics_tracker import MetricsTracker


FAQ_CONTEXT = {
    "club_name": "TRYSP",
    "lang": "fr",
    "faq": [
        {
            "q": "Quand ont lieu les entrainements ?",
            "a": "Chaque lundi a 18h.",
            "category": "logistique",
        }
    ],
}


@pytest.fixture()
def api_base_url(monkeypatch: pytest.MonkeyPatch) -> str:
    fresh_state = api_server.AppState(metrics=MetricsTracker())
    monkeypatch.setattr(api_server, "STATE", fresh_state)

    server = api_server.ThreadingHTTPServer(("127.0.0.1", 0), api_server.APIHandler)
    api_server.STATE.metrics.set_cold_start_ms(5.0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    time.sleep(0.05)
    yield base_url
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_chat_and_metrics_with_ttft(api_base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call(_: str, __: str) -> tuple[str, float]:
        return "Reponse de test.", 12.5

    monkeypatch.setattr("src.faq_responder._call_approach_c", fake_call)

    payload = {
        "question": "Quand ont lieu les entrainements ?",
        "context": FAQ_CONTEXT,
        "approach": "C",
        "lang": "fr",
        "model": "stub",
    }
    response = requests.post(f"{api_base_url}/chat", json=payload, timeout=5)
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Reponse de test."
    assert data["latency_ms"] > 0

    metrics = requests.get(f"{api_base_url}/metrics", timeout=5).json()
    assert metrics["ttft_ms"] == pytest.approx(12.5, abs=0.01)
    assert metrics["uptime_percent"] >= 99.0
    assert metrics["cost_eur"] == 0.0


def test_benchmark_endpoint_returns_metrics(api_base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call(_: str, __: str) -> tuple[str, float]:
        return "Chaque lundi a 18h.", 8.0

    monkeypatch.setattr("src.faq_responder._call_approach_c", fake_call)

    payload = {
        "dataset": [
            {
                "question": "Quand ont lieu les entrainements ?",
                "reference_answer": "Chaque lundi a 18h.",
                "category": "logistique",
            }
        ],
        "context": FAQ_CONTEXT,
        "approach": "C",
        "consistency_runs": 1,
    }
    response = requests.post(f"{api_base_url}/benchmark", json=payload, timeout=10)
    assert response.status_code == 200
    data = response.json()
    # These should be exactly 1.0 — answer == reference, exact match
    assert data["bleu"] == pytest.approx(1.0, abs=0.01)
    assert data["rouge_l"] == pytest.approx(1.0, abs=0.01)

    # These are legitimately 0 when the answer is correct and in-scope
    assert data["hallucination_rate"] == 0.0
    assert data["out_of_scope_rate"] == 0.0

    # These should be 1.0 — answer is in context, french question gets french answer
    assert data["contextual_relevance_rate"] == pytest.approx(1.0, abs=0.01)
    assert data["lang_accuracy"] == pytest.approx(1.0, abs=0.01)

    # These must be positive
    assert data["avg_latency_ms"] > 0
    assert data["ttft_ms"] == pytest.approx(8.0, abs=0.1)
    assert data["throughput_tokens_per_sec"] > 0

    assert data["consistency_rate"] is None  # runs=1 means untested

def test_chat_rate_limit_returns_429(api_base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_server, "_is_rate_limited", lambda _: True)

    payload = {
        "question": "Quand ont lieu les entrainements ?",
        "context": FAQ_CONTEXT,
        "approach": "C",
        "lang": "fr",
    }
    response = requests.post(f"{api_base_url}/chat", json=payload, timeout=5)
    assert response.status_code == 429
    assert response.json()["error"] == "Rate limit reached for approach C."


def test_concurrent_requests_recorded(
    api_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def slow_answer(*_: object, **__: object) -> AnswerResult:
        time.sleep(0.2)
        return AnswerResult(
            answer="OK",
            matched_entry=None,
            similarity=0.0,
            out_of_scope=False,
            ttft_ms=5.0,
        )

    monkeypatch.setattr(api_server, "generate_answer", slow_answer)

    payload = {
        "question": "Quand ont lieu les entrainements ?",
        "context": FAQ_CONTEXT,
        "approach": "C",
        "lang": "fr",
    }

    concurrent_requests = 8

    with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = [
            executor.submit(
                requests.post,
                f"{api_base_url}/chat",
                json=payload,
                timeout=5,
            )
            for _ in range(concurrent_requests)
        ]

        for future in futures:
            response = future.result()
            assert response.status_code == 200

    metrics = requests.get(f"{api_base_url}/metrics", timeout=5).json()

    assert metrics["concurrent_requests_handled"] >= concurrent_requests


def test_rate_limit_window_resets(api_base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def fast_call(_: str, __: str) -> tuple[str, float]:
        return "OK", 1.0

    monkeypatch.setattr("src.faq_responder._call_approach_c", fast_call)
    monkeypatch.setattr(api_server, "RATE_LIMIT_MAX_REQUESTS", 2)
    monkeypatch.setattr(api_server, "RATE_LIMIT_WINDOW_SECONDS", 0.2)

    payload = {
        "question": "Quand ont lieu les entrainements ?",
        "context": FAQ_CONTEXT,
        "approach": "C",
        "lang": "fr",
    }

    assert requests.post(f"{api_base_url}/chat", json=payload, timeout=5).status_code == 200
    assert requests.post(f"{api_base_url}/chat", json=payload, timeout=5).status_code == 200
    assert requests.post(f"{api_base_url}/chat", json=payload, timeout=5).status_code == 429

    time.sleep(0.25)
    assert requests.post(f"{api_base_url}/chat", json=payload, timeout=5).status_code == 200


def test_cold_start_metric_persists(api_base_url: str) -> None:
    metrics = requests.get(f"{api_base_url}/metrics", timeout=5).json()
    assert metrics["cold_start_ms"] == pytest.approx(5.0, abs=0.01)


def test_latency_and_throughput_over_20_requests(
    api_base_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def slow_answer(*_: object, **__: object) -> AnswerResult:
        time.sleep(0.03)
        return AnswerResult(
            answer="OK OK",
            matched_entry=None,
            similarity=0.0,
            out_of_scope=False,
            ttft_ms=3.0,
        )

    monkeypatch.setattr(api_server, "generate_answer", slow_answer)

    payload = {
        "question": "Quand ont lieu les entrainements ?",
        "context": FAQ_CONTEXT,
        "approach": "C",
        "lang": "fr",
    }

    for _ in range(20):
        response = requests.post(f"{api_base_url}/chat", json=payload, timeout=5)
        assert response.status_code == 200

    metrics = requests.get(f"{api_base_url}/metrics", timeout=5).json()
    assert metrics["avg_latency_ms"] >= 20.0
    assert metrics["avg_latency_ms"] <= 2000.0
    assert metrics["throughput_tokens_per_sec"] > 5.0


def test_high_concurrency_burst(api_base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def slow_answer(*_: object, **__: object) -> AnswerResult:
        time.sleep(0.1)
        return AnswerResult(
            answer="OK",
            matched_entry=None,
            similarity=0.0,
            out_of_scope=False,
            ttft_ms=5.0,
        )

    monkeypatch.setattr(api_server, "generate_answer", slow_answer)

    payload = {
        "question": "Quand ont lieu les entrainements ?",
        "context": FAQ_CONTEXT,
        "approach": "C",
        "lang": "fr",
    }

    burst = 8
    with ThreadPoolExecutor(max_workers=burst) as executor:
        futures = [
            executor.submit(
                requests.post,
                f"{api_base_url}/chat",
                json=payload,
                timeout=5,
            )
            for _ in range(burst)
        ]
        for future in futures:
            assert future.result().status_code == 200

    metrics = requests.get(f"{api_base_url}/metrics", timeout=5).json()
    assert metrics["concurrent_requests_handled"] >= burst