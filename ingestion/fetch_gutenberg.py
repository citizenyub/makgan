"""
Fetch curated set of public-domain dramatic works from Project Gutenberg.

We use a hand-picked seed list (not a crawler) because:
- PG actively discourages crawlers via robots.txt + rate limiting
- For an MVP corpus we want quality > quantity (50 great plays > 5000 mediocre books)
- Hand-curation lets us verify each work's PD status before fetching

Each book is fetched as plain UTF-8 text from PG's "Plain Text UTF-8" link.
Standard URL pattern:
  https://www.gutenberg.org/cache/epub/<ID>/pg<ID>.txt

Output:
- data/books/<id>.txt        — raw text with PG header/footer stripped
- data/corpus.json            — metadata for each book

Run once. Re-run to add new books to the list.
"""
import json
import time
import re
import os
from pathlib import Path
import requests

# Project root (this file is in ingestion/, project root is one level up)
ROOT = Path(__file__).resolve().parent.parent
BOOKS_DIR = ROOT / "data" / "books"
CORPUS_JSON = ROOT / "data" / "corpus.json"

# Politeness — PG asks for reasonable rate. 1 req per 2 sec is plenty conservative.
RATE_LIMIT_SECONDS = 2.0
USER_AGENT = "MakganMVP/0.1 (research demo; contact: yub.hahm@gmail.com)"


# ============================================================================
# CURATED SEED LIST
# ============================================================================
# Each entry: (gutenberg_id, title, author, lang, genre, notes)
# Only works confirmed PD in US AND author's home country.

SEED_BOOKS = [
    # === SHAKESPEARE (d. 1616, deeply PD everywhere) ===
    (1524, "Hamlet", "William Shakespeare", "en", "play", "tragedy"),
    (1112, "Romeo and Juliet", "William Shakespeare", "en", "play", "tragedy/romance"),
    (1129, "Macbeth", "William Shakespeare", "en", "play", "tragedy"),
    (1135, "King Lear", "William Shakespeare", "en", "play", "tragedy"),
    (1531, "A Midsummer Night's Dream", "William Shakespeare", "en", "play", "comedy"),
    (1515, "Much Ado About Nothing", "William Shakespeare", "en", "play", "comedy"),
    (1533, "The Tempest", "William Shakespeare", "en", "play", "romance"),
    (1110, "As You Like It", "William Shakespeare", "en", "play", "comedy"),

    # === IBSEN (d. 1906, PD) ===
    (2542, "A Doll's House", "Henrik Ibsen", "en", "play", "drama; trans. from Norwegian"),
    (4093, "Hedda Gabler", "Henrik Ibsen", "en", "play", "drama"),
    (8120, "Ghosts", "Henrik Ibsen", "en", "play", "drama"),

    # === CHEKHOV (d. 1904, PD) ===
    (1754, "The Seagull", "Anton Chekhov", "en", "play", "drama; trans. from Russian"),
    (7986, "The Cherry Orchard", "Anton Chekhov", "en", "play", "drama"),
    (1755, "Three Sisters", "Anton Chekhov", "en", "play", "drama"),
    (1756, "Uncle Vanya", "Anton Chekhov", "en", "play", "drama"),

    # === WILDE (d. 1900, PD) ===
    (844, "The Importance of Being Earnest", "Oscar Wilde", "en", "play", "comedy"),
    (854, "An Ideal Husband", "Oscar Wilde", "en", "play", "comedy"),
    (790, "Lady Windermere's Fan", "Oscar Wilde", "en", "play", "comedy"),
    (42704, "Salomé", "Oscar Wilde", "en", "play", "tragedy"),

    # === GREEK CLASSICS (ancient, deeply PD) ===
    (31, "Oedipus King", "Sophocles", "en", "play", "tragedy; trans."),
    (27673, "Antigone", "Sophocles", "en", "play", "tragedy; trans."),
    (8418, "Medea", "Euripides", "en", "play", "tragedy; trans."),

    # === SHAW (selected early works in US PD) ===
    (3825, "Pygmalion", "George Bernard Shaw", "en", "play", "comedy"),
    (4736, "Caesar and Cleopatra", "George Bernard Shaw", "en", "play", "history"),

    # === DRAMATIC NOVELS (great for scene extraction) ===
    (1342, "Pride and Prejudice", "Jane Austen", "en", "novel", "romance"),
    (768, "Wuthering Heights", "Emily Brontë", "en", "novel", "gothic romance"),
    (1260, "Jane Eyre", "Charlotte Brontë", "en", "novel", "romance/coming-of-age"),
    (98, "A Tale of Two Cities", "Charles Dickens", "en", "novel", "historical"),
    (158, "Emma", "Jane Austen", "en", "novel", "romance"),
    (2701, "Moby Dick", "Herman Melville", "en", "novel", "adventure"),
    (84, "Frankenstein", "Mary Shelley", "en", "novel", "gothic"),
    (174, "The Picture of Dorian Gray", "Oscar Wilde", "en", "novel", "gothic"),
    (43, "The Strange Case of Dr. Jekyll and Mr. Hyde", "Robert Louis Stevenson", "en", "novel", "gothic"),
    (2554, "Crime and Punishment", "Fyodor Dostoyevsky", "en", "novel", "psychological"),
    (28054, "The Brothers Karamazov", "Fyodor Dostoyevsky", "en", "novel", "psychological"),
    (1399, "Anna Karenina", "Leo Tolstoy", "en", "novel", "tragedy/romance"),
]


