import difflib
import re
from typing import List, Tuple, Dict, Any, Optional
from backend.schemas import GeneratedQuestion

def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching (lowercase, clean whitespace & punctuation)."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def calculate_best_substring_match(excerpt: str, source_text: str) -> float:
    """
    Computes best fuzzy match similarity ratio between the excerpt and any sliding
    window of similar length across the source text.
    """
    norm_excerpt = normalize_text(excerpt)
    norm_source = normalize_text(source_text)

    if not norm_excerpt:
        return 0.0

    if norm_excerpt in norm_source:
        return 1.0

    excerpt_len = len(norm_excerpt)
    words_excerpt = norm_excerpt.split()
    words_source = norm_source.split()

    if not words_source or not words_excerpt:
        return 0.0

    window_size = max(len(words_excerpt), 5)
    best_ratio = 0.0

    # Slide window over source words with step
    step = max(1, window_size // 4)
    for i in range(0, max(1, len(words_source) - window_size + 1), step):
        window = " ".join(words_source[i:i + window_size + 5])
        ratio = difflib.SequenceMatcher(None, norm_excerpt, window).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
        if best_ratio >= 0.95:
            break

    return best_ratio

def validate_question_grounding(
    question: GeneratedQuestion,
    source_chunks: List[Dict[str, Any]],
    similarity_threshold: float = 0.85
) -> Tuple[bool, str, Optional[int], float]:
    """
    Validates that question's source_excerpt is genuinely present in one of the retrieved chunks.
    Returns: (is_valid, reason, matching_chunk_id, best_score)
    """
    if not question.source_excerpt or len(question.source_excerpt.strip()) < 10:
        return False, "Empty or too short source excerpt", None, 0.0

    best_score = 0.0
    matching_chunk_id = None

    for chunk in source_chunks:
        chunk_text = chunk.get("text", "") or chunk.get("chunk_text", "")
        score = calculate_best_substring_match(question.source_excerpt, chunk_text)
        if score > best_score:
            best_score = score
            matching_chunk_id = chunk.get("chunk_id") or chunk.get("id")

    if best_score >= similarity_threshold:
        return True, "Valid source grounding verified", matching_chunk_id, best_score
    else:
        return (
            False,
            f"Source excerpt not grounded in retrieved material (similarity {best_score:.2f} < {similarity_threshold:.2f})",
            None,
            best_score
        )

def validate_question_options(question: GeneratedQuestion) -> Tuple[bool, str]:
    """Validates that question has exactly 4 non-empty options and a valid correct_index (0-3)."""
    if not question.options or len(question.options) != 4:
        return False, f"Expected exactly 4 options, found {len(question.options) if question.options else 0}"
    
    if any(not opt or not opt.strip() for opt in question.options):
        return False, "Question contains empty option choices"

    # Check for duplicate options
    clean_opts = [opt.strip().lower() for opt in question.options]
    if len(set(clean_opts)) < 4:
        return False, "Question has duplicate option choices"

    if question.correct_index not in [0, 1, 2, 3]:
        return False, f"Invalid correct_index '{question.correct_index}'. Must be 0, 1, 2, or 3."

    return True, "Options valid"

def filter_duplicate_questions(questions: List[GeneratedQuestion], threshold: float = 0.88) -> Tuple[List[GeneratedQuestion], List[Dict[str, Any]]]:
    """
    Detects and eliminates near-duplicate questions within a single generated batch.
    """
    unique_questions: List[GeneratedQuestion] = []
    discarded: List[Dict[str, Any]] = []

    for q in questions:
        norm_q = normalize_text(q.question)
        is_duplicate = False
        for u in unique_questions:
            norm_u = normalize_text(u.question)
            ratio = difflib.SequenceMatcher(None, norm_q, norm_u).ratio()
            if ratio >= threshold:
                is_duplicate = True
                discarded.append({
                    "question": q.question,
                    "reason": f"Near-duplicate of existing question with similarity {ratio:.2f}",
                    "excerpt": q.source_excerpt
                })
                break
        if not is_duplicate:
            unique_questions.append(q)

    return unique_questions, discarded
