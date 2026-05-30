"""FAQ context parsing and prompt construction utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import resolve_path


@dataclass(frozen=True)
class FAQEntry:
    """Single FAQ question/answer pair."""

    question: str
    answer: str
    category: str


@dataclass(frozen=True)
class FAQContext:
    """Normalized FAQ context with metadata."""

    club_name: str
    description: str
    lang: str
    entries: list[FAQEntry]


def _normalize_lang(value: str) -> str:
    lang = value.strip().lower()
    if lang in {"fr", "en"}:
        return lang
    return ""


def _wrap_faq_list(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"club_name": "TRYSP", "lang": "", "faq": items}


def parse_faq_payload(payload: dict[str, Any]) -> FAQContext:
    """Parse FAQ payload from either legacy or shared schema."""
    club_name = str(payload.get("club_name") or payload.get("club") or "TSYP").strip()
    if not club_name:
        club_name = "TSYP"
    description = str(payload.get("description", "")).strip()
    lang = _normalize_lang(str(payload.get("lang", "") or ""))

    faq_items = payload.get("faq", [])
    if not isinstance(faq_items, list) or not faq_items:
        raise ValueError("FAQ payload is invalid: 'faq' must be a non-empty list.")

    entries: list[FAQEntry] = []
    for index, item in enumerate(faq_items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"FAQ entry #{index} is invalid.")
        question = str(item.get("q") or item.get("question") or "").strip()
        answer = str(item.get("a") or item.get("answer") or "").strip()
        category = str(item.get("category", "")).strip()
        if not question or not answer:
            raise ValueError(f"FAQ entry #{index} must include question and answer.")
        entries.append(FAQEntry(question=question, answer=answer, category=category))

    return FAQContext(
        club_name=club_name,
        description=description,
        lang=lang,
        entries=entries,
    )


def load_faq_context(path: str | Path) -> FAQContext:
    """Load FAQ context from a JSON file on disk."""
    resolved_path = resolve_path(path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"FAQ file not found: {resolved_path}")
    with resolved_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if isinstance(payload, list):
        payload = _wrap_faq_list(payload)
    if not isinstance(payload, dict):
        raise ValueError("FAQ file is invalid: expected a JSON object or list.")
    return parse_faq_payload(payload)


def parse_faq_context(value: str | dict[str, Any] | list[dict[str, Any]]) -> FAQContext:
    """Parse FAQ context from JSON string, dictionary payload, or list of entries."""
    if isinstance(value, list):
        return parse_faq_payload(_wrap_faq_list(value))
    if isinstance(value, dict):
        return parse_faq_payload(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("FAQ context cannot be empty.")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("FAQ context must be valid JSON.") from exc
        if isinstance(payload, list):
            payload = _wrap_faq_list(payload)
        if not isinstance(payload, dict):
            raise ValueError("FAQ context must be a JSON object or list.")
        return parse_faq_payload(payload)
    raise ValueError("FAQ context must be a JSON object, list, or JSON string.")
