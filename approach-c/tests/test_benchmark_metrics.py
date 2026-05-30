"""Unit tests for benchmark metric computation."""

from __future__ import annotations

from src.benchmark import compute_benchmark_metrics
from src.faq_context import FAQContext, FAQEntry
from src.faq_responder import AnswerResult, out_of_scope_message


# ---------------------------------------------------------------------------
# Core benchmark pipeline tests
# ---------------------------------------------------------------------------

def test_compute_benchmark_metrics_captures_ttft() -> None:
    context = FAQContext(
        club_name="TRYSP",
        description="",
        lang="fr",
        entries=[FAQEntry(question="Quand?", answer="Salut", category="logistique")],
    )
    dataset = [
        {
            "question": "Quand?",
            "reference_answer": "Salut",
            "category": "logistique",
        }
    ]

    def chat_fn(_: str) -> AnswerResult:
        return AnswerResult(
            answer="Salut",
            matched_entry=None,
            similarity=1.0,
            out_of_scope=False,
            ttft_ms=150.0,
        )

    metrics = compute_benchmark_metrics(chat_fn, dataset, faq_context=context)

    assert metrics["ttft_ms_values"] == [150.0]
    assert metrics["token_count"] > 0


def test_compute_benchmark_metrics_tracks_out_of_scope() -> None:
    context = FAQContext(
        club_name="TRYSP",
        description="",
        lang="fr",
        entries=[FAQEntry(question="Quand?", answer="Lundi", category="logistique")],
    )
    dataset = [
        {
            "question": "Question hors contexte",
            "reference_answer": "N/A",
            "category": "autre",
        }
    ]

    def chat_fn(_: str) -> AnswerResult:
        return AnswerResult(
            answer=out_of_scope_message("fr"),
            matched_entry=None,
            similarity=0.0,
            out_of_scope=True,
            ttft_ms=0.0,
        )

    metrics = compute_benchmark_metrics(chat_fn, dataset, faq_context=context)

    assert metrics["out_of_scope_count"] == 1


def test_language_accuracy_and_consistency() -> None:
    context = FAQContext(
        club_name="TRYSP",
        description="",
        lang="fr",
        entries=[
            FAQEntry(question="Quand?", answer="Lundi", category="logistique"),
            FAQEntry(question="When?", answer="Monday", category="logistics"),
        ],
    )
    dataset = [
        {
            "question": "Quand ont lieu les entrainements ?",
            "reference_answer": "C'est lundi.",
            "category": "logistique",
        },
        {
            "question": "When do trainings happen?",
            "reference_answer": "It is on Monday.",
            "category": "logistics",
        },
    ]

    def chat_fn(question: str) -> AnswerResult:
        answer = "It is on Monday." if question.startswith("When") else "C'est lundi."
        return AnswerResult(
            answer=answer,
            matched_entry=None,
            similarity=1.0,
            out_of_scope=False,
            ttft_ms=10.0,
        )

    metrics = compute_benchmark_metrics(
        chat_fn,
        dataset,
        faq_context=context,
        consistency_runs=2,
    )

    assert metrics["lang_correct_count"] == 2
    assert metrics["consistency_hits"] == 2


def test_contextual_relevance_and_hallucination() -> None:
    context = FAQContext(
        club_name="TRYSP",
        description="",
        lang="fr",
        entries=[
            FAQEntry(question="Quand?", answer="Lundi", category="logistique"),
            FAQEntry(question="Ou?", answer="Paris", category="logistique"),
        ],
    )
    dataset = [
        {
            "question": "Quand?",
            "reference_answer": "Lundi",
            "category": "logistique",
        },
        {
            "question": "Ou?",
            "reference_answer": "Paris",
            "category": "logistique",
        },
    ]

    def chat_fn(question: str) -> AnswerResult:
        # "Quand?" returns a correct in-context answer; "Ou?" hallucinate "Lyon"
        answer = "Lundi" if question == "Quand?" else "Lyon"
        return AnswerResult(
            answer=answer,
            matched_entry=None,
            similarity=1.0,
            out_of_scope=False,
            ttft_ms=5.0,
        )

    metrics = compute_benchmark_metrics(chat_fn, dataset, faq_context=context)

    assert metrics["contextual_hits"] == 1
    assert metrics["hallucination_count"] == 1


# ---------------------------------------------------------------------------
# Multi-intent — FAQ matcher behaviour (approaches A/B, no LLM)
# ---------------------------------------------------------------------------
# The FAQ matcher is single-answer by design. Multi-intent questions hit one
# of three regimes:
#
#   1. DOMINANT INTENT — one intent's tokens dominate → matcher answers it,
#                        silently drops the other.
#   2. TIE             — both intents score equally → first entry by iteration
#                        order wins, second intent is dropped.
#   3. DILUTED         — tokens spread across entries, none clears threshold
#                        → out-of-scope.
# ---------------------------------------------------------------------------

