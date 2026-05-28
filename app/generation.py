"""
Claude Sonnet calls for 막간:
  1. expand_query()  — rewrite the user's free-text feeling into a richer
                       semantic search query (query expansion for better RAG)
  2. generate_card() — take retrieved passages + the user's input,
                       return a structured 막간 card.

Card output schema (JSON):
{
  "quote_original": "...",        # verbatim, exactly as in source
  "quote_translated": "...",      # Korean translation if source was English; null if source is Korean
  "language_original": "en"|"ko",
  "title": "...",
  "author": "...",
  "speaker": "...",              # character speaking (for plays) or null
  "act_scene": "...",            # e.g. "2막 2장" or "Chapter 5" or null
  "scene_context": "...",        # one-line Korean description of the moment
  "ai_commentary": "..."         # 2-3 sentence Korean commentary contextualized to the user's input
}
"""
import json
import os
from typing import List, Dict, Optional

from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"  # current Sonnet, fast + cheap + great with Korean
MAX_TOKENS = 1500
EXPAND_MAX_TOKENS = 300

# Mood label → Korean nuance hint (used by chip shortcuts)
MOOD_HINTS = {
    "지침": "지치고 소진된 상태, 위로와 공감이 필요한 마음",
    "결심": "무언가를 결정하고 행동에 옮기려는 마음",
    "이별": "헤어짐의 슬픔, 그리움, 작별의 감정",
    "나다움": "자기 정체성, 본연의 모습에 대한 탐구",
    "망설임": "결정하지 못하고 흔들리는 마음, 갈등",
}


def expand_query(user_input: str, api_key: Optional[str] = None) -> str:
    """
    Query expansion: turn the user's free-text feeling into a richer
    search query that retrieves better passages.

    The embedding model matches on *meaning*. A short or oblique user input
    ("회사 그만두고 싶다") retrieves better if we first surface the underlying
    themes (escape, freedom, duty vs. self, courage to leave). We ask Sonnet
    to produce a compact, theme-rich Korean phrase — NOT a full answer.

    Returns the expanded query string. On any failure, returns the original
    input unchanged (graceful degradation — retrieval still works).
    """
    if not user_input or not user_input.strip():
        return user_input

    client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""사용자가 지금 자신의 마음을 한 문장으로 적었습니다:

"{user_input}"

이 마음과 정서적으로 공명하는 문학 작품 속 한 장면을 찾으려 합니다.
검색 품질을 높이기 위해, 이 마음의 밑바탕에 있는 **정서적 주제와 상황**을
짧은 한국어 검색 구문으로 확장해 주세요.

규칙:
- 사용자의 표면적 단어가 아니라, 그 아래 깔린 감정·상황·욕구를 포착하세요.
- 예: "회사 그만두고 싶다" → "의무에서 벗어나고 싶은 마음, 자유에 대한 갈망, 떠날 용기, 자신을 위한 선택"
- 예: "그 사람이 보고싶어" → "그리움, 떠난 사람에 대한 사랑, 부재의 고통, 재회를 바라는 마음"
- 한 줄로, 쉼표로 구분된 4-7개의 주제어/구문만 출력하세요.
- 설명, 따옴표, 다른 텍스트 없이 검색 구문만 출력하세요."""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=EXPAND_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        expanded = response.content[0].text.strip()
        # Combine original + expansion — keeps the user's own words in the vector too
        if expanded:
            return f"{user_input} {expanded}"
        return user_input
    except Exception:
        # Graceful fallback — never let expansion failure break the app
        return user_input


def _format_passages_for_prompt(passages: List[Dict]) -> str:
    """Format the top-K retrieved passages as a prompt section."""
    sections = []
    for i, p in enumerate(passages, 1):
        loc = ""
        if p.get("act") and p.get("scene"):
            loc = f" (Act {p['act']}, Scene {p['scene']})"
        sections.append(
            f"[Passage {i}]\n"
            f"Title: {p['title']}\n"
            f"Author: {p['author']}\n"
            f"Language: {p['language']}\n"
            f"Genre: {p['genre']}{loc}\n"
            f"Text:\n{p['text']}\n"
        )
    return "\n---\n\n".join(sections)


def _build_prompt(user_expression: str, passages: List[Dict]) -> str:
    """
    user_expression: what the user told us about their state of mind.
    Either free text ("요즘 일에 치여서 내가 누구였는지 모르겠어") or a mood
    label expanded with its hint ("지침 — 지치고 소진된 상태...").
    """
    passages_str = _format_passages_for_prompt(passages)

    return f"""You are curating a literary card for a Korean app called 막간 (Makgan).

