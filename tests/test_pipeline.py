import unittest
import os
import sys
from unittest.mock import patch

# Ensure root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.schemas import GeneratedQuestion
from backend.services.parser import chunk_text
from backend.services.validation import (
    validate_question_grounding,
    validate_question_options,
    filter_duplicate_questions
)
from backend.services.embeddings import EmbeddingService

class TestQuizPipeline(unittest.TestCase):

    def test_chunking_sliding_window(self):
        sample_text = " ".join([f"word{i}" for i in range(1000)])
        chunks = chunk_text(sample_text, target_chunk_size=400, overlap_size=50)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertLessEqual(chunks[0]["token_count"], 450)
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertEqual(chunks[1]["chunk_index"], 1)

    def test_grounding_validation_positive(self):
        source_chunk = {
            "id": "chunk_1",
            "text": "In the rural sector, First Stage Units (FSUs) are census villages as per the latest Population Census."
        }
        question = GeneratedQuestion(
            question="What are the FSUs in the rural sector?",
            options=["Census villages", "Gram Panchayats", "Districts", "Blocks"],
            correct_index=0,
            explanation="Directly confirmed by text.",
            source_excerpt="First Stage Units (FSUs) are census villages as per the latest Population Census."
        )
        is_valid, reason, matched_chunk_id, sim = validate_question_grounding(question, [source_chunk], similarity_threshold=0.85)
        self.assertTrue(is_valid)
        self.assertGreaterEqual(sim, 0.85)

    def test_grounding_validation_rejection_of_hallucination(self):
        source_chunk = {
            "id": "chunk_1",
            "text": "In the rural sector, First Stage Units (FSUs) are census villages as per the latest Population Census."
        }
        # Deliberate hallucination not present in source text
        hallucinated_question = GeneratedQuestion(
            question="What is the minimum quantum computer requirement for NSSO encryption?",
            options=["128 Qubits", "256 Qubits", "512 Qubits", "1024 Qubits"],
            correct_index=1,
            explanation="Fabricated fact.",
            source_excerpt="All statistical field laptops must utilize 256 Qubit post-quantum lattice encryption keys."
        )
        is_valid, reason, matched_chunk_id, sim = validate_question_grounding(hallucinated_question, [source_chunk], similarity_threshold=0.85)
        self.assertFalse(is_valid)
        self.assertLess(sim, 0.50)

    def test_option_validation(self):
        valid_q = GeneratedQuestion(
            question="Valid question?",
            options=["Option A", "Option B", "Option C", "Option D"],
            correct_index=2,
            explanation="Valid",
            source_excerpt="Valid quote."
        )
        ok, _ = validate_question_options(valid_q)
        self.assertTrue(ok)

        # Bad: Only 3 options
        bad_q = GeneratedQuestion(
            question="Bad question?",
            options=["A", "B", "C"],
            correct_index=0,
            explanation="Invalid",
            source_excerpt="Valid quote."
        )
        ok, err = validate_question_options(bad_q)
        self.assertFalse(ok)

    def test_duplicate_question_filtering(self):
        q1 = GeneratedQuestion(
            question="What are the First Stage Units in rural NSSO surveys?",
            options=["A", "B", "C", "D"],
            correct_index=0,
            explanation="",
            source_excerpt="Source A"
        )
        q2 = GeneratedQuestion(
            question="What are the First Stage Units in rural NSSO surveys?",
            options=["A", "B", "C", "D"],
            correct_index=0,
            explanation="",
            source_excerpt="Source A"
        )
        q3 = GeneratedQuestion(
            question="Explain the hot-deck imputation methodology used in NSO surveys.",
            options=["A", "B", "C", "D"],
            correct_index=1,
            explanation="",
            source_excerpt="Source B"
        )
        unique, discarded = filter_duplicate_questions([q1, q2, q3])
        self.assertEqual(len(unique), 2)
        self.assertEqual(len(discarded), 1)

    def test_qdrant_vector_store_round_trip(self):
        from qdrant_client import QdrantClient, models

        client = QdrantClient(":memory:")
        client.create_collection(
            collection_name="test_materials",
            vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE)
        )

        service = object.__new__(EmbeddingService)
        service.use_qdrant = True
        service.qdrant_client = client
        service.qdrant_models = models
        service.generate_embeddings = lambda texts, task_type="RETRIEVAL_DOCUMENT": [
            [1.0, 0.0, 0.0] for _ in texts
        ]

        try:
            with patch("backend.services.embeddings.settings.QDRANT_COLLECTION", "test_materials"):
                ids = service.add_chunks(
                    [{"chunk_index": 0, "chunk_text": "Survey sampling rules", "token_count": 3}],
                    material_id=7,
                    skill_id="sampling",
                    doc_title="Sampling Manual"
                )
                results = service.retrieve_relevant_chunks(
                    "sampling rules",
                    skill_id="sampling",
                    material_id=7
                )

                self.assertEqual(ids, ["mat_7_chunk_0"])
                self.assertEqual(results[0]["id"], "mat_7_chunk_0")
                self.assertEqual(results[0]["text"], "Survey sampling rules")

                service.delete_material_chunks(7)
                self.assertEqual(
                    service.retrieve_relevant_chunks("sampling rules", skill_id="sampling"),
                    []
                )
        finally:
            client.close()

if __name__ == "__main__":
    unittest.main()
