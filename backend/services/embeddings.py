import os
import sys
import hashlib
from typing import List, Dict, Any, Optional
import chromadb
from backend.config import settings

class EmbeddingService:
    _instance = None

    def __init__(self):
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
        
        # Persistent ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_or_create_collection(
            name="skillbridge_materials",
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

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized embeddings for given texts."""
        if self.use_st:
            try:
                embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
                return embeddings.tolist()
            except Exception as e:
                print(f"Fallback to pseudo embed on ST error: {e}")
        
        return [self._pseudo_embed(t) for t in texts]

    def add_chunks(self, chunks: List[Dict[str, Any]], material_id: int, skill_id: str, doc_title: str) -> List[str]:
        """Embed and index document chunks in ChromaDB."""
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
        """Retrieve top-k most relevant chunks using ChromaDB."""
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
        """Remove chunks associated with a material from ChromaDB."""
        try:
            self.collection.delete(where={"material_id": material_id})
        except Exception as e:
            print(f"Error removing material chunks from Chroma: {e}")
