"""ChromaDB retrieval logic. Cached at module level — load once per process."""
from pathlib import Path
from typing import List, Dict

import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "data" / "chroma"
COLLECTION_NAME = "passages"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


_client = None
_collection = None


def _get_collection():
    """Lazy-init ChromaDB client (Streamlit reruns on every interaction)."""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )
        _collection = _client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embed_fn,
        )
    return _collection


def retrieve(query: str, k: int = 5) -> List[Dict]:
    """
    Retrieve top-k thematically relevant passages.

    Returns list of dicts:
      {id, text, title, author, language, genre, act, scene, distance}

    Lower distance = more relevant (cosine distance).
    """
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=k)

    hits = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        hits.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "distance": results["distances"][0][i],
            **meta,
        })
    return hits


def corpus_stats() -> Dict:
    """Get basic stats for display in the UI footer."""
    collection = _get_collection()
    count = collection.count()
    return {"total_passages": count}
