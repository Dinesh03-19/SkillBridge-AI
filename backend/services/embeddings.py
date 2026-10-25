import os
import hashlib
import logging
import uuid
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types
from backend.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    _instance = None

    def __init__(self):
        self.use_qdrant = settings.VECTOR_STORE == "qdrant"
        if self.use_qdrant:
            if not settings.QDRANT_URL or not settings.QDRANT_API_KEY:
                raise RuntimeError("QDRANT_URL and QDRANT_API_KEY are required when VECTOR_STORE=qdrant.")
            if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("your_"):
                raise RuntimeError("GEMINI_API_KEY must be configured to generate production embeddings.")

            from qdrant_client import QdrantClient, models

            self.qdrant_client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
                timeout=20
            )
            self.qdrant_models = models
            if not self.qdrant_client.collection_exists(settings.QDRANT_COLLECTION):
                try:
                    self.qdrant_client.create_collection(
                        collection_name=settings.QDRANT_COLLECTION,
                        vectors_config=models.VectorParams(
                            size=settings.EMBEDDING_DIMENSION,
                            distance=models.Distance.COSINE
                        )
                    )
                except Exception:
                    if not self.qdrant_client.collection_exists(settings.QDRANT_COLLECTION):
                        raise
            self.embedding_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            return

        self.use_st = False
        if os.environ.get("USE_FAST_EMBED") != "1":
            try:
                from sentence_transformers import SentenceTransformer
                print("Loading SentenceTransformer ('all-MiniLM-L6-v2')...", flush=True)
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
                self.use_st = True
                print("✓ SentenceTransformer loaded successfully.", flush=True)
            except Exception as e:
                print(f"Notice: Running in lightweight deterministic embedding mode: {e}", flush=True)
                self.use_st = False
        else:
            print("Running in fast embedding mode.", flush=True)
        
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "ChromaDB is only available in local development. Configure VECTOR_STORE=qdrant for deployment."
            ) from exc

        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_or_create_collection(
            name=settings.QDRANT_COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _pseudo_embed(self, text: str, dim: int = 384) -> List[float]:
        """High-entropy normalized deterministic embedding for lightweight environments."""
        import math
        vec = [0.0] * dim
        words = text.lower().split()
        for i, word in enumerate(words):
            h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
            for d in range(dim):
                weight = ((h >> (d % 60)) & 0xFF) / 255.0 - 0.5
                vec[d] += weight * (1.0 / (math.log(i + 2)))
        # Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        else:
            vec[0] = 1.0
        return vec

    def generate_embeddings(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Generate normalized embeddings for given texts."""
        if self.use_qdrant:
            result: List[List[float]] = []
            for start in range(0, len(texts), 100):
                batch = texts[start:start + 100]
                response = self.embedding_client.models.embed_content(
                    model=settings.EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=settings.EMBEDDING_DIMENSION
                    )
                )
                if not response.embeddings:
                    raise RuntimeError("Gemini returned no document embeddings.")
                result.extend([embedding.values for embedding in response.embeddings])
            return result

        if self.use_st:
            try:
                embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
                return embeddings.tolist()
            except Exception as e:
                print(f"Fallback to pseudo embed on ST error: {e}")
        
        return [self._pseudo_embed(t) for t in texts]

    def add_chunks(self, chunks: List[Dict[str, Any]], material_id: int, skill_id: str, doc_title: str) -> List[str]:
        """Embed and index document chunks in the configured vector store."""
        if not chunks:
            return []

        ids = [f"mat_{material_id}_chunk_{c['chunk_index']}" for c in chunks]
        texts = [c["chunk_text"] for c in chunks]
        metadatas = [
            {
                "material_id": material_id,
                "skill_id": skill_id,
                "chunk_index": c["chunk_index"],
                "doc_title": doc_title,
                "token_count": c.get("token_count", 0)
            }
            for c in chunks
        ]

        if self.use_qdrant:
            vectors = self.generate_embeddings(texts, task_type="RETRIEVAL_DOCUMENT")
            points = [
                self.qdrant_models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, embedding_id)),
                    vector=vector,
                    payload={**metadata, "embedding_id": embedding_id, "chunk_text": text}
                )
                for embedding_id, vector, metadata, text in zip(ids, vectors, metadatas, texts)
            ]
            self.qdrant_client.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=points,
                wait=True
            )
            return ids

        embeddings = self.generate_embeddings(texts)

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

        return ids

    def retrieve_relevant_chunks(
        self,
        query: str,
        skill_id: Optional[str] = None,
        material_id: Optional[int] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve top-k relevant chunks from the configured vector store."""
        if self.use_qdrant:
            conditions = []
            if skill_id:
                conditions.append(self.qdrant_models.FieldCondition(
                    key="skill_id",
                    match=self.qdrant_models.MatchValue(value=skill_id)
                ))
            if material_id is not None:
                conditions.append(self.qdrant_models.FieldCondition(
                    key="material_id",
                    match=self.qdrant_models.MatchValue(value=material_id)
                ))
            response = self.qdrant_client.query_points(
                collection_name=settings.QDRANT_COLLECTION,
                query=self.generate_embeddings([query], task_type="RETRIEVAL_QUERY")[0],
                query_filter=self.qdrant_models.Filter(must=conditions) if conditions else None,
                limit=top_k,
                with_payload=True
            )
            return [
                {
                    "id": point.payload["embedding_id"],
                    "text": point.payload.get("chunk_text", ""),
                    "metadata": point.payload,
                    "distance": 1 - point.score
                }
                for point in response.points
            ]

        where_filter = {}
        if skill_id and material_id:
            where_filter = {"$and": [{"skill_id": skill_id}, {"material_id": material_id}]}
        elif skill_id:
            where_filter = {"skill_id": skill_id}
        elif material_id:
            where_filter = {"material_id": material_id}

        query_embedding = self.generate_embeddings([query])[0]

        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = self.collection.query(**query_kwargs)

        retrieved = []
        if results and results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                retrieved.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results and results["distances"] else None
                })
        return retrieved

    def delete_material_chunks(self, material_id: int):
        """Remove all vectors associated with a material."""
        if self.use_qdrant:
            self.qdrant_client.delete(
                collection_name=settings.QDRANT_COLLECTION,
                points_selector=self.qdrant_models.FilterSelector(
                    filter=self.qdrant_models.Filter(
                        must=[self.qdrant_models.FieldCondition(
                            key="material_id",
                            match=self.qdrant_models.MatchValue(value=material_id)
                        )]
                    )
                ),
                wait=True
            )
            return

        try:
            self.collection.delete(where={"material_id": material_id})
        except Exception:
            logger.exception("Failed to remove material chunks from ChromaDB.")
            raise
