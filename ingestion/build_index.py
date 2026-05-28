"""
Build the ChromaDB vector index for retrieval.

For each book in data/books/:
  1. Split into ~400-800 character chunks (paragraph-aware, scene-aware for plays)
  2. Embed each chunk with multilingual sentence-transformer
  3. Store in ChromaDB with full metadata

The embedding model (paraphrase-multilingual-MiniLM-L12-v2) handles BOTH
Korean and English in the same embedding space, so a Korean mood query
can match an English passage. Perfect for our use case.

Output: data/chroma/ (committed to repo so deployed app boots fast)
"""
import json
import re
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings

ROOT = Path(__file__).resolve().parent.parent
BOOKS_DIR = ROOT / "data" / "books"
CORPUS_JSON = ROOT / "data" / "corpus.json"
CHROMA_DIR = ROOT / "data" / "chroma"

# Embedding model — handles 100+ languages including Korean
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "passages"

# Chunk size targets — tuned for "scene-sized" passages
CHUNK_MIN = 200    # chars; below this is too short to be a meaningful passage
CHUNK_TARGET = 600 # chars; sweet spot for a single dramatic moment
CHUNK_MAX = 1200   # chars; above this is too long for a card


# ============================================================================
# CHUNKING
# ============================================================================

def split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (separated by blank lines)."""
    # Normalize line endings, collapse 3+ newlines to 2
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    paras = [p.strip() for p in text.split("\n\n")]
    return [p for p in paras if p]


def chunk_paragraphs(paragraphs: list[str]) -> list[str]:
    """
    Combine paragraphs into chunks of roughly CHUNK_TARGET size.
    Never split a paragraph; just group adjacent ones.
    """
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        plen = len(para)

        # Skip pure noise
        if plen < 5:
            continue

        # If the paragraph itself is huge, emit it alone (rare; happens in long monologues)
        if plen > CHUNK_MAX:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            chunks.append(para)
            continue

        # If adding this paragraph would push us over MAX, close current chunk first
        if current_len + plen > CHUNK_MAX and current_len >= CHUNK_MIN:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = plen
        else:
            current.append(para)
            current_len += plen + 2  # +2 for the joining "\n\n"

            # If we've reached target size, close this chunk
            if current_len >= CHUNK_TARGET:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0

    # Don't forget any remaining content
    if current and current_len >= CHUNK_MIN:
        chunks.append("\n\n".join(current))

    return chunks


# ============================================================================
# ACT/SCENE DETECTION (for plays)
# ============================================================================

ACT_PATTERN = re.compile(
    r"^\s*(?:ACT|act)\s+([IVXLCDM]+|\d+|[A-Z]+)\b.*$",
    re.MULTILINE,
)
SCENE_PATTERN = re.compile(
    r"^\s*(?:SCENE|Scene)\s+([IVXLCDM]+|\d+|[A-Z]+)\b.*$",
    re.MULTILINE,
)


def detect_act_scene(text_so_far: str) -> tuple[str | None, str | None]:
    """
    Given the cumulative text up to (and including) a chunk,
    return the latest ACT and SCENE markers found.
    Used to attribute each chunk to a play's act/scene.
    """
    act_matches = list(ACT_PATTERN.finditer(text_so_far))
    scene_matches = list(SCENE_PATTERN.finditer(text_so_far))

    act = act_matches[-1].group(1) if act_matches else None
    scene = scene_matches[-1].group(1) if scene_matches else None
    return act, scene


# ============================================================================
# INDEX BUILD
# ============================================================================

def build_index():
    if not CORPUS_JSON.exists():
        raise FileNotFoundError(
            f"{CORPUS_JSON} not found. Run fetch_gutenberg.py first."
        )

    corpus = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    print(f"Building index from {len(corpus)} books")
    print(f"Embedding model: {EMBED_MODEL}")
    print(f"Output: {CHROMA_DIR}")
    print("-" * 60)

    # Reset Chroma directory for a clean build
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    # Drop existing collection if any
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    # Process each book
    total_chunks = 0
    for book in corpus:
        gid = book["gutenberg_id"]
        book_path = BOOKS_DIR / f"{gid}.txt"
        if not book_path.exists():
            print(f"  ✗ {gid:>5} text file missing ({book['title']})")
            continue

        text = book_path.read_text(encoding="utf-8")
        paragraphs = split_into_paragraphs(text)
        chunks = chunk_paragraphs(paragraphs)

        # Build chunk records
        ids = []
        documents = []
        metadatas = []

        # Track cumulative text for act/scene detection
        cumulative_pos = 0

        for i, chunk in enumerate(chunks):
            chunk_id = f"{gid}-{i:04d}"
            # Find chunk position in original text for act/scene attribution
            chunk_start = text.find(chunk[:50], cumulative_pos)
            if chunk_start >= 0:
                cumulative_pos = chunk_start
                act, scene = detect_act_scene(text[: chunk_start + len(chunk)])
            else:
                act, scene = None, None

            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "gutenberg_id": gid,
                "title": book["title"],
                "author": book["author"],
                "language": book["language"],
                "genre": book["genre"],
                "act": act or "",
                "scene": scene or "",
                "chunk_index": i,
                "source_url": book["source_url"],
            })

        # Batch insert (Chroma will embed automatically)
        if ids:
            # Insert in batches of 100 to avoid memory issues
            BATCH = 100
            for start in range(0, len(ids), BATCH):
                end = min(start + BATCH, len(ids))
                collection.add(
                    ids=ids[start:end],
                    documents=documents[start:end],
                    metadatas=metadatas[start:end],
                )

        total_chunks += len(chunks)
        print(f"  ✓ {gid:>5} {len(chunks):>4} chunks ({book['title']})")

    print("-" * 60)
    print(f"Total chunks indexed: {total_chunks}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Chroma persisted to: {CHROMA_DIR}")


if __name__ == "__main__":
    build_index()
