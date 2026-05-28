"""
막간 (Makgan) — Streamlit MVP

Layout matches the design mock:
- Header: 막간 logo + 지금 마음에 가까운 것을 골라보세요
- Mood chips: 지침 · 결심 · 이별 · 나다움 · 망설임
- Card:
    - Provenance badge (원문 그대로 · 변형 없음)
    - Verbatim quote (serif, prominent) + Korean translation if needed
    - Attribution
    - AI commentary (lavender callout)
    - Scene context
- Actions: 다른 대사 · 저장 · 공유
"""
import os
from pathlib import Path

import streamlit as st

# Module path — allow running both as streamlit module and from project root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from retrieval import retrieve, corpus_stats
from generation import generate_card, MOOD_HINTS


# ============================================================================
# PAGE CONFIG + CSS
# ============================================================================

st.set_page_config(
    page_title="막간 · Makgan",
    page_icon="🎭",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom CSS — matches the cream/lavender 막간 mock
st.markdown("""
<style>
    /* App background */
    .stApp {
        background-color: #FAF8F2;
    }

    /* Hide Streamlit chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Title */
    .makgan-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;
    }
    .makgan-logo {
        font-size: 18px;
    }
    .makgan-title {
        font-size: 24px;
        font-weight: 700;
        color: #1A1A1A;
        margin: 0;
    }
    .makgan-subtitle {
        font-size: 14px;
        color: #6B6B6B;
        margin: 0 0 16px 0;
    }

    /* Card */
    .quote-card {
        background: white;
        border: 1px solid #E8E4D9;
        border-radius: 18px;
        padding: 24px 22px;
        margin: 20px 0 14px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .verbatim-badge {
        display: inline-block;
        background: #F1EFE8;
        color: #6B6B6B;
        padding: 5px 12px;
        border-radius: 12px;
        font-size: 12px;
        margin-bottom: 14px;
    }
    .verbatim-badge-warn {
        background: #FFF5F3;
        color: #C24820;
    }
    .quote-text {
        font-size: 20px;
        line-height: 1.55;
        color: #1A1A1A;
        font-weight: 500;
        margin: 0 0 14px 0;
        font-family: 'Nanum Myeongjo', 'Apple SD Gothic Neo', serif;
    }
    .quote-original-en {
        font-size: 15px;
        color: #6B6B6B;
        font-style: italic;
        margin: 0 0 12px 0;
        line-height: 1.5;
        font-family: 'Georgia', serif;
    }
    .quote-attribution {
        font-size: 13px;
        color: #6B6B6B;
        margin-top: 8px;
    }

    /* AI commentary box */
    .ai-commentary {
        background: #EEEDFE;
        border-radius: 14px;
        padding: 16px 18px;
        margin: 14px 0;
    }
    .ai-commentary-label {
        font-size: 12px;
        color: #3D2D7C;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .ai-commentary-text {
        font-size: 14px;
        color: #1A1A1A;
        line-height: 1.55;
        margin: 0;
    }

    /* Scene context line */
    .scene-context {
        font-size: 13px;
        color: #6B6B6B;
        margin: 12px 0 16px 0;
    }

    /* Streamlit button overrides (mood chips + actions) */
    .stButton > button {
        background: white;
        border: 1px solid #D6D6D6;
        color: #1A1A1A;
        border-radius: 999px;
        padding: 6px 18px;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        border-color: #3D2D7C;
        color: #3D2D7C;
        background: white;
    }
    .stButton > button:focus:not(:active) {
        border-color: #3D2D7C;
        color: #3D2D7C;
        background: white;
    }
    /* Primary (selected mood) */
    .stButton > button[kind="primary"] {
        background: #3D2D7C;
        color: white;
        border-color: #3D2D7C;
    }

    /* Compact spacing */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 560px;
    }

    /* Loading spinner */
    .stSpinner > div {
        border-top-color: #3D2D7C !important;
    }

    /* Footer */
    .footer-note {
        font-size: 11px;
        color: #999999;
        text-align: center;
        margin-top: 28px;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# STATE
# ============================================================================

if "card" not in st.session_state:
    st.session_state.card = None
if "current_mood" not in st.session_state:
    st.session_state.current_mood = None
if "saved_cards" not in st.session_state:
    st.session_state.saved_cards = []
if "last_passage_ids" not in st.session_state:
    st.session_state.last_passage_ids = set()


# ============================================================================
# CARD GENERATION
# ============================================================================

def _get_api_key() -> str:
    """Get API key from Streamlit secrets, env var, or session state."""
    # Streamlit Cloud secrets
    if "ANTHROPIC_API_KEY" in st.secrets:
        return st.secrets["ANTHROPIC_API_KEY"]
    # Env var (local dev)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    return ""


def generate_new_card(mood: str, exclude_ids: set = None) -> dict:
    """Retrieve + generate for a given mood. Excludes already-shown passage IDs for reroll."""
    api_key = _get_api_key()
    if not api_key:
        st.error("Anthropic API key not configured. Add it to `.streamlit/secrets.toml` or set `ANTHROPIC_API_KEY`.")
        st.stop()

    # Build a thematic query from the mood
    mood_query = f"{mood} {MOOD_HINTS.get(mood, '')}"

    # Retrieve more candidates if we're rerolling
    k = 8 if exclude_ids else 5
    candidates = retrieve(mood_query, k=k)

    # Filter out already-shown passages
    if exclude_ids:
        candidates = [c for c in candidates if c["id"] not in exclude_ids]

    if not candidates:
        st.warning("이 무드에 더 이상 보여줄 작품이 없어요. 다른 무드를 골라보세요.")
        return None

    # Generate the card via Sonnet
    card = generate_card(mood, candidates, api_key=api_key)

    # Track which passages we considered (for reroll exclusion)
    for c in candidates:
        st.session_state.last_passage_ids.add(c["id"])

    return card


# ============================================================================
# UI
# ============================================================================

# Header
col_logo, col_profile = st.columns([5, 1])
with col_logo:
    st.markdown('<div class="makgan-header"><span class="makgan-logo">🎭</span><h1 class="makgan-title">막간</h1></div>', unsafe_allow_html=True)
    st.markdown('<p class="makgan-subtitle">지금 마음에 가까운 것을 골라보세요</p>', unsafe_allow_html=True)

# Mood chips
MOODS = ["지침", "결심", "이별", "나다움", "망설임"]

cols = st.columns(len(MOODS))
for i, mood in enumerate(MOODS):
    with cols[i]:
        is_selected = (st.session_state.current_mood == mood)
        kind = "primary" if is_selected else "secondary"
        if st.button(mood, key=f"mood_{mood}", type=kind, use_container_width=True):
            st.session_state.current_mood = mood
            st.session_state.last_passage_ids = set()  # reset reroll history
            with st.spinner("작품을 찾고 있어요…"):
                try:
                    st.session_state.card = generate_new_card(mood)
                except Exception as e:
                    st.error(f"생성 중 오류: {e}")
                    st.session_state.card = None
            st.rerun()

# Card display
card = st.session_state.card
if card:
    verbatim_ok = card.get("_verbatim_verified", True)
    badge_class = "verbatim-badge" if verbatim_ok else "verbatim-badge verbatim-badge-warn"
    badge_text = "💬 원문 그대로 · 변형 없음" if verbatim_ok else "💬 인용 검증 보류"

    # Quote card
    is_english = (card.get("language_original") == "en")

    if is_english and card.get("quote_translated"):
        # Korean translation on top (large), English original below (smaller, italic)
        quote_html = f"""
        <div class="quote-card">
            <span class="{badge_class}">{badge_text}</span>
            <p class="quote-text">{card["quote_translated"]}</p>
            <p class="quote-original-en">"{card["quote_original"]}"</p>
            <p class="quote-attribution">— {card["author"]}, 『{card["title"]}』{
                " · " + card["speaker"] if card.get("speaker") else ""
            }{
                " (" + card["act_scene"] + ")" if card.get("act_scene") else ""
            }</p>
        </div>
        """
    else:
        # Korean original — show as-is
        quote_html = f"""
        <div class="quote-card">
            <span class="{badge_class}">{badge_text}</span>
            <p class="quote-text">{card["quote_original"]}</p>
            <p class="quote-attribution">— {card["author"]}, 『{card["title"]}』{
                " · " + card["speaker"] if card.get("speaker") else ""
            }{
                " (" + card["act_scene"] + ")" if card.get("act_scene") else ""
            }</p>
        </div>
        """
    st.markdown(quote_html, unsafe_allow_html=True)

    # AI commentary
    if card.get("ai_commentary"):
        st.markdown(f"""
        <div class="ai-commentary">
            <div class="ai-commentary-label">✨ AI 해설 · 고른 마음에 맞춰</div>
            <p class="ai-commentary-text">{card["ai_commentary"]}</p>
        </div>
        """, unsafe_allow_html=True)

    # Scene context
    if card.get("scene_context"):
        st.markdown(
            f'<div class="scene-context">📍 장면 · {card["scene_context"]}</div>',
            unsafe_allow_html=True,
        )

    # Action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 다른 대사", key="reroll", use_container_width=True):
            with st.spinner("다른 작품을 찾고 있어요…"):
                try:
                    new_card = generate_new_card(
                        st.session_state.current_mood,
                        exclude_ids=st.session_state.last_passage_ids,
                    )
                    if new_card:
                        st.session_state.card = new_card
                except Exception as e:
                    st.error(f"오류: {e}")
            st.rerun()
    with col2:
        already_saved = any(
            c.get("quote_original") == card.get("quote_original")
            for c in st.session_state.saved_cards
        )
        save_label = "✓ 저장됨" if already_saved else "🔖 저장"
        if st.button(save_label, key="save", use_container_width=True, disabled=already_saved):
            st.session_state.saved_cards.append(card)
            st.toast("아카이브에 저장했어요", icon="🔖")
            st.rerun()
    with col3:
        if st.button("📤 공유", key="share", use_container_width=True):
            # For MVP: show shareable text in a modal
            share_text = (
                f'"{card.get("quote_translated") or card.get("quote_original")}"\n'
                f'— {card["author"]}, 『{card["title"]}』\n\n'
                f'막간에서 만난 한 문장'
            )
            st.toast("복사용 텍스트를 아래에서 확인하세요", icon="📤")
            with st.expander("공유 텍스트 (길게 눌러 복사)", expanded=True):
                st.code(share_text, language=None)

else:
    # Empty state
    if st.session_state.current_mood is None:
        st.markdown("""
        <div style="text-align: center; padding: 60px 20px; color: #999;">
            <div style="font-size: 48px; opacity: 0.3; margin-bottom: 12px;">🎭</div>
            <div style="font-size: 14px;">마음을 골라주세요</div>
        </div>
        """, unsafe_allow_html=True)


# Sidebar — show saved cards
if st.session_state.saved_cards:
    with st.sidebar:
        st.markdown("### 🔖 내 아카이브")
        for i, saved in enumerate(reversed(st.session_state.saved_cards)):
            with st.container():
                q = saved.get("quote_translated") or saved.get("quote_original", "")
                st.markdown(f"**{q[:60]}{'…' if len(q) > 60 else ''}**")
                st.caption(f"{saved['author']} · 『{saved['title']}』")
                st.divider()


# Footer
try:
    stats = corpus_stats()
    passages_n = stats.get("total_passages", 0)
except Exception:
    passages_n = 0

st.markdown(f"""
<div class="footer-note">
    Public domain works · Project Gutenberg · {passages_n:,}개 구절 · Powered by Claude Sonnet 4.6
    <br>
    막간 · Makgan v0.1 demo
</div>
""", unsafe_allow_html=True)