# ============================================================================
# FETCH + CLEAN
# ============================================================================

def fetch_book_text(gutenberg_id: int) -> str:
    """Download a single book's plain-text UTF-8 version."""
    url = f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt"
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


# Project Gutenberg wraps every book with a standard header and footer.
# We need to strip those to get the actual text.
PG_START_MARKER = re.compile(
    r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^\*]+\*\*\*",
    re.IGNORECASE,
)
PG_END_MARKER = re.compile(
    r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^\*]+\*\*\*",
    re.IGNORECASE,
)


def strip_pg_boilerplate(text: str) -> str:
    """Remove PG header/footer, leaving just the work itself."""
    # Find the START marker — everything before it is PG metadata
    start_match = PG_START_MARKER.search(text)
    if start_match:
        text = text[start_match.end():]

    # Find the END marker — everything after it is PG license boilerplate
    end_match = PG_END_MARKER.search(text)
    if end_match:
        text = text[:end_match.start()]

    return text.strip()


def fetch_and_save(book_meta: tuple) -> dict | None:
    """Fetch one book, clean it, save to disk. Return metadata dict or None on failure."""
    gid, title, author, lang, genre, notes = book_meta
    out_path = BOOKS_DIR / f"{gid}.txt"

    # Skip if already downloaded
    if out_path.exists():
        size = out_path.stat().st_size
        if size > 1000:  # sanity: real books are >1KB after stripping
            print(f"  ✓ {gid:>5} cached  ({title})")
            return {
                "gutenberg_id": gid,
                "title": title,
                "author": author,
                "language": lang,
                "genre": genre,
                "notes": notes,
                "char_count": size,
                "source_url": f"https://www.gutenberg.org/ebooks/{gid}",
            }

    # Fetch
    try:
        raw = fetch_book_text(gid)
    except requests.HTTPError as e:
        print(f"  ✗ {gid:>5} HTTP error ({title}): {e}")
        return None
    except requests.RequestException as e:
        print(f"  ✗ {gid:>5} network error ({title}): {e}")
        return None

    # Clean
    cleaned = strip_pg_boilerplate(raw)
    if len(cleaned) < 1000:
        print(f"  ✗ {gid:>5} suspiciously short ({title}): {len(cleaned)} chars")
        return None

    # Save
    out_path.write_text(cleaned, encoding="utf-8")
    print(f"  ✓ {gid:>5} fetched ({title}) — {len(cleaned):,} chars")

    return {
        "gutenberg_id": gid,
        "title": title,
        "author": author,
        "language": lang,
        "genre": genre,
        "notes": notes,
        "char_count": len(cleaned),
        "source_url": f"https://www.gutenberg.org/ebooks/{gid}",
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    CORPUS_JSON.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {len(SEED_BOOKS)} books from Project Gutenberg")
    print(f"Output: {BOOKS_DIR}")
    print(f"Rate limit: {RATE_LIMIT_SECONDS}s between requests")
    print("-" * 60)

    corpus = []
    success = 0
    for i, book in enumerate(SEED_BOOKS):
        result = fetch_and_save(book)
        if result:
            corpus.append(result)
            success += 1
        # Rate limit — but only if we actually hit the network
        if i < len(SEED_BOOKS) - 1 and not (BOOKS_DIR / f"{book[0]}.txt").exists():
            time.sleep(RATE_LIMIT_SECONDS)

    # Write corpus metadata
    CORPUS_JSON.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("-" * 60)
    print(f"Success: {success}/{len(SEED_BOOKS)}")
    print(f"Metadata written to: {CORPUS_JSON}")
    print(f"Total chars: {sum(c['char_count'] for c in corpus):,}")


if __name__ == "__main__":
    main()
