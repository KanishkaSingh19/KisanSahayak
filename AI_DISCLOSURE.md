# AI Tools Disclosure: KisanSahayak (Team Powerpuff Girls)

## 1. AI tools used to build the project

| Tool | What it was used for |
|---|---|
| **Claude Code (Anthropic, Claude Opus)** | Coding assistant for most of the implementation, under the team's direction and review. Work covered: the agent pipeline and router, hybrid RAG search, guardrails, Streamlit UI and FastAPI backend, voice and photo features, farm profile, PM-KISAN and market-price modules, the KVK review queue, the claim and premise checks, the tests (414) and GitHub Actions, the evaluation scripts, the README and deployment setup. It also selected and labelled the 200 Kisan Call Centre questions using the rules in `evalset/kcc/`, translated 150 of them, and drafted slide text. |
| **ChatGPT (OpenAI)** | Generating the architecture and technology-stack diagram images for the presentation, from our written descriptions. |
| **Google Gemini** | One-time translation of the advisories into Punjabi, Hindi and Hinglish for offline answers (`scripts/translate_advisories.py`). A translation was rejected automatically if any number (dose, percentage, date) changed. |

## 2. What the team did
- Chose the problem, users, features and design, and directed every change. Reviewed and tested the app, and decided what to keep: for example, catching a wrong weather district, advice that wasn't asked for, lost conversation memory and misplaced UI buttons.
- Chose the knowledge sources (PAU Package of Practices for Crops of Punjab, ICAR and CIBRC advisories; pmkisan.gov.in; the Government of India MSP decisions; Kisan Call Centre logs) and remains responsible for their accuracy.
- Had the crop advisories checked against PAU's *Package of Practices* (Rabi 2025-26, Kharif 2026). The first versions, drafted with AI help, had doses, thresholds and varieties that differed from PAU (for example the wheat aphid dose, rust-resistant varieties and an antibiotic spray for bacterial blight that PAU does not recommend). These were corrected to PAU's recommendations, and each section now cites PAU's page numbers. PAU states that it accepts no legal responsibility for the use of its recommendations.
- Tested the app by hand: voice, camera, the four languages, the live deployment.
- Managed the API keys, the Streamlit Community Cloud deployment and the GitHub repository. Contributed sample crop photos for testing.

## 3. AI inside the product

| Purpose | Model / service |
|---|---|
| Writing answers | Google Gemini 3.7 Flash, with Gemini Flash-Lite as backup, then a deterministic offline template (no AI) |
| Crop photo diagnosis | Gemini Vision. It names the likely problem only; the treatment always comes from the verified advisories. |
| Answers from PAU's *Package of Practices* | Not AI: PAU's own text, found by the same search and shown with its page numbers. Gemini, when available, translates and summarises the passages; offline answers show PAU's English text with a note in the farmer's language. |
| Checking assumptions stated in words | Gemini labels each assumption against numbered evidence sentences and cites them; the correction shown is the cited official text. Figures are checked in code. |
| Search embeddings | `gemini-embedding-001` on the cloud; multilingual MiniLM-L12-v2 offline |
| Speech-to-text | Whisper Large v3 via Groq; Gemini audio for Punjabi and as backup |
| Text-to-speech | Microsoft Edge-TTS; Google gTTS for Punjabi |
| **Not AI (rule-based)** | Question routing, banned-pesticide filter, grounding check, PM-KISAN eligibility, weather advice, MSP and mandi prices, the "not covered" referral to the Kisan Call Centre / KVK, and choosing answers for KVK expert review |

## 4. Safeguards on AI output
- Answers are grounded only in retrieved advisories. Every answer gets a grounding check, the CIBRC banned-pesticide filter and statutory spray disclaimers.
- The LLM never decides a number: every amount in a Gemini answer must appear in the retrieved text with the same unit (and every other number in it); otherwise the checked text is shown instead and the answer is logged for KVK review. Totals for the farmer's acres are calculated in code.
- Assumptions in a question are checked: figures in code, assumptions stated in words by Gemini against numbered evidence sentences (the retrieved or official text plus the sourced statements in `data/facts/`). Gemini only labels a claim (supported, contradicted, only true under conditions, not in the evidence) and cites sentence numbers; the claim must be the farmer's own words and the citations must exist, otherwise the label is ignored. The correction the farmer sees is the cited official text, not Gemini's wording. The `data/facts/` statements and their Hindi, Punjabi and Hinglish translations were written by Claude from the official source named in each file.
- Prices, PM-KISAN eligibility and weather figures come from data and rules, never from the language model.
- Questions outside the advisories are referred to the Kisan Call Centre (1800-180-1551) and the KVK instead of being answered with unrelated advice.
- Pesticide, weakly grounded and uncertain photo answers are sent to a KVK expert review queue, and photo answers are labelled as an AI estimate.
- Evaluations record which model wrote each answer, and never count offline answers as LLM answers.

## 5. AI-generated data and limitations
- **AI-generated text in the data:** the Punjabi, Hindi and Hinglish advisory translations (`data/translations.json`), the scheme guidance texts (PM-KISAN from pmkisan.gov.in; PMFBY crop insurance and the Kisan Credit Card from the PMFBY operational guidelines and PIB releases, in `data/schemes/`; Claude read the official pages and wrote the text and its translations, keeping every number identical), and the 150 non-English test questions (`evalset/kcc/translations.json`). None of this has yet been checked by native speakers or experts.
- **Test questions:**
  - The 200-question test set uses real Kisan Call Centre queries. Its English questions are the exact logged text; the others are AI translations of real queries.
  - The 67-question accuracy set (`eval/`), the 28-question feature set (`evalset/`) and the 28 PAU questions (`evalset/pau/`) were written by the team.
- **Expert review:** answer and dose accuracy have not yet been checked by an agronomist. `evalset/kcc/review_sheet.csv` is prepared for that review.
