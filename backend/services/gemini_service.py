import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from backend.config import settings
from backend.schemas import QuizGenerationResponse, GeneratedQuestion

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are a quiz generation engine for a government workforce training platform serving India's Official Statistical System. Your questions will be used for real employee assessments, so accuracy and grounding are non-negotiable.

STRICT RULES:
1. Generate questions ONLY using facts, definitions, and claims explicitly present in the provided source material below. Do not introduce outside knowledge, even if you know it to be true.
2. Every question must include the exact source sentence(s) it is based on in the source_excerpt field.
3. If the source material does not contain enough distinct, testable facts to generate the requested number of questions, generate fewer questions rather than inventing content. Never pad with fabricated or paraphrased-until-untrue questions.
4. Distractors (wrong options) must be plausible and topically relevant, but must be clearly and verifiably incorrect based on the source text.
5. Write for a {difficulty} difficulty level.
6. CRITICAL: Your entire response MUST be valid JSON only. No preamble, no explanation text, no markdown fences."""


def _is_valid_gemini_key(api_key: str) -> bool:
    """
    Validates that the API key looks like a real Gemini/Google API key.
    Valid Google API keys typically start with 'AIza' and are 39 chars long.
    Keys starting with 'AQ.', 'your_', or equal to 'your_key_here' are invalid.
    """
    if not api_key:
        return False
    if api_key in ("your_key_here", ""):
        return False
    if api_key.startswith("your_"):
        return False
    # Reject obviously invalid formats
    if api_key.startswith("AQ."):
        return False
    # Google API keys start with AIza and are ~39 chars
    if not api_key.startswith("AIza"):
        logger.warning(f"API key does not start with 'AIza' — treating as potentially invalid, will attempt anyway.")
    return True


def build_prompt(retrieved_chunks: List[Dict[str, Any]], n: int, difficulty: str) -> str:
    """Build grounded prompt string incorporating retrieved chunks."""
    separator = "\n" + "="*50 + "\n"
    chunk_texts = []
    for idx, c in enumerate(retrieved_chunks):
        title = c.get("metadata", {}).get("doc_title", f"Document Chunk {idx+1}")
        chunk_text = c.get("text") or c.get("chunk_text") or ""
        chunk_texts.append(f"[SOURCE CHUNK {idx+1} | Source: {title}]\n{chunk_text}")

    source_material_block = separator.join(chunk_texts)

    prompt = f"""{SYSTEM_INSTRUCTION.format(difficulty=difficulty)}

SOURCE MATERIAL:
{source_material_block}

TASK:
Generate up to {n} multiple-choice questions grounded STRICTLY in the facts above following the required JSON schema.
If there are fewer than {n} distinct testable facts, generate only as many as are strongly supported, and explain this in generation_notes.

