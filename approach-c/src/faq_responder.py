"""Local FAQ response and evaluation utilities."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

import requests

from config import BACKUP_MODEL, DEFAULT_MODEL, HF_API_TOKEN, INFERENCE_TIMEOUT, LLM_MAX_NEW_TOKENS, LLM_TEMPERATURE
from src.faq_context import FAQContext, FAQEntry

logger = logging.getLogger(__name__)

_WORD_CLEAN_RE = re.compile(r"[^\w\s]", re.UNICODE)

_STOPWORDS_FR = {
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "du",
    "de",
    "et",
    "ou",
    "au",
    "aux",
    "en",
    "est",
    "ce",
    "ces",
    "cette",
    "pour",
    "avec",
    "sur",
    "dans",
    "qui",
    "que",
    "quoi",
    "comment",
    "quel",
    "quelle",
    "quels",
    "quelles",
    "peut",
    "on",
    "vous",
    "il",
    "elle",
    "a", 
    "y", 
    "ne", 
    "pas", 
    "si", 
    "je", 
    "tu", 
    "nous", 
    "ils", 
    "elles",
    "me", 
    "lui", 
    "se", 
    "tout", 
    "bien", 
    "plus", 
    "par", 
    "sont",
}

_STOPWORDS_EN = {
    "the",
    "an",
    "and",
    "or",
    "to",
    "in",
    "on",
    "for",
    "of",
    "is",
    "are",
    "be",
    "with",
    "what",
    "where",
    "when",
    "how",
    "can",
    "do",
    "does",
    "i",
    "we",
    "you",
    "your",
}

_STOPWORDS_ALL = _STOPWORDS_FR | _STOPWORDS_EN

_OUT_OF_SCOPE_MESSAGES = {
    "fr": "Desole, cette information n'est pas disponible dans la FAQ fournie.",
    "en": "Sorry, that information is not available in the provided FAQ.",
}

_APPROACH_THRESHOLDS = {
    "C": 0.6,
}


@dataclass(frozen=True)
class AnswerResult:
    """Answer with metadata for evaluation."""

    answer: str
    matched_entry: FAQEntry | None
    similarity: float
    out_of_scope: bool
    ttft_ms: float = 0.0  # real TTFT in ms, 0.0 if not measurable


def normalize_text(text: str) -> str:
    """Lowercase and remove punctuation for comparison."""
    cleaned = _WORD_CLEAN_RE.sub(" ", text.lower())
    return " ".join(cleaned.split())


def tokenize(text: str) -> list[str]:
    """Split text into normalized tokens."""
    normalized = normalize_text(text)
    return [token for token in normalized.split() if token]


def count_tokens(text: str) -> int:
    """Approximate token count using whitespace tokens."""
    return len(tokenize(text))


def detect_language(text: str) -> str:
    """Heuristic FR/EN detection based on stopword hits."""
    tokens = tokenize(text)
    if not tokens:
        return ""
    fr_hits = sum(1 for token in tokens if token in _STOPWORDS_FR)
    en_hits = sum(1 for token in tokens if token in _STOPWORDS_EN)
    if fr_hits > en_hits:
        return "fr"
    if en_hits > fr_hits:
        return "en"
    if any(char in "\u00e9\u00e8\u00ea\u00e0\u00e7\u00f9\u00f4\u00ee\u00ef\u00fb" for char in text.lower()):
        return "fr"
    return ""


def infer_expected_lang(text: str, default_lang: str = "fr") -> str:
    """Infer expected language from the question text."""
    detected = detect_language(text)
    return detected or default_lang


def out_of_scope_message(lang: str) -> str:
    """Return the standard out-of-scope reply in the requested language."""
    return _OUT_OF_SCOPE_MESSAGES.get(lang, _OUT_OF_SCOPE_MESSAGES["fr"])


def is_out_of_scope(answer: str, lang: str) -> bool:
    """Check whether the answer is the standard out-of-scope reply."""
    return normalize_text(answer) == normalize_text(out_of_scope_message(lang))


def build_prompt(question: str, context: FAQContext, lang: str) -> str:
    """Build a context-injected prompt from FAQ entries."""
    lang_instruction = "Respond in French." if lang == "fr" else "Respond in English."
    faq_lines = "\n".join(
        f"Q: {entry.question}\nA: {entry.answer}" for entry in context.entries
    )
    return (
        f"You are a helpful assistant for {context.club_name}.\n"
        f"Answer ONLY using the FAQ below. If the question is not covered, reply exactly: "
        f"{out_of_scope_message(lang)}\n"
        f"Answer using the EXACT wording from the FAQ when possible. Do not paraphrase.\n"
        f"If the question contains multiple sub-questions, answer each one in a single merged response using only FAQ content.\n"
        f"{lang_instruction}\n\n"
        f"FAQ:\n{faq_lines}\n\n"
        f"Question: {question}\nAnswer:"
    )


def _token_set(text: str, stopwords: Iterable[str] | None = None) -> set[str]:
    tokens = tokenize(text)
    if stopwords:
        return {token for token in tokens if token not in stopwords}
    return set(tokens)


def _jaccard_similarity(a: str, b: str) -> float:
    tokens_a = _token_set(a, _STOPWORDS_ALL)
    tokens_b = _token_set(b, _STOPWORDS_ALL)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _sequence_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def _overlap_similarity(a: str, b: str) -> float:
    tokens_a = _token_set(a, _STOPWORDS_ALL)
    tokens_b = _token_set(b, _STOPWORDS_ALL)
    if len(tokens_a) < 2 or len(tokens_b) < 2:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    return overlap / min(len(tokens_a), len(tokens_b)) if overlap else 0.0


def question_similarity(question: str, candidate: str) -> float:
    """Blend lexical overlap and sequence similarity."""
    jaccard = _jaccard_similarity(question, candidate)
    seq = _sequence_similarity(question, candidate)
    overlap = _overlap_similarity(question, candidate)
    return max((0.6 * jaccard) + (0.4 * seq), overlap)


def find_best_entry(question: str, entries: list[FAQEntry]) -> tuple[FAQEntry | None, float]:
    """Return best matching FAQ entry and score."""
    best_entry: FAQEntry | None = None
    best_score = 0.0
    for entry in entries:
        score = question_similarity(question, entry.question)
        if score > best_score:
            best_score = score
            best_entry = entry
    return best_entry, best_score


def _call_approach_c(prompt: str, model: str) -> tuple[str, float]:
    """
    Call HuggingFace Inference API (free tier) with SSE streaming to capture real TTFT.
    Returns (answer_text, ttft_ms).
    Raises RuntimeError on failure or if HF_API_TOKEN is not set.
    """
    if not HF_API_TOKEN:
        raise RuntimeError("HF_API_TOKEN is not configured.")
    effective_model = DEFAULT_MODEL if DEFAULT_MODEL else "llama-3.1-8b-instant"
    url = "https://api.groq.com/openai/v1/chat/completions"    
    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": effective_model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": LLM_MAX_NEW_TOKENS,
        "temperature": LLM_TEMPERATURE,
        "stream": True,
    }
    t0 = time.perf_counter()
    ttft_ms = 0.0
    first_token_captured = False
    chunks: list[str] = []

    with requests.post(
        url,
        headers=headers,
        json=payload,
        stream=True,
        timeout=INFERENCE_TIMEOUT,
    ) as resp:
        if resp.status_code == 429:
            raise RuntimeError("HF_RATE_LIMIT")
        resp.raise_for_status()
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line.startswith("data:"):
                continue
            data_str = line[len("data:") :].strip()
            if data_str == "[DONE]":
                break
            try:
                obj = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            token_text = obj.get("choices", [{}])[0].get("delta", {}).get("content", "") or ""
            if token_text and not first_token_captured:
                ttft_ms = (time.perf_counter() - t0) * 1000
                first_token_captured = True
            chunks.append(token_text)

    answer = "".join(chunks).strip()
    if not answer:
        payload_no_stream = {k: v for k, v in payload.items() if k != "stream"}
        resp2 = requests.post(
            url,
            headers=headers,
            json=payload_no_stream,
            timeout=INFERENCE_TIMEOUT,
        )
        if resp2.status_code == 429:
            raise RuntimeError("HF_RATE_LIMIT")
        resp2.raise_for_status()
        result = resp2.json()
        if isinstance(result, dict):
            answer = str(result.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
        ttft_ms = (time.perf_counter() - t0) * 1000
    if not answer:
        raise RuntimeError("HF Inference API returned an empty response.")
    return answer, ttft_ms


def generate_answer(
    question: str,
    context: FAQContext,
    approach: str = "C",
    lang: str | None = None,
    model: str | None = None,
) -> AnswerResult:
    """
    Route inference to the correct backend based on approach.
    Falls back to deterministic FAQ matching if the backend is unavailable.
    """
    selected_lang = (lang or context.lang or infer_expected_lang(question)).lower()
    effective_model = (model or "").strip()
    prompt = build_prompt(question, context, selected_lang)

    _CALLERS = {
        "C": _call_approach_c,
    }
    caller = _CALLERS.get(approach.upper())

    if caller is not None:
        try:
            answer, ttft_ms = caller(prompt, effective_model)
            oos = is_out_of_scope(answer, selected_lang)
            return AnswerResult(
                answer=answer,
                matched_entry=None,
                similarity=0.0,
                out_of_scope=oos,
                ttft_ms=ttft_ms,
            )
        except RuntimeError as exc:
            err_str = str(exc)
            if err_str == "HF_RATE_LIMIT":
                raise
            logger.warning(
                "Approach %s inference failed (%s). Falling back to FAQ matcher.",
                approach,
                exc,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Approach %s inference error (%s). Falling back to FAQ matcher.",
                approach,
                exc,
            )

    threshold = _APPROACH_THRESHOLDS.get(approach.upper(), _APPROACH_THRESHOLDS["C"])
    best_entry, score = find_best_entry(question, context.entries)
    if best_entry is None or score < threshold:
        return AnswerResult(
            answer=out_of_scope_message(selected_lang),
            matched_entry=None,
            similarity=score,
            out_of_scope=True,
            ttft_ms=0.0,
        )
    return AnswerResult(
        answer=best_entry.answer,
        matched_entry=best_entry,
        similarity=score,
        out_of_scope=False,
        ttft_ms=0.0,
    )


def is_answer_in_context(answer: str, context: FAQContext) -> bool:
    """Check if answer content appears within any FAQ answer."""
    normalized_answer = normalize_text(answer)
    if not normalized_answer:
        return False
    for entry in context.entries:
        normalized_entry = normalize_text(entry.answer)
        if normalized_answer in normalized_entry or normalized_entry in normalized_answer:
            return True
    return False