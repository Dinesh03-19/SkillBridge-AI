import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.config import settings
from backend.models import Quiz, QuizQuestion, GenerationLog, TrainingMaterial, DocumentChunk
from backend.schemas import QuizGenerateRequest, QuizGenerationResponse, GeneratedQuestion
from backend.services.embeddings import EmbeddingService
from backend.services.gemini_service import generate_quiz_via_gemini
from backend.services.validation import (
    validate_question_grounding,
    validate_question_options,
    filter_duplicate_questions
)

logger = logging.getLogger(__name__)

MINIMUM_WORD_COUNT_THRESHOLD = 150

class QuizOrchestrationService:

    @staticmethod
    def generate_grounded_quiz(db: Session, request: QuizGenerateRequest) -> Dict[str, Any]:
        """
        Full pipeline for grounded quiz generation:
        1. Query ChromaDB for top-k relevant chunks matching skill / material.
        2. Check for sufficient source material words.
        3. Call Gemini API with structured JSON output schema.
        4. Validate schema, options, duplicate detection, and fuzzy source grounding.
        5. Discard non-grounded questions and record generation audit logs.
        6. Persist Quiz and valid Questions to database.
        """
        embedding_service = EmbeddingService.get_instance()
        
        # 1. Retrieve top-k chunks
        target_doc_title = ""
        if request.material_id:
            mat = db.query(TrainingMaterial).filter(TrainingMaterial.id == request.material_id).first()
            if mat:
                target_doc_title = mat.title
                if not request.skill_id or request.skill_id == "all":
                    request.skill_id = mat.linked_skill_id

        search_query = f"Key concepts, methodology, definitions, rules, facts, and procedures in {target_doc_title or request.skill_id.replace('_', ' ')}"
        retrieved = embedding_service.retrieve_relevant_chunks(
            query=search_query,
            skill_id=request.skill_id if not request.material_id else None,
            material_id=request.material_id,
            top_k=6
        )

        # Also find chunk metadata from database to get DB chunk IDs
        db_chunks = []
        if retrieved:
            chunk_embedding_ids = [r["id"] for r in retrieved]
            db_chunks = db.query(DocumentChunk).filter(DocumentChunk.embedding_id.in_(chunk_embedding_ids)).all()
            # Map chunk DB IDs into retrieved list
            chunk_id_map = {c.embedding_id: c.id for c in db_chunks}
            for r in retrieved:
                r["chunk_id"] = chunk_id_map.get(r["id"])

        # 2. Check for insufficient content (< 150 words)
        total_words = sum(len((r.get("text") or "").split()) for r in retrieved)
        if total_words < MINIMUM_WORD_COUNT_THRESHOLD:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough training material uploaded for this skill yet (found {total_words} words, minimum required is {MINIMUM_WORD_COUNT_THRESHOLD}). Please upload relevant documents first."
            )

        # 3. Call Gemini API
        raw_response_text = None
        error_msg = None
        parse_success = True
        
        parsed_response, raw_response_text, error_msg = generate_quiz_via_gemini(
            retrieved_chunks=retrieved,
            question_count=request.question_count,
            difficulty=request.difficulty
        )

        if error_msg and not parsed_response.questions:
            parse_success = False

        # 4. Filter duplicate questions first
        unique_questions, discarded_duplicates = filter_duplicate_questions(parsed_response.questions)
        
        discarded_items = list(discarded_duplicates)
        valid_questions: List[Dict[str, Any]] = []

        # 5. Defensive grounding & option validation on each question
        for q in unique_questions:
            # Option validation
            opt_valid, opt_reason = validate_question_options(q)
            if not opt_valid:
                discarded_items.append({
                    "question": q.question,
                    "reason": f"Option validation failed: {opt_reason}",
                    "excerpt": q.source_excerpt
                })
                continue

            # Grounding check (Fuzzy substring match >= 0.85)
            grounded_valid, ground_reason, matched_chunk_id, sim_score = validate_question_grounding(
                question=q,
                source_chunks=retrieved,
                similarity_threshold=0.85
            )

            if not grounded_valid:
                discarded_items.append({
                    "question": q.question,
                    "reason": f"Grounding validation failed: {ground_reason}",
                    "excerpt": q.source_excerpt,
                    "similarity_score": round(sim_score, 3)
                })
                continue

            # Question passed all checks!
            valid_questions.append({
                "question": q,
                "source_chunk_id": matched_chunk_id,
                "similarity_score": sim_score
            })

        # Determine quiz title
        skill_name = request.skill_id.replace('_', ' ').title()
        quiz_title = f"{skill_name} Assessment ({request.difficulty.capitalize()})"

        # 6. Persist Quiz and Questions to DB
        new_quiz = Quiz(
            title=quiz_title,
            source_material_id=request.material_id,
            linked_skill_id=request.skill_id,
            difficulty=request.difficulty,
            question_count=len(valid_questions),
            generation_model=settings.GEMINI_MODEL,
            generation_notes=parsed_response.generation_notes
        )
        db.add(new_quiz)
        db.flush()

        for item in valid_questions:
            q: GeneratedQuestion = item["question"]
            qq = QuizQuestion(
                quiz_id=new_quiz.id,
                question_text=q.question,
                options=q.options,
                correct_option_index=q.correct_index,
                explanation=q.explanation,
                source_chunk_id=item["source_chunk_id"],
                source_excerpt=q.source_excerpt
            )
            db.add(qq)

        # 7. Record Generation Audit Log
        gen_log = GenerationLog(
            quiz_id=new_quiz.id,
            raw_model_response=raw_response_text or (parsed_response.model_dump_json() if hasattr(parsed_response, "model_dump_json") else str(parsed_response)),
            parse_success=parse_success,
            retry_count=0,
            error_message=error_msg,
            discarded_questions_count=len(discarded_items),
            discarded_reasons=discarded_items
        )
        db.add(gen_log)
        db.commit()
        db.refresh(new_quiz)

        return {
            "quiz": new_quiz,
            "discarded_count": len(discarded_items),
            "generation_notes": parsed_response.generation_notes
        }