def _multi_intent_context() -> FAQContext:
    return FAQContext(
        club_name="TRYSP",
        description="",
        lang="fr",
        entries=[
            FAQEntry(
                question="Quand ont lieu les entrainements ?",
                answer="Chaque lundi a 18h.",
                category="logistique",
            ),
            FAQEntry(
                question="Comment s inscrire ?",
                answer="Via le formulaire en ligne sur notre site.",
                category="inscription",
            ),
            FAQEntry(
                question="Ou se deroule l evenement ?",
                answer="Au campus INSAT salle B2.",
                category="logistique",
            ),
            FAQEntry(
                question="Quel est le cout de participation ?",
                answer="La participation est gratuite.",
                category="inscription",
            ),
        ],
    )


def test_multi_intent_dominant_returns_best_match() -> None:
    """One intent dominates token overlap — matcher answers it, drops the other."""
    from src.faq_responder import find_best_entry

    context = _multi_intent_context()
    question = "Quand ont lieu les entrainements inscription"
    best, score = find_best_entry(question, context.entries)

    assert best is not None
    assert best.answer == "Chaque lundi a 18h."
    assert score >= 0.6


def test_multi_intent_tie_returns_first_entry_by_order() -> None:
    """Equal-scoring intents: first FAQ entry by iteration order wins, second is dropped."""
    from src.faq_responder import find_best_entry, question_similarity

    context = _multi_intent_context()
    question = "Quand ont lieu les entrainements et comment s inscrire ?"

    scores = [question_similarity(question, e.question) for e in context.entries]
    assert scores[0] == scores[1], "Precondition: both intents must score equally"

    best, score = find_best_entry(question, context.entries)

    assert best is not None
    assert best.answer == "Chaque lundi a 18h."  # first entry wins
    assert "formulaire" not in best.answer        # second intent completely absent
    assert score == scores[0]


def test_multi_intent_diluted_falls_below_threshold_and_returns_oos() -> None:
    """Tokens diluted across unrelated entries: no entry clears 0.6 → out-of-scope end-to-end."""
    from src.faq_responder import find_best_entry, generate_answer, out_of_scope_message

    context = _multi_intent_context()
    question = "inscription logistique details"

    _, score = find_best_entry(question, context.entries)
    assert score < 0.6

    # End-to-end via FAQ matcher (approach A, no LLM)
    result = generate_answer(question=question, context=context, approach="A", lang="fr")
    assert result.out_of_scope is True
    assert result.answer == out_of_scope_message("fr")


# ---------------------------------------------------------------------------
# Multi-intent — approach C (LLM) tests
# ---------------------------------------------------------------------------

def test_build_prompt_contains_multi_intent_instruction() -> None:
    """Prompt must explicitly instruct the LLM to merge answers for multi-intent questions."""
    from src.faq_responder import build_prompt

    context = _multi_intent_context()
    prompt = build_prompt("Quand et comment s inscrire ?", context, "fr")

    assert "multiple sub-questions" in prompt
    assert "single merged response" in prompt


def test_multi_intent_llm_merged_answer_scores_higher_than_partial() -> None:
    """
    Merged answer covering both intents must score strictly higher than a
    partial answer on BLEU and ROUGE-L against the full two-part reference.
    This is the core regression guard for the multi-intent prompt change.
    """
    from src.benchmark import _compute_bleu, _compute_rouge_l

    reference = "Chaque lundi a 18h. Via le formulaire en ligne sur notre site."
    merged  = "Chaque lundi a 18h. Via le formulaire en ligne sur notre site."
    partial = "Chaque lundi a 18h."

    assert _compute_bleu(reference, merged)   > _compute_bleu(reference, partial)
    assert _compute_rouge_l(reference, merged) > _compute_rouge_l(reference, partial)


def test_multi_intent_llm_merged_answer_scores_perfect_in_benchmark() -> None:
    """
    When the LLM returns an answer that exactly covers both intents,
    benchmark BLEU and ROUGE-L must both be 1.0.
    """
    from src.benchmark import compute_benchmark_metrics
    from src.faq_responder import AnswerResult

    context = _multi_intent_context()
    dataset = [
        {
            "question": "Quand ont lieu les entrainements et comment s inscrire ?",
            "reference_answer": "Chaque lundi a 18h. Via le formulaire en ligne sur notre site.",
            "category": "multi_intent",
        }
    ]

    def chat_fn(_: str) -> AnswerResult:
        return AnswerResult(
            answer="Chaque lundi a 18h. Via le formulaire en ligne sur notre site.",
            matched_entry=None,
            similarity=1.0,
            out_of_scope=False,
            ttft_ms=120.0,
        )

    metrics = compute_benchmark_metrics(chat_fn, dataset, faq_context=context)

    assert metrics["bleu_scores"][0] == 1.0
    assert metrics["rouge_l_scores"][0] == 1.0