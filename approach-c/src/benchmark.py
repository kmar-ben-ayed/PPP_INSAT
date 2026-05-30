"""Quality benchmarking utilities for FAQ chatbot responses."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu
from rouge_score import rouge_scorer

from src.faq_context import FAQContext
from src.faq_responder import (
    AnswerResult,
    count_tokens,
    detect_language,
    infer_expected_lang,
    is_answer_in_context,
    is_out_of_scope,
    normalize_text,
)

_ROUGE_SCORER = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)


@dataclass
class BenchmarkSampleResult:
    """Per-question benchmark output."""

    index: int
    question: str
    reference_answer: str
    generated_answer: str
    category: str
    latency_seconds: float
    bleu: float
    rouge_l: float
    error: str = ""


def _compute_bleu(reference: str, hypothesis: str) -> float:
    """Compute sentence-level BLEU score with smoothing."""
    reference_tokens = reference.lower().split()
    hypothesis_tokens = hypothesis.lower().split()
    if not hypothesis_tokens:
        return 0.0
    return float(
        sentence_bleu(
            [reference_tokens],
            hypothesis_tokens,
            smoothing_function=SmoothingFunction().method1,
        )
    )


def _compute_rouge_l(reference: str, hypothesis: str) -> float:
    """Compute ROUGE-L recall score."""
    score = _ROUGE_SCORER.score(reference, hypothesis)["rougeL"].recall
    return float(score)


def compute_benchmark_metrics(
    chat_fn: Callable[[str], AnswerResult],
    dataset: list[dict[str, str]],
    faq_context: FAQContext | None = None,
    delay_seconds: float = 1.5,
    consistency_runs: int = 1,
) -> dict[str, object]:
    """Evaluate a dataset and return metrics plus sample results."""
    sample_results: list[BenchmarkSampleResult] = []
    latencies: list[float] = []
    ttft_ms_values: list[float] = []
    bleu_scores: list[float] = []
    rouge_l_scores: list[float] = []

    token_count = 0
    contextual_hits = 0
    hallucination_count = 0
    out_of_scope_count = 0
    lang_correct_count = 0
    consistency_hits = 0
    error_count = 0

    default_lang = faq_context.lang if faq_context and faq_context.lang else "fr"

    for index, item in enumerate(dataset, start=1):
        question = str(item.get("question", "")).strip()
        reference = str(item.get("reference_answer", "")).strip()
        category = str(item.get("category", "")).strip()

        start = time.perf_counter()
        generated_result: AnswerResult | None = None
        generated = ""
        error = ""
        try:
            generated_result = chat_fn(question)
            generated = generated_result.answer
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            error_count += 1
        latency = time.perf_counter() - start
        latencies.append(latency)
        ttft_ms_values.append(generated_result.ttft_ms if generated_result else 0.0)

        if generated:
            token_count += count_tokens(generated)

        bleu = _compute_bleu(reference, generated) if generated else 0.0
        rouge_l = _compute_rouge_l(reference, generated) if generated else 0.0

        sample = BenchmarkSampleResult(
            index=index,
            question=question,
            reference_answer=reference,
            generated_answer=generated,
            category=category,
            latency_seconds=round(latency, 4),
            bleu=round(bleu, 4),
            rouge_l=round(rouge_l, 4),
            error=error,
        )
        sample_results.append(sample)

        bleu_scores.append(bleu)
        rouge_l_scores.append(rouge_l)

        if generated:
            expected_lang = infer_expected_lang(question, default_lang)
            answer_lang = detect_language(generated) or default_lang
            is_oos = is_out_of_scope(generated, "fr") or is_out_of_scope(generated, "en")
            if not is_oos and answer_lang == expected_lang:
                lang_correct_count += 1
            if is_oos:
                out_of_scope_count += 1
            if faq_context and not is_oos:
                if is_answer_in_context(generated, faq_context):
                    contextual_hits += 1
                else:
                    hallucination_count += 1

            if consistency_runs > 1:
                consistent = True
                for _ in range(consistency_runs - 1):
                    try:
                        retry = chat_fn(question)
                    except Exception:
                        consistent = False
                        break
                    if normalize_text(retry.answer) != normalize_text(generated):
                        consistent = False
                        break
                if consistent:
                    consistency_hits += 1
            else:
                consistency_hits += 1

        if index < len(dataset) and delay_seconds > 0:
            time.sleep(delay_seconds)

    return {
        "sample_results": sample_results,
        "latencies": latencies,
        "ttft_ms_values": ttft_ms_values,
        "bleu_scores": bleu_scores,
        "rouge_l_scores": rouge_l_scores,
        "token_count": token_count,
        "contextual_hits": contextual_hits,
        "hallucination_count": hallucination_count,
        "out_of_scope_count": out_of_scope_count,
        "lang_correct_count": lang_correct_count,
        "consistency_hits": consistency_hits,
        "error_count": error_count,
    }
