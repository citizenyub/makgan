# 막간 (Makgan)

> 지금 마음에 가까운 한 문장을 만나다.
> A small AI that retrieves a public-domain literary passage matching your current mood — then explains why it fits, in Korean.

**Status:** demo MVP · sprint output for Curtaincall team · 2026-05-27
**Live:** `https://makgan.streamlit.app` (after deploy)

---

## What it does

1. User picks a mood chip (지침 · 결심 · 이별 · 나다움 · 망설임 — or types their own)
2. RAG retrieves a thematically matching passage from a pre-built corpus of public-domain literature (Project Gutenberg)
3. Claude Sonnet 4.7 generates Korean commentary tailored to the user's mood
4. Card UI displays: verbatim quote · attribution · scene context · AI commentary
5. User can reroll, save, or share

## Why

This is a **sprint demo** exploring a RAG + LLM-generation approach for Curtaincall — the team's main product (curated card-form literary content). The iOS app uses a different architecture (Supabase + pre-curated cards); this is a parallel exploration of whether retrieval-from-corpus + on-the-fly generation could be a viable alternative or supplement.

## Legal safety

- **Only public domain works** are used (Project Gutenberg).
- **Verbatim quotes are unmodified** — preserved exactly as published, displayed with a "원문 그대로 · 변형 없음" badge.
- **Korean translations** of English works are AI-generated for display only; the verbatim English text is preserved as the source of truth.
- **AI commentary is clearly labeled** ("AI 해설") to distinguish it from the original work.

## Setup (local)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/makgan.git
cd makgan

# 2. Install
pip install -r requirements.txt

# 3. Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Build the corpus (one-time, ~10 min)
python ingestion/fetch_gutenberg.py
python ingestion/build_index.py

# 5. Run
streamlit run app/main.py
```

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (public)
2. Go to https://share.streamlit.io
3. Click "Create app" → select your repo, branch `main`, file `app/main.py`
4. In "Advanced settings" → Secrets, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
5. Deploy. URL will be `https://<app-name>.streamlit.app`.

The pre-built ChromaDB index is committed to the repo (`data/chroma/`) so the deployed app boots without re-ingesting.

## Architecture

```
┌─────────────────────────────────────────┐
│ One-time (local laptop):                │
│   fetch_gutenberg.py  →  raw texts     │
│   build_index.py      →  ChromaDB      │
│                          (committed)   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ Runtime (Streamlit Cloud):              │
│   User mood → embed → retrieve top-K   │
│   Top-K + mood → Sonnet 4.7 → card     │
└─────────────────────────────────────────┘
```

## Project structure

```
makgan/
├── README.md
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── config.toml          # theme matching the 막간 design
├── ingestion/
│   ├── fetch_gutenberg.py   # Phase 1: download + clean texts
│   └── build_index.py       # Phase 2: chunk + embed + Chroma
├── app/
│   ├── main.py              # Streamlit entry point
│   ├── retrieval.py         # ChromaDB queries
│   ├── generation.py        # Sonnet prompt + call
│   └── ui.py                # card layout components
└── data/
    ├── books/               # raw .txt files (gitignored if too big)
    ├── corpus.json          # metadata for each book
    └── chroma/              # vector DB (committed)
```

## Status of v0.1 corpus

Initial seed of ~30-40 plays/dramatic novels in PD:
- Shakespeare (all plays)
- Ibsen — A Doll's House, Hedda Gabler, Ghosts
- Chekhov — The Seagull, Three Sisters, Uncle Vanya
- Wilde — The Importance of Being Earnest, Salomé
- Sophocles — Oedipus Rex, Antigone
- Korean public domain: 이광수 무정 (1917), 김유정 단편 (1908-1937)*

\* Korean PD verification per author death date + 70 years (Korean copyright law, post-2013).
