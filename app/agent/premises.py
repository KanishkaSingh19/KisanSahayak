"""Premises stated in words, checked against the evidence an answer uses.

app/agent/claims.py checks claims that have a recognisable form (₹12,000 per month, 100 g Actara, a
disease name). A premise stated in words ("Since MSP guarantees that the government will buy all my
wheat, ...") has no such form, so it is checked here, for every kind of answer, after the answer is
built and before it is shown:

1. A premise cue ("since", "because", "I heard", "क्योंकि", "ਕਿਉਂਕਿ", ...) marks a question that asserts
   something. Questions without one are not checked (no extra cost, no unnecessary corrections).
2. The evidence is what the answer already used (retrieved advisory text, the official scheme text, the
   MSP table, live weather) plus official statements from data/facts/ whose keywords the question uses.
3. A verifier (the LLM) lists the claims the question assumes and labels each against the numbered
   evidence sentences: supported, contradicted, qualified (true only under conditions), or not in the
   evidence. It can only cite evidence by number, and a claim must be words from the question.
4. The correction shown is the cited official sentences, in the farmer's language where the official
   text has a translation; never the LLM's own wording. Without an LLM nothing is claimed either way.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings

FACTS_DIR = settings.DATA_DIR / "facts"
PREMISE_CUE = re.compile(
    r"\b(since|because|as you know|given that|i heard|i have heard|i read|they say|people say|is it true|isn't it|"
    r"guarantee[sd]?|kyunki|kyonki|chunki|suna hai|sunaa hai|maine suna)\b|"
    r"क्योंकि|चूंकि|चूँकि|सुना है|मैंने सुना|ਕਿਉਂਕਿ|ਸੁਣਿਆ ਹੈ|ਮੈਂ ਸੁਣਿਆ",
    re.IGNORECASE,
)
QUALIFIED = "qualified"  # true only partly or under conditions the question leaves out
VERDICTS = ("supported", "contradicted", QUALIFIED, "not_in_evidence")
# A "claim" that starts like a question is the farmer's request, not something the question assumes
_ASKS = re.compile(
    r"^(how|what|where|when|which|why|who|should|can|could|shall|will|is|are|do|does|did|kaise|kya|kahan|kab|"
    r"kitna|kitni|kaun|kyun)\b|^(कैसे|क्या|कहाँ|कहां|कब|कितना|कितनी|कौन|ਕਿਵੇਂ|ਕੀ|ਕਿੱਥੇ|ਕਦੋਂ|ਕਿੰਨਾ|ਕਿੰਨੀ|ਕੌਣ)",
    re.IGNORECASE)
MAX_EVIDENCE = 40  # sentences given to the verifier


def asserts_something(question: str) -> bool:
    return bool(PREMISE_CUE.search(question))


def premise_clause(question: str) -> str:
    """The words after the premise cue, up to the next comma or question mark ("Since MSP guarantees
    that ..., where should I sell?" -> "MSP guarantees that ..."); used when no verifier could run."""
    cue = PREMISE_CUE.search(question)
    if not cue:
        return ""
    clause = re.split(r"[,?।!]", question[cue.end():], maxsplit=1)[0].strip(" .:")
    return re.sub(r"^(that|ki|कि|ਕਿ)\s+", "", clause, flags=re.IGNORECASE)


@lru_cache(maxsize=1)
def load_facts(facts_dir: Path = FACTS_DIR) -> List[dict]:
    """Official statements, each {"id", "text": {lang: sentence}, "source", ...} from data/facts/*.json."""
    facts = []
    for path in sorted(Path(facts_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for fact in data["facts"]:
            facts.append({**fact, "topic": data["topic"], "keywords": data["keywords"], "source": data["source"],
                          "source_url": data["source_url"]})
    return facts


def facts_for(question: str) -> List[dict]:
    """Official statements on the topics the question names."""
    from app.textmatch import contains_term

    return [f for f in load_facts() if any(contains_term(k, question, whole_word=False) for k in f["keywords"])]


def evidence_sentences(texts: List[str]) -> List[str]:
    """The evidence as numbered-to-be sentences: no headings, no repeats, at most MAX_EVIDENCE."""
    out = []
    for text in texts:
        for s in re.split(r"(?<=[.!?।])\s+|\n+", text):
            s = s.strip(" *#-•")
            if len(s.split()) >= 4 and s not in out:
                out.append(s)
    return out[:MAX_EVIDENCE]


def _norm(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.lower()).strip()


def claim_from_question(claim: str, question: str) -> Optional[str]:
    """The claim as words of the question (the verifier must not put words in the farmer's mouth)."""
    if _norm(claim) and _norm(claim) in _norm(question):
        return claim.strip(" .,?!")
    return None


PROMPT = """You check the factual assumptions in a farmer's question against official evidence.

Question: {question}

Evidence (numbered sentences from official sources):
{evidence}

List each factual claim about the world that the question assumes is true. Ignore the farmer's own situation
("my wheat has rust"), questions and requests. Copy each claim's words exactly from the question.
For each claim give a verdict, using ONLY the evidence:
- "supported": the evidence states it
- "contradicted": the evidence states something incompatible with it
- "qualified": the evidence shows it is true only partly or only under conditions the claim leaves out
- "not_in_evidence": the evidence does not say
Do not list what the farmer asks or wants to do ("how do I register", "where should I sell it").
Cite the numbers of the evidence sentences that justify the verdict (none for not_in_evidence). For "contradicted"
and "qualified", cite every sentence the farmer needs to see the correct position, including any options the
evidence gives them.

Return JSON only: {{"claims": [{{"claim": "...", "verdict": "...", "evidence": [1, 2]}}]}}"""


class PremiseVerifier:
    """Asks the LLM to label the question's claims against numbered evidence (see module notes)."""

    def __init__(self, api_key: str, models: List[str]):
        from google import genai
        from google.genai import types

        retry = types.HttpRetryOptions(attempts=2, initial_delay=0.5, max_delay=1.0, http_status_codes=[500, 503])
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(retry_options=retry, timeout=10_000))
        self.models = models

    def verify(self, question: str, evidence: List[str]) -> Optional[List[Dict]]:
        """The labelled claims, or None when no model answered."""
        from google.genai import types

        prompt = PROMPT.format(question=question, evidence="\n".join(f"[{i}] {s}" for i, s in enumerate(evidence, 1)))
        for model in self.models:
            try:
                resp = self.client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
                )
                data = json.loads(resp.text)
                return data if isinstance(data, list) else data.get("claims", [])  # some models drop the wrapper
            except Exception as e:
                print(f"[Warning] Premise check ({model}) failed: {str(e)[:120]}")
        return None


def get_premise_verifier() -> Optional[PremiseVerifier]:
    """The verifier, or None when no LLM is configured (then worded premises are not judged)."""
    if settings.LLM_PROVIDER.lower() != "gemini" or not settings.GEMINI_API_KEY:
        return None
    try:
        return PremiseVerifier(settings.GEMINI_API_KEY, [m for m in (settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL) if m])
    except Exception as e:
        print(f"[Warning] Premise verifier unavailable: {str(e)[:120]}")
        return None


def judged_premises(question: str, raw: List[Dict], evidence: List[str], already: List[str]) -> List[Dict]:
    """The verifier's labels, kept only when they are well-formed: the claim is words from the question,
    the verdict is known, cited numbers point at real evidence (contradicted/qualified need at least one),
    and the claim was not already handled by the form-based checks (`already`)."""
    kept = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        claim = claim_from_question(str(item.get("claim", "")), question)
        verdict = item.get("verdict")
        numbers = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        cited = [n for n in numbers if isinstance(n, int) and 1 <= n <= len(evidence)]
        if not claim or _ASKS.match(claim) or verdict not in VERDICTS or any(_norm(a) and _norm(a) in _norm(claim) for a in already):
            continue
        if verdict in ("contradicted", "qualified") and not cited:
            continue
        kept.append({"claim": claim, "verdict": verdict, "cited": cited})
    return kept
