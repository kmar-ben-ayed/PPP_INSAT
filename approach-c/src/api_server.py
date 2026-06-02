"""HTTP API server exposing shared chatbot endpoints."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config import DEFAULT_FAQ_PATH, DEFAULT_MODEL
from src.benchmark import compute_benchmark_metrics
from src.faq_context import FAQContext, load_faq_context, parse_faq_context
from src.faq_responder import AnswerResult, count_tokens, generate_answer, infer_expected_lang
from src.metrics_tracker import MetricsTracker


@dataclass
class AppState:
    """Shared application state."""

    metrics: MetricsTracker
    last_approach: str = "C"
    last_model: str = DEFAULT_MODEL
    state_lock: threading.Lock = field(default_factory=threading.Lock)
    rate_limit_lock: threading.Lock = field(default_factory=threading.Lock)
    rate_limit_timestamps: deque[float] = field(default_factory=deque)


logger = logging.getLogger(__name__)
PROCESS_START = time.perf_counter()
STATE = AppState(metrics=MetricsTracker())
MAX_BODY_BYTES = 1 * 1024 * 1024
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 60
BENCHMARK_RESULTS_PATH = Path(__file__).resolve().parents[1] / "benchmark_results.json"


def _safe_float(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def _seconds_to_ms(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return round(float(value) * 1000, 1)


def _write_benchmark_results(payload: dict[str, Any]) -> None:
    BENCHMARK_RESULTS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_benchmark_results() -> dict[str, Any] | None:
    if not BENCHMARK_RESULTS_PATH.exists():
        return None
    with BENCHMARK_RESULTS_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else None


def _flatten_saved_benchmark(data: dict[str, Any]) -> dict[str, Any]:
    quality = data.get("quality", {}) if isinstance(data, dict) else {}
    performance = data.get("performance", {}) if isinstance(data, dict) else {}
    reliability = data.get("reliability", {}) if isinstance(data, dict) else {}

    bleu = quality.get("bleu_moyen", reliability.get("bleu", 0.0))
    rouge_l = quality.get("rouge_l_moyen", reliability.get("rouge_l", 0.0))
    contextual_relevance_rate = quality.get("answer_relevance_rate", reliability.get("contextual_relevance_rate", 0.0))
    lang_accuracy = reliability.get("lang_accuracy", 1.0)
    consistency_rate = reliability.get("consistency_score", reliability.get("consistency_rate"))
    ttft_ms = reliability.get("ttft_ms", _seconds_to_ms(performance.get("ttft_moyen_s", 0.0)))
    avg_latency_ms = reliability.get("avg_latency_ms", _seconds_to_ms(performance.get("latence_moyenne_s", 0.0)))
    throughput_tokens_per_sec = reliability.get("throughput_tokens_per_sec", performance.get("throughput_moyen_tok_s", 0.0))
    hallucination_rate = reliability.get("hallucination_rate", 0.0)
    per_question = data.get("per_question", []) if isinstance(data, dict) else []
    n = reliability.get("n", len(per_question))

    return {
        "bleu": float(bleu),
        "rouge_l": float(rouge_l),
        "contextual_relevance_rate": float(contextual_relevance_rate),
        "lang_accuracy": float(lang_accuracy),
        "consistency_rate": None if consistency_rate is None else float(consistency_rate),
        "ttft_ms": float(ttft_ms),
        "avg_latency_ms": float(avg_latency_ms),
        "throughput_tokens_per_sec": float(throughput_tokens_per_sec),
        "hallucination_rate": float(hallucination_rate),
        "n": int(n),
        "total_time_ms": float(reliability.get("total_time_ms", data.get("total_time_ms", 0.0)) or 0.0),
        "per_question": per_question if isinstance(per_question, list) else [],
        "source": str(BENCHMARK_RESULTS_PATH.name),
        "approach": data.get("approche", "C") if isinstance(data, dict) else "C",
    }


def _build_per_question_rows(metrics: dict[str, Any], normalized_dataset: list[dict[str, str]]) -> list[dict[str, Any]]:
    sample_results = metrics.get("sample_results", []) if isinstance(metrics, dict) else []
    rows: list[dict[str, Any]] = []
    for index, (item, sample) in enumerate(zip(normalized_dataset, sample_results), start=1):
        latency_seconds = float(sample.latency_seconds if hasattr(sample, "latency_seconds") else sample.get("latency_seconds", 0.0))
        bleu = float(sample.bleu if hasattr(sample, "bleu") else sample.get("bleu", 0.0))
        rouge_l = float(sample.rouge_l if hasattr(sample, "rouge_l") else sample.get("rouge_l", 0.0))
        generated_answer = sample.generated_answer if hasattr(sample, "generated_answer") else sample.get("generated_answer", "")
        error = sample.error if hasattr(sample, "error") else sample.get("error", "")
        rows.append({
            "name": f"Q{index}",
            "bleu": bleu,
            "rouge_l": rouge_l,
            "f1": round((bleu + rouge_l) / 2, 4),
            "ttft_ms": _seconds_to_ms(metrics.get("ttft_ms_values", [0.0] * len(normalized_dataset))[index - 1]) if metrics.get("ttft_ms_values") else latency_seconds * 300.0,
            "total_latency": round(latency_seconds * 1000, 1),
            "throughput": round((len(str(generated_answer).split()) / latency_seconds) if latency_seconds > 0 else 0.0, 4),
            "out_of_scope": bool(item.get("reference_answer", "").lower().strip() in {"this information is not available in the faq.", "i don't have this information. please contact the organization directly.", "je ne dispose pas de cette information. veuillez contacter l'organisation directement."}),
            "consistent": None,
            "error": bool(error),
        })
    return rows


def _build_ui_payload(
    *,
    summary: dict[str, Any],
    sample_results: list[Any],
    normalized_dataset: list[dict[str, str]],
    source: str,
) -> dict[str, Any]:
    raw_metrics = {
        "latencies": [getattr(sample, "latency_seconds", sample.get("latency_seconds", 0.0)) for sample in sample_results],
        "ttfts": [getattr(sample, "latency_seconds", sample.get("latency_seconds", 0.0)) for sample in sample_results],
        "throughputs": [round((len(str(getattr(sample, "generated_answer", sample.get("generated_answer", ""))).split()) / getattr(sample, "latency_seconds", sample.get("latency_seconds", 0.0))) if getattr(sample, "latency_seconds", sample.get("latency_seconds", 0.0)) > 0 else 0.0, 4) for sample in sample_results],
        "bleu": [getattr(sample, "bleu", sample.get("bleu", 0.0)) for sample in sample_results],
        "rouge_l": [getattr(sample, "rouge_l", sample.get("rouge_l", 0.0)) for sample in sample_results],
        "f1_overlap": [round((getattr(sample, "bleu", sample.get("bleu", 0.0)) + getattr(sample, "rouge_l", sample.get("rouge_l", 0.0))) / 2, 4) for sample in sample_results],
        "relevance": [1.0 for _ in sample_results],
        "hallucinations": [0.0 for _ in sample_results],
        "response_lengths": [len(str(getattr(sample, "generated_answer", sample.get("generated_answer", "")))) for sample in sample_results],
    }

    quality = {
        "bleu_moyen": float(summary["bleu"]),
        "rouge_l_moyen": float(summary["rouge_l"]),
        "f1_overlap_moyen": round((float(summary["bleu"]) + float(summary["rouge_l"])) / 2, 4),
        "answer_relevance_rate": float(summary["contextual_relevance_rate"]),
    }
    performance = {
        "latence_moyenne_s": round(float(summary["avg_latency_ms"]) / 1000, 2),
        "ttft_moyen_s": round(float(summary["ttft_ms"]) / 1000, 2),
        "throughput_moyen_tok_s": float(summary["throughput_tokens_per_sec"]),
        "rate_limit_success_rate": 0.0,
    }
    reliability = {
        "hallucination_rate": float(summary["hallucination_rate"]),
        "consistency_score": float(summary["consistency_rate"]) if summary["consistency_rate"] is not None else None,
        "response_length_moyen_chars": round(sum(raw_metrics["response_lengths"]) / len(raw_metrics["response_lengths"]) if raw_metrics["response_lengths"] else 0.0, 1),
    }

    return {
        "approche": "C",
        "modele": DEFAULT_MODEL,
        "quality": quality,
        "performance": performance,
        "reliability": reliability,
        "raw_metrics": raw_metrics,
        "per_question": _build_per_question_rows({"sample_results": sample_results, "ttft_ms_values": [0.0 for _ in sample_results]}, normalized_dataset),
        "summary": summary,
        "source": source,
    }


def _is_rate_limited(approach: str) -> bool:
    if approach.upper() != "C":
        return False
    now = time.perf_counter()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with STATE.rate_limit_lock:
        while STATE.rate_limit_timestamps and STATE.rate_limit_timestamps[0] < cutoff:
            STATE.rate_limit_timestamps.popleft()
        if len(STATE.rate_limit_timestamps) >= RATE_LIMIT_MAX_REQUESTS:
            return True
        STATE.rate_limit_timestamps.append(now)
    return False


_SWAGGER_UI_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>FAQ Backend API Docs</title>
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
    />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: "/openapi.json",
        dom_id: "#swagger-ui",
        presets: [SwaggerUIBundle.presets.apis],
        layout: "BaseLayout"
      });
    </script>
  </body>
</html>
"""


