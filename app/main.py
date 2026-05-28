"""
막간 (Makgan) — premium demo build

Screen flow (state-driven, mobile-first vertical layout):
  1. splash   — calm welcome, single entry button
  2. main     — text box + chips + 🎲, card is the hero, typewriter reveal
  3. archive  — saved/favorited cards

Anonymous accounts: a stable user id is generated per session for the archive.
No login, no credentials — deferred to the real web-app build (Supabase Auth).
"""
import os
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from retrieval import retrieve, corpus_stats
from generation import generate_card, expand_query, MOOD_HINTS


st.set_page_config(
    page_title="막간 · Makgan",
    page_icon="🎭",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

    .stApp { background: linear-gradient(180deg, #FAF8F2 0%, #F4F1E8 100%); }
    #MainMenu, footer, header {visibility: hidden;}
    .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 480px; }

    .brand-row { display: flex; align-items: center; gap: 9px; margin-bottom: 2px; }
    .brand-mark { font-size: 20px; }
    .brand-name { font-family: 'Nanum Myeongjo', serif; font-size: 22px; font-weight: 800;
        color: #2A2438; letter-spacing: -0.01em; margin: 0; }

    .quote-card {
        background: #FFFFFF; border: 1px solid #ECE7DA; border-radius: 22px;
        padding: 30px 26px 26px 26px; margin: 18px 0 14px 0;
        box-shadow: 0 6px 24px rgba(42,36,56,0.06), 0 1px 2px rgba(42,36,56,0.04);
        animation: cardrise 0.55s cubic-bezier(0.22,1,0.36,1);
    }
    @keyframes cardrise { from {opacity:0; transform:translateY(14px);} to {opacity:1; transform:translateY(0);} }
    .verbatim-badge { display:inline-block; background:#F3F0E8; color:#8A8270;
        padding:6px 13px; border-radius:999px; font-family:'Noto Sans KR',sans-serif;
        font-size:11.5px; font-weight:500; letter-spacing:0.02em; margin-bottom:18px; }
    .verbatim-badge-warn { background:#FBEEE9; color:#B5623C; }
    .quote-text { font-family:'Nanum Myeongjo',serif; font-size:21px; line-height:1.62;
        color:#1F1A2B; font-weight:700; margin:0 0 16px 0; letter-spacing:-0.01em; word-break:keep-all; }
    .quote-original-en { font-family:'Georgia',serif; font-size:14px; color:#9A9387;
        font-style:italic; line-height:1.6; margin:0 0 14px 0; word-break:keep-all; }
    .quote-attribution { font-family:'Noto Sans KR',sans-serif; font-size:13px; color:#6B6456;
        line-height:1.5; margin-top:10px; word-break:keep-all; }

    .ai-commentary { background: linear-gradient(135deg, #EFEDFB 0%, #F1EFFC 100%);
        border-radius:16px; padding:18px 20px; margin:16px 0; }
    .ai-commentary-label { font-family:'Noto Sans KR',sans-serif; font-size:11.5px;
        color:#5B4D9E; font-weight:700; margin-bottom:9px; letter-spacing:0.02em; }
    .ai-commentary-text { font-family:'Noto Sans KR',sans-serif; font-size:14px;
        color:#2A2438; line-height:1.62; margin:0; word-break:keep-all; }
    .tw-cursor { display:inline-block; width:2px; height:1em; background:#5B4D9E;
        margin-left:1px; animation: blink 0.9s steps(1) infinite; vertical-align:-2px; }
    @keyframes blink { 50% { opacity:0; } }
    /* fade-in for 해설 + scene after the quote finishes typing */
    .ai-fade { animation: aifade 0.6s ease both; }
    @keyframes aifade { from {opacity:0; transform:translateY(6px);} to {opacity:1; transform:translateY(0);} }

    .scene-context { font-family:'Noto Sans KR',sans-serif; font-size:12.5px;
        color:#9A9387; margin:14px 0 4px 0; word-break:keep-all; }

    .stTextInput > div > div > input { background:#FFFFFF; border:1px solid #E4DFD2;
        border-radius:16px; padding:14px 18px; font-family:'Noto Sans KR',sans-serif;
        font-size:15px; color:#1F1A2B; }
    .stTextInput > div > div > input:focus { border-color:#5B4D9E;
        box-shadow:0 0 0 3px rgba(91,77,158,0.08); }
    .stTextInput > div > div > input::placeholder { color:#B3ADA0; }

    .stButton > button { background:#FFFFFF; border:1px solid #E4DFD2; color:#6B6456;
        border-radius:999px; padding:8px 4px; font-family:'Noto Sans KR',sans-serif;
        font-size:13px; font-weight:500; white-space:nowrap; transition:all 0.15s ease;
        min-height:38px; }
    .stButton > button:hover { border-color:#5B4D9E; color:#5B4D9E; background:#FFFFFF;
        transform:translateY(-1px); }
    .stButton > button:focus:not(:active) { border-color:#5B4D9E; color:#5B4D9E; }
    .stButton > button[kind="primary"] { background:#2A2438; color:#FFFFFF;
        border-color:#2A2438; font-weight:600; padding:13px 4px; min-height:48px; font-size:15px; }
    .stButton > button[kind="primary"]:hover { background:#3A3150; border-color:#3A3150; color:#FFFFFF; }

    .splash-wrap { text-align:center; padding:80px 24px 40px 24px; animation: fadein 0.9s ease; }
    @keyframes fadein { from {opacity:0;} to {opacity:1;} }
    .splash-mark { font-size:56px; margin-bottom:18px; opacity:0.92; }
    .splash-title { font-family:'Nanum Myeongjo',serif; font-size:38px; font-weight:800;
        color:#2A2438; margin:0 0 14px 0; letter-spacing:0.04em; }
    .splash-sub { font-family:'Noto Sans KR',sans-serif; font-size:15px; color:#8A8270;
        font-weight:300; line-height:1.7; margin:0 0 8px 0; }
    .splash-divider { width:36px; height:2px; background:#D8D2C4; margin:28px auto; border:none; }

    .sec-heading { font-family:'Nanum Myeongjo',serif; font-size:18px; font-weight:700;
        color:#2A2438; margin:6px 0 14px 0; }
    .archive-empty { text-align:center; padding:50px 20px; color:#B3ADA0;
        font-family:'Noto Sans KR',sans-serif; font-size:13.5px; }

    /* ---- Compact mood pills (small, wrap nicely on mobile) ---- */
    div[data-testid="stPills"] button {
        font-family:'Noto Sans KR',sans-serif !important;
        font-size:12.5px !important; padding:5px 12px !important;
        min-height:32px !important; border-radius:999px !important;
        white-space:nowrap !important;
    }
    div[data-testid="stPills"] { gap:6px !important; }

    /* ---- Send button (➤) — filled accent, square, aligns with input ---- */
    div.st-key-send_text button {
        background:#2A2438 !important; color:#FFFFFF !important;
        border:1px solid #2A2438 !important; border-radius:14px !important;
        min-height:48px !important; font-size:17px !important; padding:0 !important;
    }
    div.st-key-send_text button:hover {
        background:#3A3150 !important; border-color:#3A3150 !important; color:#FFFFFF !important;
        transform:none !important;
    }

    /* ---- Breathing orb loader (centered, calm) ---- */
    .orb-wrap { display:flex; flex-direction:column; align-items:center;
        justify-content:center; padding:70px 20px 60px 20px; }
    .orb { width:54px; height:54px; border-radius:50%;
        background: radial-gradient(circle at 35% 35%, #C8BEEC, #5B4D9E);
        box-shadow: 0 0 0 0 rgba(91,77,158,0.35);
        animation: breathe 2.6s ease-in-out infinite; }
    @keyframes breathe {
        0%   { transform: scale(0.82); opacity:0.7; box-shadow:0 0 0 0 rgba(91,77,158,0.30); }
        50%  { transform: scale(1.0);  opacity:1.0; box-shadow:0 0 26px 10px rgba(91,77,158,0.06); }
        100% { transform: scale(0.82); opacity:0.7; box-shadow:0 0 0 0 rgba(91,77,158,0.30); }
    }
    .orb-label { margin-top:22px; font-family:'Noto Sans KR',sans-serif; font-size:13px;
        color:#9A9387; font-weight:300; letter-spacing:0.03em;
        animation: labelpulse 2.6s ease-in-out infinite; }
    @keyframes labelpulse { 0%,100%{opacity:0.5;} 50%{opacity:0.9;} }
</style>
""", unsafe_allow_html=True)


def show_loading_orb(label="마음을 읽고 있어요"):
    """Centered breathing orb — replaces the ugly inline spinner."""
    st.markdown(f"""
    <div class="orb-wrap">
        <div class="orb"></div>
        <div class="orb-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def init_state():
    defaults = {
        "screen": "splash", "card": None, "current_expression": None,
        "current_query": None, "saved_cards": [], "last_passage_ids": set(),
        "animate_next": False, "show_share": False, "pending": None,
        "reroll_count": 0, "show_paywall": False, "pills_nonce": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if "anon_id" not in st.session_state:
        st.session_state.anon_id = "anon-" + uuid.uuid4().hex[:12]

init_state()

# Demo paywall: after this many 다른 대사 rerolls, nudge to subscribe.
REROLL_LIMIT = 3
SUBSCRIBE_PRICE = "5,900"


def _get_api_key() -> str:
    if "ANTHROPIC_API_KEY" in st.secrets:
        return st.secrets["ANTHROPIC_API_KEY"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    return ""


def generate_new_card(expression: str, is_free_text: bool = False, surprise: bool = False) -> dict:
    api_key = _get_api_key()
    if not api_key:
        st.error("API 키가 설정되지 않았어요. `.streamlit/secrets.toml`을 확인해주세요.")
        st.stop()
    if surprise:
        import random
        seeds = [
            "사랑과 상실, 운명, 인간의 욕망",
            "고독, 자유, 삶의 의미를 향한 갈망",
            "결단의 순간, 돌이킬 수 없는 선택",
            "그리움, 후회, 시간의 흐름",
            "정체성, 변화, 자신을 마주하는 순간",
        ]
        search_query = random.choice(seeds)
        card_expression = "지금 어떤 마음인지 모르지만, 마음을 흔드는 한 장면을 만나고 싶은 상태"
    elif is_free_text:
        search_query = expand_query(expression, api_key=api_key)
        card_expression = expression
    else:
        hint = MOOD_HINTS.get(expression, "")
        search_query = f"{expression} {hint}"
        card_expression = f"{expression} — {hint}" if hint else expression

    st.session_state.current_expression = card_expression
    st.session_state.current_query = search_query
    st.session_state.show_share = False

    candidates = retrieve(search_query, k=5)
    if not candidates:
        st.warning("더 이상 보여줄 작품이 없어요. 다른 마음을 적어보세요.")
        return None
    card = generate_card(card_expression, candidates[:5], api_key=api_key)
    # Mark only the passages we actually showed Sonnet as "seen"
    st.session_state.last_passage_ids = {c["id"] for c in candidates[:5]}
    return card


def _reroll_card() -> dict:
    api_key = _get_api_key()
    query = st.session_state.current_query
    expression = st.session_state.current_expression
    if not query:
        return None

    # Pull a wide candidate pool so we keep finding fresh passages across rerolls
    candidates = retrieve(query, k=40)
    fresh = [c for c in candidates if c["id"] not in st.session_state.last_passage_ids]

    if not fresh:
        # Exhausted unseen passages for this query — instead of dead-ending,
        # reset the exclusion set and start cycling through again.
        st.session_state.last_passage_ids = set()
        fresh = candidates
        if not fresh:
            st.warning("이 마음에 더 보여줄 장면이 없어요. 다른 마음을 적어보세요.")
            return None

    card = generate_card(expression, fresh[:5], api_key=api_key)
    # Only add the ones we actually showed Sonnet, so the pool drains gradually
    st.session_state.last_passage_ids |= {c["id"] for c in fresh[:5]}
    st.session_state.show_share = False
    return card


def go(screen: str):
    st.session_state.screen = screen


def screen_splash():
    st.markdown("""
    <div class="splash-wrap">
        <div class="splash-mark">🎭</div>
        <h1 class="splash-title">막간</h1>
        <p class="splash-sub">막과 막 사이, 잠시 숨을 고르는 시간.</p>
        <p class="splash-sub">지금 마음에 어울리는 한 문장을<br/>문학 속에서 찾아 건넵니다.</p>
        <hr class="splash-divider"/>
    </div>
    """, unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if st.button("시작하기", key="enter", type="primary", use_container_width=True):
            go("main"); st.rerun()


def render_card(card: dict, animate: bool = False):
    """
    Render the card. When animate=True, the entire reveal choreography runs
    in the browser (one HTML component): card fades in → quote types at
    ~0.09s/char → 해설 box + scene fade in. Smooth because it's CSS/JS, not
    Python time.sleep.
    """
    import html as _html
    import json as _json

    verbatim_ok = card.get("_verbatim_verified", True)
    badge_text = "💬 원문 그대로 · 변형 없음" if verbatim_ok else "💬 인용 검증 보류"
    badge_bg = "#F3F0E8" if verbatim_ok else "#FBEEE9"
    badge_fg = "#8A8270" if verbatim_ok else "#B5623C"

    is_english = (card.get("language_original") == "en")
    attribution = f'— {card["author"]}, 『{card["title"]}』'
    if card.get("speaker"):
        attribution += f' · {card["speaker"]}'
    if card.get("act_scene"):
        attribution += f' ({card["act_scene"]})'

    commentary = card.get("ai_commentary", "")
    scene = card.get("scene_context", "")

    if is_english and card.get("quote_translated"):
        hero_text = card["quote_translated"]
        sub_en = card["quote_original"]
    else:
        hero_text = card["quote_original"]
        sub_en = ""

    # ---- Static (non-animated) render: plain markdown, no component overhead ----
    if not animate:
        sub_html = f'<p class="quote-original-en">"{_html.escape(sub_en)}"</p>' if sub_en else ""
        body = ""
        if commentary:
            body += (f'<div class="ai-commentary">'
                     f'<div class="ai-commentary-label">✨ AI 해설 · 지금 마음에 맞춰</div>'
                     f'<p class="ai-commentary-text">{_html.escape(commentary)}</p></div>')
        if scene:
            body += f'<div class="scene-context">📍 장면 · {_html.escape(scene)}</div>'
        st.markdown(f"""
        <div class="quote-card">
            <span class="verbatim-badge">{badge_text}</span>
            <p class="quote-text">{_html.escape(hero_text)}</p>
            {sub_html}
            <p class="quote-attribution">{_html.escape(attribution)}</p>
        </div>
        {body}
        """, unsafe_allow_html=True)
        return

    # ---- Animated render: one self-contained component, browser-driven ----
    j_hero = _json.dumps(hero_text, ensure_ascii=False)
    j_sub = _json.dumps(sub_en, ensure_ascii=False)
    j_attr = _json.dumps(attribution, ensure_ascii=False)
    j_comm = _json.dumps(commentary, ensure_ascii=False)
    j_scene = _json.dumps(scene, ensure_ascii=False)

    comp = f"""
    <div id="mk-card" style="opacity:0; transition:opacity 1.0s ease;">
      <div style="background:#FFFFFF;border:1px solid #ECE7DA;border-radius:22px;
           padding:30px 26px 26px 26px;
           box-shadow:0 6px 24px rgba(42,36,56,0.06),0 1px 2px rgba(42,36,56,0.04);">
        <span style="display:inline-block;background:{badge_bg};color:{badge_fg};
           padding:6px 13px;border-radius:999px;font-family:'Noto Sans KR',sans-serif;
           font-size:11.5px;font-weight:500;margin-bottom:18px;">{badge_text}</span>
        <p id="mk-quote" style="font-family:'Nanum Myeongjo',serif;font-size:21px;
           line-height:1.62;color:#1F1A2B;font-weight:700;margin:0 0 16px 0;
           letter-spacing:-0.01em;word-break:keep-all;min-height:1.6em;"></p>
        <p id="mk-sub" style="font-family:'Georgia',serif;font-size:14px;color:#9A9387;
           font-style:italic;line-height:1.6;margin:0 0 14px 0;word-break:keep-all;
           opacity:0;transition:opacity 0.9s ease;"></p>
        <p id="mk-attr" style="font-family:'Noto Sans KR',sans-serif;font-size:13px;
           color:#6B6456;line-height:1.5;margin-top:10px;word-break:keep-all;
           opacity:0;transition:opacity 0.9s ease;"></p>
      </div>
      <div id="mk-comm" style="background:linear-gradient(135deg,#EFEDFB,#F1EFFC);
           border-radius:16px;padding:18px 20px;margin:16px 0;
           opacity:0;transform:translateY(8px);transition:opacity 1.0s ease, transform 1.0s ease;">
        <div style="font-family:'Noto Sans KR',sans-serif;font-size:11.5px;color:#5B4D9E;
             font-weight:700;margin-bottom:9px;">✨ AI 해설 · 지금 마음에 맞춰</div>
        <p id="mk-comm-text" style="font-family:'Noto Sans KR',sans-serif;font-size:14px;
           color:#2A2438;line-height:1.62;margin:0;word-break:keep-all;"></p>
      </div>
      <div id="mk-scene" style="font-family:'Noto Sans KR',sans-serif;font-size:12.5px;
           color:#9A9387;margin:14px 0 4px 0;word-break:keep-all;
           opacity:0;transition:opacity 1.0s ease;"></div>
    </div>

    <style>
      @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
      .mk-cursor {{ display:inline-block;width:2px;height:1em;background:#5B4D9E;
        margin-left:2px;vertical-align:-2px;animation:mkblink 1s steps(1) infinite; }}
      @keyframes mkblink {{ 50% {{ opacity:0; }} }}
    </style>

    <script>
      const HERO = {j_hero}, SUB = {j_sub}, ATTR = {j_attr}, COMM = {j_comm}, SCENE = {j_scene};
      const card = document.getElementById('mk-card');
      const qEl = document.getElementById('mk-quote');
      const subEl = document.getElementById('mk-sub');
      const attrEl = document.getElementById('mk-attr');
      const commEl = document.getElementById('mk-comm');
      const commText = document.getElementById('mk-comm-text');
      const sceneEl = document.getElementById('mk-scene');

      const TYPE_MS = 90;   // ~0.09s per char — slow & meditative
      const sleep = ms => new Promise(r => setTimeout(r, ms));

      async function run() {{
        await sleep(120);
        card.style.opacity = 1;          // soft fade-in of the card (1s)
        await sleep(1050);

        // type the hero quote
        qEl.innerHTML = '<span class="mk-cursor"></span>';
        for (let i = 0; i < HERO.length; i++) {{
          qEl.innerHTML = HERO.slice(0, i+1) + '<span class="mk-cursor"></span>';
          await sleep(TYPE_MS);
        }}
        qEl.innerHTML = HERO;            // remove cursor
        await sleep(350);

        // fade in subline (if any) + attribution
        if (SUB) {{ subEl.innerText = '“' + SUB + '”'; subEl.style.opacity = 1; }}
        attrEl.innerText = ATTR; attrEl.style.opacity = 1;
        await sleep(650);

        // fade in the 해설 box (content already inside)
        if (COMM) {{
          commText.innerText = COMM;
          commEl.style.opacity = 1;
          commEl.style.transform = 'translateY(0)';
        }}
        await sleep(500);

        // fade in scene line
        if (SCENE) {{ sceneEl.innerText = '📍 장면 · ' + SCENE; sceneEl.style.opacity = 1; }}
      }}
      run();
    </script>
    """
    # Height generous enough for long quotes + commentary
    est_height = 360 + min(len(hero_text), 300) * 1 + (140 if commentary else 0)
    components.html(comp, height=int(est_height))


def render_share_sheet(card: dict):
    """
    Share sheet: a downloadable card image (html2canvas) + SNS share buttons.
    Order: Kakao, X, Instagram(image), Threads, Facebook, Copy link.
    Rendered as a single HTML component so JS (canvas, share intents) can run.
    """
    import html as _html
    import json as _json

    quote = card.get("quote_translated") or card.get("quote_original", "")
    author = card.get("author", "")
    title = card.get("title", "")
    attribution = f"— {author}, 『{title}』"

    # App URL for share links (update if your deployed URL differs)
    app_url = "https://makgan.streamlit.app"
    share_text = f'"{quote}"  {attribution}  · 막간에서 만난 한 문장'

    # JSON-safe values for embedding in JS
    j_quote = _json.dumps(quote, ensure_ascii=False)
    j_attr = _json.dumps(attribution, ensure_ascii=False)
    j_text = _json.dumps(share_text, ensure_ascii=False)
    j_url = _json.dumps(app_url, ensure_ascii=False)

    components_html = f"""
    <div id="share-root" style="font-family:'Noto Sans KR',-apple-system,sans-serif;">
      <!-- The capture target: a self-contained styled card -->
      <div id="cap" style="background:linear-gradient(160deg,#FAF8F2,#F1EFFC);
           padding:30px 26px; border-radius:22px; width:340px; margin:0 auto 14px auto;
           box-shadow:0 6px 24px rgba(42,36,56,0.10);">
        <div style="font-family:'Nanum Myeongjo',serif;font-size:19px;font-weight:700;
             line-height:1.6;color:#1F1A2B;word-break:keep-all;margin-bottom:14px;">{_html.escape(quote)}</div>
        <div style="font-size:12.5px;color:#6B6456;">{_html.escape(attribution)}</div>
        <div style="margin-top:16px;font-family:'Nanum Myeongjo',serif;font-size:13px;
             color:#5B4D9E;font-weight:700;">🎭 막간</div>
      </div>

      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;width:340px;margin:0 auto;">
        <button onclick="dlImg()" style="grid-column:span 3;background:#2A2438;color:#fff;border:none;
          border-radius:12px;padding:12px;font-size:14px;font-weight:600;cursor:pointer;">
          🖼️ 카드 이미지 저장</button>

        <button onclick="shareKakao()" class="sns" style="background:#FEE500;color:#191600;">카카오</button>
        <button onclick="shareX()" class="sns" style="background:#000;color:#fff;">X</button>
        <button onclick="shareIG()" class="sns" style="background:#E1306C;color:#fff;">인스타</button>
        <button onclick="shareThreads()" class="sns" style="background:#000;color:#fff;">Threads</button>
        <button onclick="shareFB()" class="sns" style="background:#1877F2;color:#fff;">페북</button>
        <button onclick="copyLink()" class="sns" style="background:#fff;color:#2A2438;border:1px solid #E4DFD2;">링크 복사</button>
      </div>
      <div id="share-msg" style="text-align:center;font-size:11.5px;color:#8A8270;margin-top:10px;height:14px;"></div>
    </div>

    <style>
      .sns {{ border:none;border-radius:12px;padding:11px 4px;font-size:13px;
              font-weight:600;cursor:pointer;font-family:'Noto Sans KR',sans-serif; }}
      .sns:hover {{ opacity:0.88; }}
    </style>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script>
      const TEXT = {j_text};
      const URL_ = {j_url};
      const QUOTE = {j_quote};
      const ATTR = {j_attr};
      function msg(t) {{ document.getElementById('share-msg').innerText = t; }}

      function dlImg() {{
        const node = document.getElementById('cap');
        html2canvas(node, {{scale:2, backgroundColor:null}}).then(canvas => {{
          const link = document.createElement('a');
          link.download = 'makgan-card.png';
          link.href = canvas.toDataURL('image/png');
          link.click();
          msg('이미지를 저장했어요. 인스타·카톡에 올려보세요.');
        }});
      }}
      function shareKakao() {{
        // Basic share-link fallback (rich Kakao share needs Kakao JS SDK + app key)
        window.open('https://story.kakao.com/share?url=' + encodeURIComponent(URL_), '_blank');
        msg('카카오 공유 창을 열었어요.');
      }}
      function shareX() {{
        window.open('https://twitter.com/intent/tweet?text=' + encodeURIComponent(TEXT) +
          '&url=' + encodeURIComponent(URL_), '_blank');
      }}
      function shareIG() {{
        // Instagram has no web share API — guide the user to use the saved image
        dlImg();
        msg('인스타는 이미지로 공유해요. 저장된 카드를 스토리에 올려보세요.');
      }}
      function shareThreads() {{
        window.open('https://www.threads.net/intent/post?text=' +
          encodeURIComponent(TEXT + ' ' + URL_), '_blank');
      }}
      function shareFB() {{
        window.open('https://www.facebook.com/sharer/sharer.php?u=' +
          encodeURIComponent(URL_) + '&quote=' + encodeURIComponent(TEXT), '_blank');
      }}
      function copyLink() {{
        navigator.clipboard.writeText(TEXT + ' ' + URL_).then(() => msg('링크를 복사했어요.'));
      }}
    </script>
    """
    components.html(components_html, height=430)


def _set_pending(kind: str, value: str = ""):
    """Queue a generation request, then rerun so the orb shows during the wait."""
    st.session_state.pending = {"kind": kind, "value": value}
    # A fresh intent (text/mood/surprise) resets the reroll allowance
    if kind != "reroll":
        st.session_state.reroll_count = 0


@st.dialog("막간 프리미엄")
def paywall_dialog():
    """
    Demo paywall — appears after REROLL_LIMIT rerolls. This is a DEMO ONLY:
    the 구독하기 button does not process real payment. Real billing would be a
    separate integration (e.g. Stripe / 토스페이먼츠) in the production app.
    """
    st.markdown(f"""
    <div style="text-align:center; padding:6px 4px 2px 4px;
         font-family:'Noto Sans KR',sans-serif;">
        <div style="font-size:40px; margin-bottom:10px;">🎭</div>
        <div style="font-family:'Nanum Myeongjo',serif; font-size:21px; font-weight:800;
             color:#2A2438; margin-bottom:10px;">더 많은 장면을 만나보세요</div>
        <p style="font-size:14px; color:#6B6456; line-height:1.7; margin:0 0 6px 0;">
            오늘의 무료 발견을 모두 사용하셨어요.<br/>
            막간 프리미엄으로 마음에 닿는 장면을<br/>무제한으로 만나보세요.</p>
        <div style="margin:18px 0 6px 0;">
            <span style="font-family:'Nanum Myeongjo',serif; font-size:30px; font-weight:800;
                  color:#2A2438;">₩{SUBSCRIBE_PRICE}</span>
            <span style="font-size:14px; color:#9A9387;"> / 월</span>
        </div>
        <p style="font-size:11.5px; color:#B3ADA0; margin:4px 0 0 0;">
            언제든 해지할 수 있어요</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("구독하기", key="subscribe", type="primary", use_container_width=True):
        st.session_state.show_paywall = False
        st.session_state.reroll_count = 0
        st.toast("데모 모드입니다 — 실제 결제는 진행되지 않아요", icon="🎭")
        st.rerun()
    if st.button("나중에 할게요", key="paywall_dismiss", use_container_width=True):
        st.session_state.show_paywall = False
        st.session_state.reroll_count = 0   # reset so they can keep exploring
        st.rerun()


def screen_main():
    top_l, top_r = st.columns([4, 1])
    with top_l:
        st.markdown("""<div class="brand-row"><span class="brand-mark">🎭</span>
        <h1 class="brand-name">막간</h1></div>""", unsafe_allow_html=True)
    with top_r:
        if st.button("아카이브", key="to_archive", use_container_width=True):
            go("archive"); st.rerun()

    # Demo paywall overlay (after REROLL_LIMIT rerolls)
    if st.session_state.get("show_paywall", False):
        paywall_dialog()

    # Mobile-first input bar: text field + send button side by side.
    # (No reliance on Enter-to-send — the button is the trigger.)
    in_col, send_col = st.columns([5, 1])
    with in_col:
        st.text_input(label="지금 마음", key="makgan_text_input",
            placeholder="지금 마음, 그대로 적어보세요",
            label_visibility="collapsed")
    with send_col:
        if st.button("➤", key="send_text", use_container_width=True, help="보내기"):
            txt = st.session_state.get("makgan_text_input", "").strip()
            if txt:
                _set_pending("text", txt); st.rerun()

    # Mood chips as a compact pills row (wraps & stays small on mobile),
    # plus a small 🎲 surprise button. Emoji is shown; Korean meaning is the value.
    MOOD_LABELS = {
        "😮‍💨 지침": "지침",
        "🔥 결심": "결심",
        "💔 이별": "이별",
        "🪞 나다움": "나다움",
        "🌫️ 망설임": "망설임",
    }
    pill_col, dice_col = st.columns([5, 1])
    with pill_col:
        picked = st.pills(
            "지금 마음", options=list(MOOD_LABELS.keys()),
            selection_mode="single", default=None,
            label_visibility="collapsed", key=f"mood_pills_{st.session_state.get('pills_nonce', 0)}",
        )
        if picked:
            mood = MOOD_LABELS[picked]
            # bump the nonce so the pills widget remounts fresh (deselected) next run
            st.session_state.pills_nonce = st.session_state.get("pills_nonce", 0) + 1
            _set_pending("mood", mood); st.rerun()
    with dice_col:
        if st.button("🎲", key="surprise", use_container_width=True, help="무작위 한 장면"):
            _set_pending("surprise"); st.rerun()

    # If a request is pending, show the orb HERE (card area), generate, then rerun.
    pending = st.session_state.get("pending")
    if pending:
        labels = {
            "text": "마음을 읽고, 어울리는 장면을 찾고 있어요",
            "mood": "마음에 닿는 한 장면을 찾고 있어요",
            "surprise": "마음 가는 대로 한 장면을 고르고 있어요",
            "reroll": "다른 한 장면을 찾고 있어요",
        }
        show_loading_orb(labels.get(pending["kind"], "찾고 있어요"))
        try:
            if pending["kind"] == "text":
                card = generate_new_card(pending["value"], is_free_text=True)
            elif pending["kind"] == "mood":
                card = generate_new_card(pending["value"], is_free_text=False)
            elif pending["kind"] == "surprise":
                card = generate_new_card("", surprise=True)
            elif pending["kind"] == "reroll":
                card = _reroll_card()
            else:
                card = None
            if card:
                st.session_state.card = card
                st.session_state.animate_next = True
        except Exception as e:
            st.session_state.pending = None
            st.error(f"생성 중 오류: {e}")
            return
        st.session_state.pending = None
        st.rerun()

    # Otherwise, show the current card (or empty state)
    card = st.session_state.card
    if card:
        animate = st.session_state.animate_next
        st.session_state.animate_next = False
        render_card(card, animate=animate)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🔄 다른 대사", key="reroll", use_container_width=True):
                st.session_state.reroll_count += 1
                if st.session_state.reroll_count > REROLL_LIMIT:
                    # Demo paywall: nudge to subscribe after a few rerolls
                    st.session_state.show_paywall = True
                    st.rerun()
                else:
                    _set_pending("reroll"); st.rerun()
        with c2:
            saved = any(c.get("quote_original") == card.get("quote_original")
                        for c in st.session_state.saved_cards)
            if st.button("✓ 저장됨" if saved else "🔖 저장", key="save",
                         use_container_width=True, disabled=saved):
                st.session_state.saved_cards.append(card)
                st.toast("아카이브에 저장했어요", icon="🔖")
                st.rerun()
        with c3:
            if st.button("📤 공유", key="share", use_container_width=True):
                st.session_state.show_share = not st.session_state.get("show_share", False)
                st.rerun()

        if st.session_state.get("show_share", False):
            render_share_sheet(card)
    else:
        st.markdown("""
        <div style="text-align:center; padding:54px 20px;">
            <div style="font-size:38px; opacity:0.18; margin-bottom:14px;">🎭</div>
            <div style="font-family:'Noto Sans KR',sans-serif; font-size:13.5px;
                        color:#B3ADA0; line-height:1.7;">
                지금 마음을 한 줄로 적어보세요.<br/>
                또는 아래에서 골라보거나, 🎲 로 우연히 만나보세요.
            </div>
        </div>
        """, unsafe_allow_html=True)


def screen_archive():
    top_l, top_r = st.columns([4, 1])
    with top_l:
        st.markdown('<div class="sec-heading">🔖 내 아카이브</div>', unsafe_allow_html=True)
    with top_r:
        if st.button("돌아가기", key="back_main", use_container_width=True):
            go("main"); st.rerun()
    saved = st.session_state.saved_cards
    if not saved:
        st.markdown("""<div class="archive-empty">
            아직 저장한 카드가 없어요.<br/>마음에 드는 한 문장을 저장해보세요.</div>""",
            unsafe_allow_html=True)
        return
    st.markdown(f"""<div style="font-family:'Noto Sans KR',sans-serif;
        font-size:12.5px; color:#9A9387; margin-bottom:8px;">
        저장한 카드 {len(saved)}개</div>""", unsafe_allow_html=True)
    for c in reversed(saved):
        q = c.get("quote_translated") or c.get("quote_original", "")
        attr = f'{c.get("author","")} · 『{c.get("title","")}』'
        st.markdown(f"""
        <div class="quote-card" style="padding:20px 22px; margin:10px 0;">
            <p class="quote-text" style="font-size:16px; margin-bottom:10px;">{q}</p>
            <p class="quote-attribution">— {attr}</p>
        </div>
        """, unsafe_allow_html=True)


screen = st.session_state.screen
if screen == "splash":
    screen_splash()
elif screen == "archive":
    screen_archive()
else:
    screen_main()

if screen != "splash":
    try:
        n = corpus_stats().get("total_passages", 0)
    except Exception:
        n = 0
    st.markdown(f"""
    <div style="text-align:center; margin-top:30px;
        font-family:'Noto Sans KR',sans-serif; font-size:10.5px; color:#C4BDAE; line-height:1.6;">
        공개 도메인 문학 · Project Gutenberg · {n:,}개 구절<br/>
        Powered by Claude Sonnet · 막간 v0.2 demo
    </div>
    """, unsafe_allow_html=True)
