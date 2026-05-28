"""
Claude Sonnet 4.7 call: takes retrieved passages + user mood,
returns a structured 막간 card.

Output schema (JSON):
{
  "quote_original": "...",        # verbatim, exactly as in source
  "quote_translated": "...",      # Korean translation if source was English; null if source is Korean
  "language_original": "en"|"ko",
  "title": "...",
  "author": "...",
  "speaker": "...",              # character speaking (for plays) or null
  "act_scene": "...",            # e.g. "2막 2장" or "Chapter 5" or null
  "scene_context": "...",        # one-line Korean description of the moment
  "ai_commentary": "..."         # 2-3 sentence Korean commentary contextualized to mood
}
"""
import json
import os
from typing import List, Dict, Optional

from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"  # current Sonnet, fast + cheap + great with Korean
MAX_TOKENS = 1500

# Mood label → Korean nuance hint
MOOD_HINTS = {
    "지침": "지치고 소진된 상태, 위로와 공감이 필요한 마음",
    "결심": "무언가를 결정하고 행동에 옮기려는 마음",
    "이별": "헤어짐의 슬픔, 그리움, 작별의 감정",
    "나다움": "자기 정체성, 본연의 모습에 대한 탐구",
    "망설임": "결정하지 못하고 흔들리는 마음, 갈등",
}


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


def _build_prompt(mood: str, passages: List[Dict]) -> str:
    mood_hint = MOOD_HINTS.get(mood, mood)
    passages_str = _format_passages_for_prompt(passages)

    return f"""You are curating a literary card for a Korean app called 막간 (Makgan).
The user has selected the mood/theme: **{mood}** ({mood_hint}).

Below are {len(passages)} candidate passages retrieved from public-domain works.
Your job:

1. **Choose ONE passage** that best matches the user's mood. Pick the most thematically resonant one — not just keyword-overlapping.
2. **Extract a SHORT quote** (1-4 sentences max, ~30-150 characters) from that passage. This must be a VERBATIM substring of the original text — do not paraphrase, do not modify, do not translate the original.
3. **Identify the speaker** (for plays) or narrator/POV (for novels) if possible.
4. **Write a Korean translation** of the quote if the original is English. Make it literary and natural Korean, not literal word-for-word. If the original is already Korean, set `quote_translated` to null.
5. **Write a one-line Korean scene context** (장면 설명) describing the moment — where, when, who's involved. Example: "발코니에서 로미오와 밤의 작별을 나누며".
6. **Write 2-3 sentences of Korean AI commentary** (AI 해설) that:
   - Connects this passage to the user's mood ({mood})
   - Explains why this moment resonates emotionally
   - Does NOT just summarize — it interprets and contextualizes
   - Sounds like a thoughtful curator, not a literature professor

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


def generate_card(mood: str, passages: List[Dict], api_key: Optional[str] = None) -> Dict:
    """
    Call Sonnet, parse the JSON response, return the card dict.
    Raises if the response is not valid JSON.
    """
    client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    prompt = _build_prompt(mood, passages)

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