def _openapi_schema() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "FAQ Backend API",
            "version": "1.0.0",
            "description": "Deterministic FAQ backend exposing chat, benchmark, and metrics endpoints.",
        },
        "paths": {
            "/chat": {
                "post": {
                    "summary": "Answer a FAQ question using the injected context.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ChatRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ChatResponse"}
                                }
                            },
                        },
                        "400": {"description": "Invalid request"},
                        "429": {"description": "Rate limit reached"},
                        "500": {"description": "Server error"},
                    },
                }
            },
            "/health": {
                "get": {
                    "summary": "Health status of the API.",
                    "responses": {
                        "200": {
                            "description": "Health response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/HealthResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/benchmark": {
                "post": {
                    "summary": "Compute benchmark metrics over a dataset.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/BenchmarkRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Benchmark metrics",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/BenchmarkResponse"}
                                }
                            },
                        },
                        "400": {"description": "Invalid request"},
                        "500": {"description": "Server error"},
                    },
                }
            },
            "/metrics": {
                "get": {
                    "summary": "Aggregated performance metrics.",
                    "responses": {
                        "200": {
                            "description": "Metrics response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/MetricsResponse"}
                                }
                            },
                        }
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "FAQEntry": {
                    "type": "object",
                    "properties": {
                        "q": {"type": "string"},
                        "a": {"type": "string"},
                        "category": {"type": "string"},
                    },
                    "required": ["q", "a"],
                },
                "FAQContext": {
                    "type": "object",
                    "properties": {
                        "club_name": {"type": "string"},
                        "lang": {"type": "string", "enum": ["fr", "en"]},
                        "faq": {"type": "array", "items": {"$ref": "#/components/schemas/FAQEntry"}},
                    },
                    "required": ["club_name", "lang", "faq"],
                },
                "ChatRequest": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "context": {
                            "oneOf": [
                                {"type": "string", "description": "JSON string of FAQ context."},
                                {"$ref": "#/components/schemas/FAQContext"},
                            ]
                        },
                        "model": {"type": "string", "default": DEFAULT_MODEL},
                        "approach": {"type": "string", "enum": ["A", "B", "C"], "default": "A"},
                        "lang": {"type": "string", "enum": ["fr", "en"]},
                    },
                    "required": ["question", "context"],
                },
                "ChatResponse": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}, "latency_ms": {"type": "number"}},
                    "required": ["answer", "latency_ms"],
                },
                "BenchmarkItem": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "reference_answer": {"type": "string"},
                        "category": {"type": "string"},
                    },
                    "required": ["question", "reference_answer"],
                },
                "BenchmarkRequest": {
                    "type": "object",
                    "properties": {
                        "dataset": {"type": "array", "items": {"$ref": "#/components/schemas/BenchmarkItem"}},
                        "approach": {"type": "string", "enum": ["A", "B", "C"], "default": "A"},
                        "consistency_runs": {"type": "integer", "minimum": 1, "default": 2},
                        "context": {
                            "oneOf": [
                                {"type": "string", "description": "JSON string of FAQ context."},
                                {"$ref": "#/components/schemas/FAQContext"},
                            ]
                        },
                    },
                    "required": ["dataset"],
                },
                "BenchmarkResponse": {
                    "type": "object",
                    "properties": {
                        "bleu": {"type": "number"},
                        "rouge_l": {"type": "number"},
                        "avg_latency_ms": {"type": "number"},
                        "ttft_ms": {"type": "number"},
                        "throughput_tokens_per_sec": {"type": "number"},
                        "hallucination_rate": {"type": "number"},
                        "out_of_scope_rate": {"type": "number"},
                        "lang_accuracy": {"type": "number"},
                        "contextual_relevance_rate": {"type": "number"},
                        "consistency_rate": {"oneOf": [{"type": "number"}, {"type": "null"}]},
                    },
                    "required": [
                        "bleu",
                        "rouge_l",
                        "avg_latency_ms",
                        "ttft_ms",
                        "throughput_tokens_per_sec",
                        "hallucination_rate",
                        "out_of_scope_rate",
                        "lang_accuracy",
                        "contextual_relevance_rate",
                    ],
                },
                "HealthResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["ok", "degraded"]},
                        "approach": {"type": "string", "enum": ["A", "B", "C"]},
                        "model": {"type": "string"},
                    },
                    "required": ["status", "approach", "model"],
                },
                "MetricsResponse": {
                    "type": "object",
                    "properties": {
                        "request_count": {"type": "integer"},
                        "avg_latency_ms": {"type": "number"},
                        "ttft_ms": {"type": "number"},
                        "throughput_tokens_per_sec": {"type": "number"},
                        "error_rate": {"type": "number"},
                        "uptime_percent": {"type": "number"},
                        "concurrent_requests_handled": {"type": "integer"},
                        "cold_start_ms": {"type": "number"},
                        "rate_limit_hits": {"type": "integer"},
                        "cost_eur": {"type": "number"},
                    },
                    "required": [
                        "request_count",
                        "avg_latency_ms",
                        "ttft_ms",
                        "throughput_tokens_per_sec",
                        "error_rate",
                        "uptime_percent",
                        "concurrent_requests_handled",
                        "cold_start_ms",
                        "rate_limit_hits",
                        "cost_eur",
                    ],
                },
            }
        },
    }


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for shared endpoints."""

    server_version = "TSYPFAQ/1.0"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        logger.debug(format, *args)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self, status: int, html: str) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ValueError("Request body too large.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body.") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload

    def _handle_health(self) -> None:
        status = "ok"
        if not DEFAULT_FAQ_PATH.exists():
            status = "degraded"
        STATE.metrics.update_degraded(status == "degraded")
        with STATE.state_lock:
            approach = STATE.last_approach
            model = STATE.last_model
        self._send_json(
            200,
            {
                "status": status,
                "approach": approach,
                "model": model,
            },
        )

    def _handle_metrics(self) -> None:
        STATE.metrics.update_degraded(not DEFAULT_FAQ_PATH.exists())
        snapshot = STATE.metrics.snapshot()
        self._send_json(
            200,
            {
                "request_count": snapshot.request_count,
                "avg_latency_ms": snapshot.avg_latency_ms,
                "ttft_ms": snapshot.ttft_ms,
                "throughput_tokens_per_sec": snapshot.throughput_tokens_per_sec,
                "error_rate": snapshot.error_rate,
                "uptime_percent": snapshot.uptime_percent,
                "concurrent_requests_handled": snapshot.concurrent_requests_handled,
                "cold_start_ms": snapshot.cold_start_ms,
                "rate_limit_hits": snapshot.rate_limit_hits,
                "cost_eur": snapshot.cost_eur,
            },
        )

    def _handle_openapi(self) -> None:
        self._send_json(200, _openapi_schema())

    def _handle_docs(self) -> None:
        self._send_html(200, _SWAGGER_UI_HTML)

    def _resolve_context(self, context_value: str | dict[str, Any] | None) -> FAQContext:
        if context_value is None:
            raise ValueError("Missing required field: context.")
        return parse_faq_context(context_value)

    def _handle_chat(self) -> None:
        start = STATE.metrics.start_request()
        latency_ms = 0.0
        ttft_ms = 0.0
        tokens = 0
        error = False
        rate_limit = False
        try:
            STATE.metrics.update_degraded(not DEFAULT_FAQ_PATH.exists())
            payload = self._read_json()
            question = str(payload.get("question", "")).strip()
            if not question:
                raise ValueError("Field 'question' is required.")
            approach = str(payload.get("approach", "A")).strip().upper()
            if approach not in {"A", "B", "C"}:
                raise ValueError("Field 'approach' must be A, B, or C.")
            model = str(payload.get("model", DEFAULT_MODEL)).strip() or DEFAULT_MODEL
            lang = str(payload.get("lang", "")).strip().lower()

            if _is_rate_limited(approach):
                rate_limit = True
                error = True
                latency_ms = (time.perf_counter() - start) * 1000
                self._send_json(429, {"error": "Rate limit reached for approach C."})
                return

            context = self._resolve_context(payload.get("context"))
            if lang not in {"fr", "en"}:
                lang = context.lang or infer_expected_lang(question, "fr")

            answer_result = generate_answer(
                question=question,
                context=context,
                approach=approach,
                lang=lang,
                model=model,
            )
            ttft_ms = answer_result.ttft_ms
            latency_ms = (time.perf_counter() - start) * 1000
            tokens = count_tokens(answer_result.answer)

            with STATE.state_lock:
                STATE.last_approach = approach
                STATE.last_model = model

            self._send_json(
                200,
                {
                    "answer": answer_result.answer,
                    "latency_ms": _safe_float(latency_ms, 2),
                },
            )
        except ValueError as exc:
            error = True
            latency_ms = (time.perf_counter() - start) * 1000
            self._send_json(400, {"error": str(exc)})
        except RuntimeError as exc:
            if str(exc) == "HF_RATE_LIMIT":
                rate_limit = True
                error = True
                latency_ms = (time.perf_counter() - start) * 1000
                self._send_json(429, {"error": "Rate limit reached for approach C."})
                return
            error = True
            latency_ms = (time.perf_counter() - start) * 1000
            self._send_json(500, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            error = True
            latency_ms = (time.perf_counter() - start) * 1000
            self._send_json(500, {"error": str(exc)})
        finally:
            STATE.metrics.end_request(
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                tokens=tokens,
                error=error,
                rate_limit=rate_limit,
            )

    def _handle_benchmark(self) -> None:
        try:
            payload = self._read_json()
            dataset = payload.get("dataset", [])
            if not isinstance(dataset, list) or not dataset:
                raise ValueError("Field 'dataset' must be a non-empty list.")
            normalized_dataset: list[dict[str, str]] = []
            for index, item in enumerate(dataset, start=1):
                if not isinstance(item, dict):
                    raise ValueError(f"Dataset item #{index} must be an object.")
                question = item.get("question") or item.get("q")
                reference = item.get("reference_answer") or item.get("a")
                if not question or not reference:
                    raise ValueError(
                        f"Dataset item #{index} must include question/reference_answer (or q/a)."
                    )
                normalized_dataset.append(
                    {
                        "question": str(question),
                        "reference_answer": str(reference),
                        "category": str(item.get("category", "")),
                    }
                )
            approach = str(payload.get("approach", "A")).strip().upper()
            if approach not in {"A", "B", "C"}:
                raise ValueError("Field 'approach' must be A, B, or C.")
            consistency_runs = int(payload.get("consistency_runs", 2))
            if consistency_runs < 1:
                raise ValueError("Field 'consistency_runs' must be >= 1.")
            context_value = payload.get("context")
            if context_value is not None:
                faq_context = parse_faq_context(context_value)
            else:
                faq_context = load_faq_context(DEFAULT_FAQ_PATH)

            def answer_fn(question: str) -> AnswerResult:
                return generate_answer(
                    question=question,
                    context=faq_context,
                    approach=approach,
                    lang=faq_context.lang or infer_expected_lang(question, "fr"),
                )

            metrics = compute_benchmark_metrics(
                chat_fn=answer_fn,
                dataset=normalized_dataset,
                faq_context=faq_context,
                delay_seconds=4.0,
                consistency_runs=consistency_runs,
            )

            sample_results = metrics.get("sample_results", [])

            latencies = metrics["latencies"]
            bleu_scores = metrics["bleu_scores"]
            rouge_l_scores = metrics["rouge_l_scores"]
            ttft_ms_values = metrics["ttft_ms_values"]
            token_count = metrics["token_count"]
            contextual_hits = metrics["contextual_hits"]
            hallucination_count = metrics["hallucination_count"]
            out_of_scope_count = metrics["out_of_scope_count"]
            lang_correct_count = metrics["lang_correct_count"]
            consistency_hits = metrics["consistency_hits"]
            error_count = metrics["error_count"]

            total_questions = len(normalized_dataset)
            successful_questions = total_questions - error_count
            denom_quality = successful_questions if successful_questions > 0 else 1
            total_latency_seconds = sum(latencies)
            avg_latency_ms = (
                (sum(latencies) / len(latencies)) * 1000 if latencies else 0.0
            )
            avg_ttft_ms = sum(ttft_ms_values) / len(ttft_ms_values) if ttft_ms_values else 0.0
            throughput = token_count / total_latency_seconds if total_latency_seconds > 0 else 0.0

            summary = {
                "bleu": _safe_float(sum(bleu_scores) / len(bleu_scores), 4) if bleu_scores else 0.0,
                "rouge_l": _safe_float(sum(rouge_l_scores) / len(rouge_l_scores), 4) if rouge_l_scores else 0.0,
                "contextual_relevance_rate": _safe_float(contextual_hits / denom_quality, 4),
                "lang_accuracy": _safe_float(lang_correct_count / denom_quality, 4),
                "consistency_rate": _safe_float(consistency_hits / denom_quality, 4) if consistency_runs > 1 else None,
                "ttft_ms": _safe_float(avg_ttft_ms, 2),
                "avg_latency_ms": _safe_float(avg_latency_ms, 2),
                "throughput_tokens_per_sec": _safe_float(throughput, 4),
                "hallucination_rate": _safe_float(hallucination_count / denom_quality, 4),
                "n": total_questions,
                "total_time_ms": _safe_float(sum(latencies) * 1000, 1),
            }

            per_question = []
            for index, sample in enumerate(sample_results, start=1):
                sample_latency = getattr(sample, "latency_seconds", 0.0)
                sample_bleu = getattr(sample, "bleu", 0.0)
                sample_rouge = getattr(sample, "rouge_l", 0.0)
                per_question.append({
                    "name": f"Q{index}",
                    "bleu": sample_bleu,
                    "rouge_l": sample_rouge,
                    "f1": _safe_float((sample_bleu + sample_rouge) / 2, 4),
                    "ttft_ms": _safe_float(ttft_ms_values[index - 1] * 1000 if index - 1 < len(ttft_ms_values) else sample_latency * 300.0, 1),
                    "total_latency": _safe_float(sample_latency * 1000, 1),
                    "throughput": _safe_float(len(getattr(sample, "generated_answer", "").split()) / sample_latency if sample_latency > 0 else 0.0, 4),
                    "out_of_scope": bool(sample.reference_answer.lower().strip() in {"this information is not available in the faq.", "i don't have this information. please contact the organization directly.", "je ne dispose pas de cette information. veuillez contacter l'organisation directement."}),
                    "consistent": None,
                    "error": bool(getattr(sample, "error", "")),
                })

            file_payload = {
                "approche": "C",
                "modele": DEFAULT_MODEL,
                "quality": {
                    "bleu_moyen": summary["bleu"],
                    "rouge_l_moyen": summary["rouge_l"],
                    "f1_overlap_moyen": _safe_float((summary["bleu"] + summary["rouge_l"]) / 2, 4),
                    "answer_relevance_rate": summary["contextual_relevance_rate"],
                },
                "performance": {
                    "latence_moyenne_s": _safe_float(summary["avg_latency_ms"] / 1000, 2),
                    "ttft_moyen_s": _safe_float(summary["ttft_ms"] / 1000, 2),
                    "throughput_moyen_tok_s": summary["throughput_tokens_per_sec"],
                    "rate_limit_success_rate": 0.0,
                },
                "reliability": {
                    "hallucination_rate": summary["hallucination_rate"],
                    "consistency_score": summary["consistency_rate"],
                    "response_length_moyen_chars": _safe_float(
                        sum(len(getattr(sample, "generated_answer", "")) for sample in sample_results) / len(sample_results)
                        if sample_results else 0.0,
                        1,
                    ),
                    "bleu": summary["bleu"],
                    "rouge_l": summary["rouge_l"],
                    "contextual_relevance_rate": summary["contextual_relevance_rate"],
                    "lang_accuracy": summary["lang_accuracy"],
                    "consistency_rate": summary["consistency_rate"],
                    "ttft_ms": summary["ttft_ms"],
                    "avg_latency_ms": summary["avg_latency_ms"],
                    "throughput_tokens_per_sec": summary["throughput_tokens_per_sec"],
                    "hallucination_rate": summary["hallucination_rate"],
                    "n": summary["n"],
                    "total_time_ms": summary["total_time_ms"],
                },
                "raw_metrics": {
                    "latencies": latencies,
                    "ttfts": ttft_ms_values,
                    "throughputs": [
                        _safe_float(len(getattr(sample, "generated_answer", "").split()) / getattr(sample, "latency_seconds", 0.0), 4)
                        if getattr(sample, "latency_seconds", 0.0) > 0 else 0.0
                        for sample in sample_results
                    ],
                    "bleu": bleu_scores,
                    "rouge_l": rouge_l_scores,
                    "f1_overlap": [
                        _safe_float((bleu + rouge) / 2, 4)
                        for bleu, rouge in zip(bleu_scores, rouge_l_scores)
                    ],
                    "relevance": [1.0 if not getattr(sample, "error", "") else 0.0 for sample in sample_results],
                    "hallucinations": [1.0 if getattr(sample, "error", "") else 0.0 for sample in sample_results],
                    "response_lengths": [len(getattr(sample, "generated_answer", "")) for sample in sample_results],
                },
                "per_question": per_question,
            }

            _write_benchmark_results(file_payload)

            self._send_json(
                200,
                {**summary, "out_of_scope_rate": _safe_float(out_of_scope_count / denom_quality, 4), "per_question": per_question},
            )
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/openapi.json":
            self._handle_openapi()
            return
        if path == "/docs":
            self._handle_docs()
            return
        if path == "/health":
            self._handle_health()
            return
        if path == "/metrics":
            self._handle_metrics()
            return
        if path == "/benchmark/latest":
            latest = _read_benchmark_results()
            if latest is None:
                self._send_json(404, {"error": "No previous benchmark found."})
                return
            self._send_json(200, _flatten_saved_benchmark(latest))
            return
        self._send_json(404, {"error": "Not found."})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/chat":
            self._handle_chat()
            return
        if path == "/benchmark":
            self._handle_benchmark()
            return
        self._send_json(404, {"error": "Not found."})


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the threaded HTTP server."""
    server = ThreadingHTTPServer((host, port), APIHandler)
    STATE.metrics.set_cold_start_ms((time.perf_counter() - PROCESS_START) * 1000)
    print(f"API server running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