The user described their current state of mind:
"{user_expression}"

Below are {len(passages)} candidate passages retrieved from public-domain works.
Your job:

1. **Choose ONE passage** that best resonates with what the user expressed. Pick the most emotionally resonant one — match the *feeling*, not just surface keywords.
2. **Extract a SHORT quote** (1-4 sentences max, ~30-150 characters) from that passage. This must be a VERBATIM substring of the original text — do not paraphrase, do not modify, do not translate the original.
3. **Identify the speaker** (for plays) or narrator/POV (for novels) if possible.
4. **Write a Korean translation** of the quote if the original is English. Make it literary and natural Korean, not literal word-for-word. If the original is already Korean, set `quote_translated` to null.
5. **Write a one-line Korean scene context** (장면 설명) describing the moment — where, when, who's involved. Example: "발코니에서 로미오와 밤의 작별을 나누며".
6. **Write 2-3 sentences of Korean AI commentary** (AI 해설) that:
   - Speaks to the user as if you are present with them, having heard what they said
   - Connects this passage to what the user expressed — gently, without repeating their words back verbatim
   - Explains why this moment resonates emotionally
   - Does NOT just summarize the plot — it interprets and offers a small turn of insight
   - Sounds like a thoughtful companion, not a literature professor

Return STRICTLY a single valid JSON object with these exact keys:
- `quote_original` (string, verbatim from source)
- `quote_translated` (string in Korean, or null if source is Korean)
- `language_original` ("en" or "ko")
- `title` (string)
- `author` (string)
- `speaker` (string or null)
- `act_scene` (string in Korean like "2막 2장" or "5장" or null)
- `scene_context` (Korean string, ~10-25 chars)
- `ai_commentary` (Korean string, 2-3 sentences, ~80-180 chars)

Do not include any text outside the JSON. Do not wrap in markdown code blocks.

CANDIDATE PASSAGES:

{passages_str}
"""


def generate_card(user_expression: str, passages: List[Dict], api_key: Optional[str] = None) -> Dict:
    """
    Call Sonnet, parse the JSON response, return the card dict.
    `user_expression` is the user's free text or an expanded mood label.
    Raises if the response is not valid JSON.
    """
    client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    prompt = _build_prompt(user_expression, passages)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()

    # Defensive: sometimes the model wraps in ```json...``` despite instructions
    if text.startswith("```"):
        # Strip first and last fence lines
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        text = text.strip()

    try:
        card = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Sonnet returned invalid JSON: {e}\nResponse:\n{text}")

    # Verify verbatim claim — the quote_original must appear in one of the source passages
    quote = card.get("quote_original", "").strip()
    if quote and not _verify_verbatim(quote, passages):
        # Don't fail loudly; mark the card so the UI can show a fallback badge
        card["_verbatim_verified"] = False
    else:
        card["_verbatim_verified"] = True

    return card


def _verify_verbatim(quote: str, passages: List[Dict]) -> bool:
    """Check that the quote actually appears verbatim in at least one passage."""
    # Normalize whitespace for comparison
    import re

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    quote_n = norm(quote)
    for p in passages:
        if quote_n in norm(p["text"]):
            return True
    return False
