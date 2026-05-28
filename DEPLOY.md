# Deploy 막간 to Streamlit Cloud

Step-by-step. You should be live in ~30 minutes if no surprises.

---

## Part 1 — Local setup (on your Mac)

### 1.1 Create new repo on GitHub

1. Go to https://github.com/new
2. Repo name: **`makgan`** (or whatever you want)
3. **Public** (Streamlit Community Cloud free tier requires public repos)
4. **Don't initialize** with README/gitignore — we have our own
5. Click "Create repository"
6. Note the SSH/HTTPS URL it gives you (e.g. `git@github.com:yub-hahm/makgan.git`)

### 1.2 Push the makgan code

```bash
# Move the makgan/ folder I generated to wherever you want it locally
# (e.g. ~/Code/makgan)

cd ~/Code/makgan

# Initialize git
git init
git branch -M main

# Stage everything
git add .
git status   # sanity check — should NOT include secrets.toml or data/books/

# First commit
git commit -m "initial commit — 막간 v0.1 MVP"

# Connect to GitHub
git remote add origin git@github.com:YOUR_USERNAME/makgan.git
# OR if you use HTTPS:
# git remote add origin https://github.com/YOUR_USERNAME/makgan.git

# Push
git push -u origin main
```

### 1.3 Set up local environment

```bash
# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

This takes 2-3 min — `sentence-transformers` and `chromadb` are chunky.

### 1.4 Set your API key

```bash
# Copy the example secrets file
cp .streamlit/secrets.example.toml .streamlit/secrets.toml

# Edit secrets.toml — replace the placeholder with your real key
# (use your editor of choice)
nano .streamlit/secrets.toml
```

Your `secrets.toml` should look like:
```toml
ANTHROPIC_API_KEY = "sk-ant-api03-XXXX...your-real-key..."
```

**Important:** `secrets.toml` is in `.gitignore` — it won't be committed.

### 1.5 Build the corpus (one-time)

```bash
# Fetch ~35 public-domain plays/novels from Gutenberg
# This takes ~5-10 min (we rate-limit to 1 req/2sec to be polite)
python ingestion/fetch_gutenberg.py

# Build the ChromaDB vector index
# This takes ~3-5 min (downloads the embedding model on first run, ~470MB)
python ingestion/build_index.py
```

You should see:
- `data/books/` filled with ~35 .txt files (total ~30-50 MB)
- `data/corpus.json` with metadata
- `data/chroma/` with the vector DB (~50-100 MB)

### 1.6 Test locally

```bash
streamlit run app/main.py
```

Browser opens at http://localhost:8501. Click a mood chip — you should get a card in 5-10 seconds.

If it works locally, you're ready to deploy.

### 1.7 Commit the corpus + push

The corpus needs to be in git for Streamlit Cloud to use it:

```bash
# Books folder is in .gitignore (too large). Only commit the metadata + Chroma DB.
git add data/corpus.json
git add data/chroma/
git add -A   # everything else

git status   # sanity check

git commit -m "build: corpus + Chroma index (v0.1, ~35 works)"
git push
```

If the Chroma DB is >100MB, GitHub may complain. If so, see the **Troubleshooting** section below.

---

## Part 2 — Deploy to Streamlit Cloud

### 2.1 Sign in

1. Go to https://share.streamlit.io
2. Click "Continue with GitHub"
3. Authorize Streamlit to access your repos

### 2.2 Create the app

1. Click **"Create app"** (top right)
2. Click **"Deploy a public app from GitHub"**
3. Fill in:
   - **Repository:** `YOUR_USERNAME/makgan`
   - **Branch:** `main`
   - **Main file path:** `app/main.py`
   - **App URL (custom):** `makgan` (so URL is `https://makgan.streamlit.app`)
4. Click **"Advanced settings…"**
5. Under **Secrets**, paste:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-api03-YOUR-KEY-HERE"
   ```
6. Click **Deploy**

### 2.3 Wait for build

First deploy takes 5-10 min — Streamlit pulls your repo, installs `requirements.txt`, and starts the app. You'll see logs scroll by. If something goes wrong, the error usually appears in red at the bottom.

### 2.4 Share

Your URL is `https://makgan.streamlit.app` (or whatever you set). Share it.

---

## Troubleshooting

### ChromaDB is too big to push to GitHub (>100MB)

GitHub has a 100MB file limit. The Chroma DB might exceed this with many books.

**Fix option A:** Use Git LFS for the `chroma_db.sqlite3` file:
```bash
git lfs install
git lfs track "data/chroma/**"
git add .gitattributes
git add data/chroma/
git commit -m "use git LFS for chroma"
git push
```

**Fix option B:** Reduce corpus size — edit `ingestion/fetch_gutenberg.py`, comment out books in `SEED_BOOKS`, re-run both ingestion scripts.

**Fix option C:** Have the deployed app re-build the index on first start. Add to your `main.py`:
```python
if not Path("data/chroma/chroma.sqlite3").exists():
    import ingestion.build_index as bi
    bi.build_index()
```
But this makes cold starts ~5min. Not recommended.

### Streamlit Cloud build fails: "module not found"

Check `requirements.txt` — every imported package must be there.

### "Anthropic API key not configured" error in production

Go to Streamlit Cloud → your app → ⋮ menu → **Settings** → **Secrets** — make sure the key is there in toml format.

### The app is slow on first card

First retrieval after deploy/restart triggers `sentence-transformers` to download the embedding model (~470MB) and load it into memory. **First card: 30-60 seconds. Subsequent cards: 5-10 seconds.**

For demo purposes, hit the URL yourself first, click a mood once, *then* share the URL. Subsequent visitors will get a warm app.

### Korean text shows as boxes/squares

The card UI uses `Nanum Myeongjo` / `Apple SD Gothic Neo` fonts. On macOS/iOS browsers these render correctly. On Windows or Linux you may want to add a Google Fonts import. Let me know if needed.

---

## Cost expectation

- **Streamlit Community Cloud:** free
- **Anthropic API:** Sonnet 4.6 is ~$3/$15 per million input/output tokens
- **Per card generated:** ~3,000 input tokens (5 candidate passages) + ~400 output tokens
  - = $0.009 input + $0.006 output = **~$0.015 per card**
- **Demo budget:** $5 covers ~330 cards. Plenty for showing the project.

---

## What to do after deploy

1. **Test the URL yourself** — make sure cards render correctly across all 5 moods
2. **Take screenshots** of the deployed app for your portfolio / class submission
3. **Share with the team** for feedback before pitching
4. **Watch the Anthropic console** for actual cost on first 50 cards — calibrate from there

Good luck.
