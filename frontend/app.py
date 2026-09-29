import html
import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st

# On Streamlit Community Cloud, keys and settings come from the app's Secrets. Load them first:
# root-level secrets become environment variables, which app.config reads at import time.
# Locally there is no secrets file and settings come from .env instead.
try:
    st.secrets.load_if_toml_exists()
except Exception:
    pass

from app.agent.pipeline import KisanPipeline
from app.agent.state import ConversationTurn
from app.config import settings
from app.agent.synthesizer import GeminiSynthesizer, OpenAISynthesizer
from app.i18n import DEFAULT_LANGUAGE, LANGUAGES, SAMPLE_QUESTIONS, t
from app.tools.weather_tool import AgWeatherTool, DISTRICT_COORDINATES

# Page Configuration
st.set_page_config(
    page_title="KisanSahayak - AI Krishi Sahayak",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Visual design: light "wheat field" theme (colors in .streamlit/config.toml) + Indic-script fonts
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&family=Noto+Sans+Gurmukhi:wght@400;600;700&display=swap');

    :root {
        --ks-green: #2F6B2F;
        --ks-deep: #1F4D2B;
        --ks-gold: #E0A526;
        --ks-line: #E4DCC8;
        --ks-text: #1E2B1E;
        --ks-muted: #5B6B5B;
    }
    html, body, [data-testid="stAppViewContainer"], .stMarkdown, .stMarkdown p, .stMarkdown li,
    label, input, textarea, button {
        font-family: 'Noto Sans', 'Noto Sans Devanagari', 'Noto Sans Gurmukhi', sans-serif;
    }
    .block-container { max-width: 1180px; padding-top: 3.2rem; padding-bottom: 2rem; }

    /* Hero banner */
    .ks-hero {
        position: relative; overflow: hidden;
        background: linear-gradient(135deg, #1F4D2B 0%, #2F6B2F 55%, #5E7F1F 100%);
        border-radius: 20px; padding: 28px 32px; margin-bottom: 1.2rem;
        box-shadow: 0 12px 32px rgba(31, 77, 43, 0.20);
    }
    .ks-hero::after {
        content: ""; position: absolute; right: -70px; top: -70px; width: 260px; height: 260px;
        border-radius: 50%; background: radial-gradient(circle, rgba(244, 210, 122, 0.40), transparent 70%);
    }
    .ks-hero h1 { color: #FFFFFF; font-size: 2.1rem; font-weight: 700; line-height: 1.25; margin: 0; padding: 0; }
    .ks-hero h1 .ks-hi { color: #F4D27A; }
    .ks-hero p { color: rgba(255, 255, 255, 0.90); font-size: 1.05rem; margin: 0.45rem 0 1rem; }
    .ks-badges { display: flex; flex-wrap: wrap; gap: 8px; position: relative; z-index: 1; }
    .ks-badge {
        background: rgba(255, 255, 255, 0.14); border: 1px solid rgba(255, 255, 255, 0.30);
        color: #FFFFFF; padding: 5px 13px; border-radius: 999px; font-size: 0.85rem;
    }

    /* Cards: bordered containers are keyed "card_*" (Streamlit adds a st-key-<key> class) */
    [class*="st-key-card_"] {
        background: #FFFFFF; border-radius: 18px !important; border: 1px solid var(--ks-line) !important;
        box-shadow: 0 2px 12px rgba(60, 50, 20, 0.05); padding: 1.1rem 1.2rem !important;
    }
    .ks-section-title { font-weight: 700; font-size: 1.02rem; color: var(--ks-deep); margin: 0 0 0.5rem; }

    /* Inputs and buttons */
    [data-testid="stTextInput"] input { font-size: 1.05rem; padding: 0.75rem 1rem; border-radius: 12px; }
    .stButton > button { border-radius: 999px; font-weight: 600; transition: all 0.15s ease; }
    [data-testid="stBaseButton-primary"] { background: var(--ks-green); border: none; box-shadow: 0 4px 12px rgba(47, 107, 47, 0.25); }
    [data-testid="stBaseButton-primary"]:hover { background: var(--ks-deep); }
    [data-testid="stBaseButton-secondary"] { background: #FFFFFF; border: 1px solid var(--ks-line); color: var(--ks-text); }
    [data-testid="stBaseButton-secondary"]:hover { border-color: var(--ks-green); color: var(--ks-green); }
    .st-key-card_samples .stButton > button { justify-content: flex-start; border-radius: 12px; padding: 0.55rem 0.9rem; }
    .st-key-card_samples .stButton > button > div { justify-content: flex-start; width: 100%; }
    .st-key-card_samples .stButton > button p { text-align: left; font-weight: 500; font-size: 0.9rem; }

    /* Answer */
    .ks-chip { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 0.85rem; font-weight: 600; margin: 0 6px 6px 0; }
    .ks-chip-crop { background: #EAF3E3; color: #1F4D2B; }
    .ks-chip-ok { background: #E1F3E6; color: #1B6B35; }
    .ks-chip-warn { background: #FFF1D0; color: #8A5A00; }
    .disclaimer-card {
        background: #FFF6E0; border-left: 4px solid var(--ks-gold); color: #4A3A10;
        padding: 0.75rem 1rem; border-radius: 10px; margin: 0.5rem 0; font-size: 0.9rem;
    }
    .citation-box {
        border-left: 3px solid var(--ks-green); background: #F5F9F1; color: var(--ks-text);
        padding: 0.55rem 0.9rem; border-radius: 8px; margin: 0.4rem 0; font-size: 0.86rem;
    }
    .chunk-card {
        background: #FAF8F2; border: 1px solid var(--ks-line); color: var(--ks-text);
        padding: 0.8rem; border-radius: 8px; margin-bottom: 0.5rem; font-size: 0.85rem;
    }
    /* Keep LLM-written headings modest inside the answer card */
    .st-key-card_answer [data-testid="stMarkdownContainer"] h1,
    .st-key-card_answer [data-testid="stMarkdownContainer"] h2,
    .st-key-card_answer [data-testid="stMarkdownContainer"] h3,
    .st-key-card_answer [data-testid="stMarkdownContainer"] h4 {
        font-size: 1.08rem !important; font-weight: 700; color: var(--ks-deep); padding: 0.9rem 0 0.2rem;
    }
    .st-key-card_answer hr { margin: 0.8rem 0; }
    /* Chat bubbles: farmer messages tinted green, assistant messages plain */
    [data-testid="stChatMessage"] { border-radius: 14px; padding: 0.8rem 1rem; margin-bottom: 0.4rem; }
    [data-testid="stChatInput"] textarea { font-size: 1.02rem; }
    .ks-answer-title { font-size: 1.35rem; font-weight: 700; color: var(--ks-deep); margin: 0.6rem 0 0.4rem; }
    .ks-empty { color: var(--ks-muted); text-align: center; padding: 26px 12px; font-size: 0.98rem; }

    /* Weather card */
    .ks-weather { background: linear-gradient(135deg, #E6F0FA, #F4F8FC); color: #16324F; border-radius: 14px; padding: 14px 16px; margin-top: 0.4rem; }
    .ks-weather-title { font-weight: 700; margin-bottom: 8px; }
    .ks-weather-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
    .ks-grid-4 { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); margin-bottom: 0; }
    .ks-stat { background: rgba(255, 255, 255, 0.75); border-radius: 10px; padding: 6px 10px; }
    .ks-stat-label { font-size: 0.75rem; color: #4A6480; }
    .ks-stat-value { font-size: 1.05rem; font-weight: 700; }
    .ks-weather-advice { font-size: 0.88rem; line-height: 1.45; }

    .ks-footer { text-align: center; color: var(--ks-muted); font-size: 0.8rem; margin-top: 1.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_pipeline():
    """Cache and initialize KisanPipeline."""
    return KisanPipeline()


@st.cache_resource
def get_weather_tool():
    """Cache AgWeatherTool."""
    return AgWeatherTool()


def _ask_sample(question: str) -> None:
    """Sample-question chip: send it as the next chat message in one tap."""
    st.session_state["pending_query"] = question


def _new_chat() -> None:
    st.session_state["messages"] = []
    st.session_state["audio"] = {}


def conversation_history():
    """Finished turns of this farmer's conversation, oldest first (for follow-up questions)."""
    skip = {"empty", "error", "voice_stt_unavailable"}
    return [
        ConversationTurn.from_answer(m["result"])
        for m in st.session_state["messages"]
        if m["role"] == "assistant" and m["result"].intent not in skip
    ]


def render_sidebar(pipeline, lang: str) -> None:
    """System status for judges and developers; collapsed by default so farmers aren't distracted."""
    with st.sidebar:
        st.markdown("### 🌾 KisanSahayak")
        st.markdown(f"#### {t('system_status_header', lang)}")
        status_text = "🟢 Active (Ready)" if pipeline.retriever.is_ready else "🔴 Initializing..."
        st.write(f"**Knowledge Index:** {status_text}")
        st.write(f"**Retriever:** FAISS + BM25 + RRF ($k={settings.RRF_K}$)")
        if isinstance(pipeline.synthesizer, GeminiSynthesizer):
            llm_text = f"`{settings.GEMINI_MODEL}` (Gemini)"
        elif isinstance(pipeline.synthesizer, OpenAISynthesizer):
            llm_text = f"`{settings.OPENAI_MODEL}` (OpenAI)"
        else:
            llm_text = "⚪ None (offline template)"
        st.write(f"**Primary LLM:** {llm_text}")
        stt = pipeline.stt_adapter
        engines = [f"`{settings.GROQ_WHISPER_MODEL}` (Groq)"] if stt._groq_available() else []
        engines += ["Gemini"] if stt._gemini_available() else []
        st.write(f"**STT Adapter:** {' + '.join(engines) if engines else '⚪ Off (no GROQ_API_KEY / GEMINI_API_KEY)'}")
        tts = pipeline.tts_adapter
        if tts.is_available():
            punjabi = "gTTS" if tts.engine_for("pa") == "gtts" else "text only"
            st.write(f"**TTS Voice:** Edge-TTS (`en-IN`, `hi-IN`) · Punjabi: {punjabi}")
        else:
            st.write("**TTS Voice:** ⚪ Off (edge-tts / gTTS not installed)")
        st.markdown("---")
        st.caption(t("sidebar_caption", lang))


def render_hero(lang: str) -> None:
    st.markdown(
        f"""
        <div class="ks-hero">
            <h1>🌾 KisanSahayak <span class="ks-hi">किसान सहायक</span></h1>
            <p>{t("subtitle", lang)}</p>
            <div class="ks-badges">
                <span class="ks-badge">✅ {t("badge_verified", lang)}</span>
                <span class="ks-badge">🗣️ {t("badge_languages", lang)}</span>
                <span class="ks-badge">🌦️ {t("badge_weather", lang)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_answer(result, pipeline, lang: str, msg_id: int, speak_now: bool = False) -> None:
    meta = result.processing_metadata

    # Problems (voice not understood, empty question, internal error) are plain messages:
    # no crop/verified chips, no Listen button; the technical reason is under Details
    if result.intent in ("voice_stt_unavailable", "empty", "error"):
        st.warning(result.answer)
        reason = meta.get("stt_error") or meta.get("error")
        if reason:
            with st.expander(t("details_header", lang), expanded=False):
                st.code(reason, language=None)
        return

    # Farmer-facing summary chips: what the answer is about and whether it's verified
    crop_label = meta.get("detected_crop") or meta.get("district") or t("general", lang)
    topic = meta.get("detected_topic")
    if topic and topic not in ("Agronomy/General", "Ag-Weather & Spray Window Advisory"):
        crop_label = f"{crop_label} · {topic}"
    if result.is_grounded:
        grounded_chip = f'<span class="ks-chip ks-chip-ok">{t("grounded_yes", lang)}</span>'
    else:
        grounded_chip = f'<span class="ks-chip ks-chip-warn">{t("grounded_partial", lang)}</span>'
    st.markdown(
        f'<span class="ks-chip ks-chip-crop">{html.escape(crop_label)}</span>{grounded_chip}',
        unsafe_allow_html=True,
    )

    # Weather metrics if weather result
    if result.weather_report:
        wr = result.weather_report
        stats = [
            (t("temperature", lang), f"{wr.get('temperature_c')}°C"),
            (t("wind_speed", lang), f"{wr.get('wind_speed_kmh')} km/h"),
            (t("rain_chance", lang), f"{wr.get('rain_probability_pct')}%"),
            (t("humidity", lang), f"{wr.get('relative_humidity')}%"),
        ]
        cells = "".join(
            f'<div class="ks-stat"><div class="ks-stat-label">{label}</div><div class="ks-stat-value">{value}</div></div>'
            for label, value in stats
        )
        st.markdown(f'<div class="ks-weather"><div class="ks-weather-grid ks-grid-4">{cells}</div></div>', unsafe_allow_html=True)

    answer_source = meta.get("answer_source")
    if answer_source == "template_llm_failed":
        st.warning(t("note_template_llm_failed", lang))
    elif answer_source == "template_offline":
        st.info(t("note_template_offline", lang))
    st.markdown(result.answer)

    # Spoken answer: made on demand (Listen) so the text appears without waiting for audio.
    # Answers to spoken questions are read aloud automatically, once, like a phone conversation.
    answer_lang = result.detected_language
    if pipeline.tts_adapter.supports(answer_lang):
        audio_path = st.session_state["audio"].get(msg_id)
        if audio_path and os.path.exists(audio_path):
            st.audio(audio_path, format="audio/mp3", autoplay=speak_now)
        elif speak_now or st.button(t("listen_header", lang), key=f"listen_{msg_id}"):
            with st.spinner(t("speaking", lang)):
                audio_path = pipeline.tts_adapter.synthesize_speech(result.answer, language=answer_lang)
            if audio_path:
                st.session_state["audio"][msg_id] = str(audio_path)
                st.audio(str(audio_path), format="audio/mp3", autoplay=True)
    else:
        st.caption(t("voice_unavailable", lang))

    if result.safety_disclaimers:
        st.markdown(f'<div class="ks-section-title" style="margin-top:1rem">{t("safety_header", lang)}</div>', unsafe_allow_html=True)
        for disc in result.safety_disclaimers:
            st.markdown(f'<div class="disclaimer-card">{disc}</div>', unsafe_allow_html=True)

    if result.citations:
        st.markdown(f'<div class="ks-section-title" style="margin-top:1rem">{t("sources_header", lang)}</div>', unsafe_allow_html=True)
        for cit in result.citations:
            st.markdown(f'<div class="citation-box">{html.escape(cit)}</div>', unsafe_allow_html=True)

    if result.retrieved_chunks:
        with st.expander(t("evidence_header", lang), expanded=False):
            for idx, c in enumerate(result.retrieved_chunks):
                st.markdown(f"**#{idx + 1} · `{c.citation}` · RRF {c.score:.4f}**")
                st.markdown(
                    f'<div class="chunk-card"><pre style="white-space: pre-wrap; font-family: inherit; margin: 0;">'
                    f"{html.escape(c.text)}</pre></div>",
                    unsafe_allow_html=True,
                )

    # Technical details for demos and debugging, kept out of the farmer's way
    with st.expander(t("details_header", lang), expanded=False):
        st.write(f"**{t('metric_intent', lang)}:** `{result.intent}`")
        st.write(f"**{t('metric_latency', lang)}:** {meta.get('latency_ms', 0)} ms")
        if answer_source:
            st.write(f"**Answer source:** `{answer_source}`")
        if meta.get("grounding_score") is not None:
            st.write(f"**{t('metric_grounding', lang)}:** {meta['grounding_score']}")
        if meta.get("router_reasoning"):
            st.write(f"**Router:** {meta['router_reasoning']}")
        st.write(f"**Language:** `{result.detected_language}`")


def render_weather_card(weather_tool, lang: str) -> None:
    st.markdown(f'<div class="ks-section-title">{t("sidebar_weather_header", lang)}</div>', unsafe_allow_html=True)
    districts = [d.capitalize() for d in sorted(DISTRICT_COORDINATES.keys())]
    district = st.selectbox(
        t("select_district", lang), districts, index=districts.index("Ludhiana"), key="weather_district"
    )
    if st.button(t("check_weather", lang), use_container_width=True):
        with st.spinner("🌦️ ..."):
            st.session_state["weather"] = (lang, weather_tool.get_weather_for_district(district, language=lang))

    saved = st.session_state.get("weather")
    if saved and saved[0] == lang:
        report = saved[1]
        st.markdown(
            f"""
            <div class="ks-weather">
                <div class="ks-weather-title">{t("weather_card_title", lang, district=report.district)}</div>
                <div class="ks-weather-grid">
                    <div class="ks-stat"><div class="ks-stat-label">{t("temperature", lang)}</div><div class="ks-stat-value">{report.temperature_c}°C</div></div>
                    <div class="ks-stat"><div class="ks-stat-label">{t("wind_speed", lang)}</div><div class="ks-stat-value">{report.wind_speed_kmh} km/h</div></div>
                    <div class="ks-stat"><div class="ks-stat-label">{t("rain_chance", lang)}</div><div class="ks-stat-value">{report.rain_probability_pct}%</div></div>
                    <div class="ks-stat"><div class="ks-stat-label">{t("humidity", lang)}</div><div class="ks-stat-value">{report.relative_humidity}%</div></div>
                </div>
                <div class="ks-weather-advice">{report.spray_recommendation}<br>{report.irrigation_advisory}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main():
    pipeline = get_pipeline()
    weather_tool = get_weather_tool()

    # Farmer's chosen language drives the UI text, the answer language and the voice
    if "ui_language" not in st.session_state:
        st.session_state["ui_language"] = DEFAULT_LANGUAGE
    lang = st.session_state["ui_language"]
    # This farmer's conversation (private to their browser session)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("audio", {})

    render_sidebar(pipeline, lang)

    # Language switch, top right
    _, lang_col = st.columns([5, 2])
    with lang_col:
        st.selectbox(
            t("language_label", lang),
            options=list(LANGUAGES.keys()),
            format_func=LANGUAGES.get,
            key="ui_language",
        )

    render_hero(lang)

    main_col, side_col = st.columns([2, 1], gap="large")

    with side_col:
        with st.container(border=True, key="card_samples"):
            st.markdown(f'<div class="ks-section-title">{t("samples_header", lang)}</div>', unsafe_allow_html=True)
            for i, q in enumerate(SAMPLE_QUESTIONS[lang]):
                st.button(q, key=f"sample_{lang}_{i}", on_click=_ask_sample, args=(q,), use_container_width=True)

        with st.container(border=True, key="card_weather"):
            render_weather_card(weather_tool, lang)

    with main_col:
        chat = st.container(border=True, key="card_answer")
        with chat:
            head_col, new_col = st.columns([3, 2], vertical_alignment="center")
            with head_col:
                st.markdown(f'<div class="ks-answer-title">{t("chat_header", lang)}</div>', unsafe_allow_html=True)
            with new_col:
                st.button(t("new_chat", lang), on_click=_new_chat, use_container_width=True)

            if not st.session_state["messages"]:
                with st.chat_message("assistant", avatar="🌾"):
                    st.markdown(t("chat_welcome", lang))
            for msg in st.session_state["messages"]:
                if msg["role"] == "user":
                    with st.chat_message("user", avatar="🧑‍🌾"):
                        st.markdown(msg["text"])
                else:
                    with st.chat_message("assistant", avatar="🌾"):
                        render_answer(msg["result"], pipeline, lang, msg["id"], speak_now=msg.get("speak", False))
                    msg["speak"] = False  # read aloud only the first time it is shown

        prompt = st.chat_input(t("input_placeholder", lang), key="chat_box")

        # Speak in real time: record in the browser, and the question is sent as soon as recording stops.
        # A new key after each question resets the recorder for the next one.
        st.session_state.setdefault("mic_round", 0)
        recording = st.audio_input(t("record_label", lang), key=f"mic_{st.session_state['mic_round']}")
        with st.expander(t("upload_instead", lang)):
            audio_file = st.file_uploader(t("upload_label", lang), type=["wav", "mp3", "m4a", "ogg"], key="voice_file")
            send_voice = st.button(t("submit", lang), key="send_voice", disabled=audio_file is None)

        voice = None  # (audio bytes, filename) of a spoken question
        if recording is not None:
            voice = (recording.getvalue(), "recording.wav")
        elif send_voice and audio_file is not None:
            voice = (audio_file.read(), audio_file.name)

        # New message: typed, tapped sample question, recorded or uploaded voice
        prompt = prompt or st.session_state.pop("pending_query", None)
        if prompt or voice:
            history = conversation_history()
            with chat:
                if prompt:
                    with st.chat_message("user", avatar="🧑‍🌾"):
                        st.markdown(prompt)
                with st.chat_message("assistant", avatar="🌾"):
                    if prompt:
                        with st.spinner(t("spinner_text", lang)):
                            result = pipeline.process_query(prompt, language=lang, generate_audio=False, history=history)
                    else:
                        with st.spinner(t("spinner_audio", lang)):
                            result = pipeline.process_audio_query(
                                voice[0], filename=voice[1], language=lang, generate_audio=False, history=history,
                            )
            user_text = prompt or result.processing_metadata.get("stt_transcript") or t("voice_not_understood", lang)
            st.session_state["messages"].append({"role": "user", "text": user_text})
            st.session_state["messages"].append({
                "role": "assistant",
                "result": result,
                "id": len(st.session_state["messages"]),
                # Spoken questions get a spoken answer (unless speech-to-text failed)
                "speak": voice is not None and result.intent != "voice_stt_unavailable",
            })
            if recording is not None:
                st.session_state["mic_round"] += 1
            st.rerun()

    st.markdown(f'<div class="ks-footer">{t("sidebar_caption", lang)}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
