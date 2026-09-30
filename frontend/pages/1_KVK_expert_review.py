"""KVK expert review: experts check pesticide, uncertain and unanswered answers from the chat."""

import csv
import io
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st

try:
    st.secrets.load_if_toml_exists()  # REVIEW_PASSCODE and other settings on Streamlit Cloud
except Exception:
    pass

from app.review import REASONS, ReviewQueue  # noqa: E402

st.set_page_config(page_title="KVK expert review - KisanSahayak", page_icon="🌾", layout="wide")

VERDICTS = {
    "correct": "Correct",
    "needs_correction": "Needs correction",
    "unsafe": "Unsafe: must not be shown",
}


@st.cache_resource
def get_queue() -> ReviewQueue:
    return ReviewQueue()


st.title("KVK expert review")
st.caption(
    "Answers that need an expert's check are collected here: any pesticide spray or dose, banned-pesticide "
    "questions, AI answers weakly backed by the sources, uncertain photo diagnoses, and questions the "
    "advisories do not cover. Only the question and answer are stored, no personal details."
)

# Optional passcode, so only KVK experts can mark answers (set REVIEW_PASSCODE in .env or Streamlit Secrets)
passcode = os.environ.get("REVIEW_PASSCODE", "")
if passcode:
    if st.session_state.get("review_ok") is not True:
        entered = st.text_input("Reviewer passcode", type="password")
        if entered and entered == passcode:
            st.session_state["review_ok"] = True
            st.rerun()
        elif entered:
            st.error("Wrong passcode.")
        st.stop()
else:
    st.info("Demo mode: anyone can review. Set REVIEW_PASSCODE in the app's Secrets to restrict this page to KVK experts.")

queue = get_queue()
stats = queue.stats()
cols = st.columns(5)
cols[0].metric("Waiting for review", stats["pending"])
cols[1].metric("Reviewed", stats["reviewed"])
cols[2].metric("Correct", stats["correct"])
cols[3].metric("Needs correction", stats["needs_correction"])
cols[4].metric("Unsafe", stats["unsafe"])

left, right = st.columns([1, 2])
status = left.radio("Show", ["pending", "reviewed", "all"], horizontal=True,
                    format_func={"pending": "Waiting", "reviewed": "Reviewed", "all": "All"}.get)
reasons = right.multiselect("Reason", list(REASONS), format_func=REASONS.get)

items = queue.items(None if status == "all" else status)
if reasons:
    items = [i for i in items if set(i["reasons"]) & set(reasons)]

if items:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(items[0]), extrasaction="ignore")
    writer.writeheader()
    writer.writerows({**i, "reasons": "; ".join(i["reasons"]), "sources": "; ".join(i["sources"])} for i in items)
    st.download_button("Download as CSV", buffer.getvalue().encode("utf-8-sig"), "kvk_review.csv", "text/csv")

if not items:
    st.success("Nothing here. New answers that need a check will appear as farmers use the app.")

for item in items:
    with st.container(border=True):
        st.markdown(f"**{item['question']}**")
        st.caption(
            f"{item['created'][:16].replace('T', ' ')} UTC · language: {item['language']} · "
            f"{', '.join(REASONS.get(r, r) for r in item['reasons'])}"
            + (f" · grounding {item['grounding_score']:.2f}" if item.get("grounding_score") is not None else "")
            + (f" · answer: {item['answer_source']}" if item.get("answer_source") else "")
        )
        with st.expander("Answer shown to the farmer", expanded=item["status"] == "pending"):
            st.markdown(item["answer"])
            if item["sources"]:
                st.caption("Sources: " + "; ".join(item["sources"]))
        if item["status"] == "reviewed":
            st.markdown(f"**Verdict:** {VERDICTS.get(item['verdict'], item['verdict'])}"
                        + (f" · by {item['reviewer']}" if item["reviewer"] else ""))
            if item["correction"]:
                st.markdown(f"**Correction:** {item['correction']}")
            continue
        with st.form(f"review_{item['id']}"):
            verdict = st.radio("Verdict", list(VERDICTS), format_func=VERDICTS.get, horizontal=True)
            correction = st.text_area("Correct advice (if the answer needs correcting)")
            reviewer = st.text_input("Your name / KVK (optional)")
            if st.form_submit_button("Save review"):
                if verdict != "correct" and not correction.strip():
                    st.warning("Please write the correct advice, or why the answer is unsafe.")
                else:
                    queue.review(item["id"], verdict, correction, reviewer)
                    st.rerun()