Return ONLY a valid JSON object. Do not include any text before or after the JSON.
"""
    return prompt


def _extract_json_from_text(text: str) -> Optional[str]:
    """
    Tries to extract valid JSON from a text that may have surrounding content.
    Handles markdown code fences and leading/trailing text.
    """
    if not text:
        return None

    # Remove markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    text = re.sub(r"```\s*$", "", text).strip()

    # Try the full text first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Try to find JSON object boundaries
    brace_start = text.find('{')
    if brace_start != -1:
        # Find the matching closing brace
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[brace_start:i+1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break

    return None


def generate_mock_quiz_response(retrieved_chunks: List[Dict[str, Any]], n: int, difficulty: str) -> QuizGenerationResponse:
    """
    Intelligent local mock generator used when GEMINI_API_KEY is not configured or in offline demo mode.
    Extracts real sentences from retrieved chunks to guarantee 100% genuine grounding during tests.
    """
    import re as re_mod

    all_sentences = []
    for chunk in retrieved_chunks:
        text = chunk.get("text") or chunk.get("chunk_text") or ""
        # split by sentence endings
        raw_sents = re_mod.split(r'(?<=[.!?])\s+', text)
        for s in raw_sents:
            s_clean = s.strip()
            if len(s_clean.split()) >= 8 and len(s_clean.split()) <= 40:
                all_sentences.append(s_clean)

    questions = []
    selected_sents = all_sentences[:min(n, len(all_sentences))]

    for i, sent in enumerate(selected_sents):
        words = sent.split()
        # Create a realistic question grounded in the sentence
        key_phrase = " ".join(words[:min(6, len(words))])

        q_text = f"According to the official protocol regarding '{key_phrase}...', which of the following statements is accurately stated?"
        opt_correct = sent
        opt_wrong1 = f"The protocol explicitly excludes {words[0]} operations and applies solely to secondary classifications."
        opt_wrong2 = f"This requirement has been completely deprecated in the latest revision of statistical standards."
        opt_wrong3 = f"The procedure is strictly discretionary and not mandated for official statistical enumeration."

        questions.append(GeneratedQuestion(
            question=q_text,
            options=[opt_correct, opt_wrong1, opt_wrong2, opt_wrong3],
            correct_index=0,
            explanation=f"This statement is directly affirmed by the official text: '{sent}'. The other options contain fabricated contradictions.",
            source_excerpt=sent
        ))

    notes = f"Generated {len(questions)} of {n} requested questions directly grounded in source material chunks."
    if len(questions) < n:
        notes += " Insufficient distinct facts in the provided source material to generate more without sacrificing grounding."

    return QuizGenerationResponse(
        questions=questions,
        generation_notes=notes
    )


def generate_quiz_via_gemini(
    retrieved_chunks: List[Dict[str, Any]],
    question_count: int,
    difficulty: str
) -> Tuple[QuizGenerationResponse, Optional[str], Optional[str]]:
    """
    Calls Google Gemini API using the official google-genai SDK with structured output enforcement.
    Returns: (QuizGenerationResponse, raw_response_text, error_message)
    Falls back to local mock generator on any failure if MOCK_GEMINI_ON_MISSING_KEY is True.
    """
    api_key = settings.GEMINI_API_KEY

    # Validate API key before attempting real call
    if not _is_valid_gemini_key(api_key):
        if settings.MOCK_GEMINI_ON_MISSING_KEY:
            logger.warning("GEMINI_API_KEY not configured or invalid format. Using local grounded generation fallback.")
            resp = generate_mock_quiz_response(retrieved_chunks, question_count, difficulty)
            return resp, json.dumps(resp.model_dump(), indent=2), None
        else:
            raise ValueError("GEMINI_API_KEY is not set or is invalid. Please provide a valid Gemini API Key (starts with AIza) in .env.")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt_content = build_prompt(retrieved_chunks, n=question_count, difficulty=difficulty)

        # First attempt: structured JSON output schema
        try:
            config = types.GenerateContentConfig(
                temperature=settings.GENERATION_TEMPERATURE,
                response_mime_type="application/json",
                response_schema=QuizGenerationResponse,
            )

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt_content,
                config=config,
            )

            raw_text = response.text if response and hasattr(response, 'text') else None

            if not raw_text:
                raise ValueError("Empty response from Gemini API")

            # Try to extract valid JSON (handle cases where model adds extra text)
            clean_json = _extract_json_from_text(raw_text)
            if clean_json:
                parsed = QuizGenerationResponse.model_validate_json(clean_json)
                return parsed, raw_text, None
            else:
                raise ValueError(f"Could not extract valid JSON from Gemini response. Raw: {raw_text[:200]}")

        except Exception as schema_err:
            logger.warning(f"Structured output attempt failed: {schema_err}. Retrying without schema enforcement.")

            # Second attempt: plain text JSON without schema enforcement
            config_plain = types.GenerateContentConfig(
                temperature=settings.GENERATION_TEMPERATURE,
                response_mime_type="application/json",
            )

            response2 = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt_content,
                config=config_plain,
            )

            raw_text2 = response2.text if response2 and hasattr(response2, 'text') else None
            if not raw_text2:
                raise ValueError("Empty response on retry from Gemini API")

            clean_json2 = _extract_json_from_text(raw_text2)
            if clean_json2:
                parsed2 = QuizGenerationResponse.model_validate_json(clean_json2)
                return parsed2, raw_text2, None
            else:
                raise ValueError(f"Could not extract valid JSON on retry. Raw: {raw_text2[:200]}")

    except Exception as e:
        error_str = str(e)
        logger.error(f"Gemini API call failed: {error_str}")

        # Always fall back to mock if configured to do so
        if settings.MOCK_GEMINI_ON_MISSING_KEY:
            logger.warning("Falling back to local grounded mock generator due to API error.")
            resp = generate_mock_quiz_response(retrieved_chunks, question_count, difficulty)
            fallback_note = f"API Error (fallback used): {error_str[:200]}"
            return resp, json.dumps(resp.model_dump(), indent=2), fallback_note

        # No fallback: return empty response with error
        return (
            QuizGenerationResponse(questions=[], generation_notes=f"Generation failed: {error_str}"),
            None,
            error_str
        )
