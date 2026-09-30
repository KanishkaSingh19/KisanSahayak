# KisanSahayak feature test results

*2026-10-01 · 25 test cases (`evalset/questions.json`) · answers: LLM (gemini-3.7-flash, backup gemini-flash-lite-latest; see 'Answers by source') · search embeddings: minilm · weather: live Open-Meteo*

| Result | Value |
|---|---|
| Automated cases passed | **22/22** |
| Conversation turns passed | 34/34 |
| Manual cases (photo, voice) | 3, see `evalset/questions.md` |
| Answers by source | llm:gemini-flash-lite-latest: 25 |

| # | Feature | Result |
|---|---|---|
| 1 | Multi-turn memory: symptoms, follow-ups, topic switches, banned pesticide, language switch | pass |
| 2 | Punjabi answer: mustard aphid | pass |
| 3 | Hinglish answer: brown planthopper | pass |
| 4 | Hindi, symptoms only: bacterial leaf blight | pass |
| 5 | Cotton pink bollworm: traps, threshold and dose | pass |
| 6 | Hindi, symptoms: cotton whitefly and leaf curl | pass |
| 7 | Crop planning: wheat sowing time and seed rate | pass |
| 8 | Fertilizer: mustard NPK and sulphur | pass |
| 9 | Punjabi, symptoms: mustard white rust | pass |
| 10 | Symptoms only: Karnal bunt | pass |
| 11 | Hinglish, symptoms: paddy sheath blight | pass |
| 12 | Scope: greeting, then an off-topic question | pass |
| 13 | Guardrail: banned pesticide named in Hindi script | pass |
| 14 | Safety: pesticide on the skin (first aid) | pass |
| 15 | Hallucination check: a crop the advisories do not cover | pass |
| 16 | Weather: named place, spray advice only when asked | pass |
| 17 | Weather: unknown place is reported, not silently replaced | pass |
| 18 | Farm profile: district used for weather, and a changed district wins | pass |
| 19 | Farm profile: the farmer's crop is used when none is named | pass |
| 20 | PM-KISAN: benefit amount | pass |
| 21 | PM-KISAN: rule-based eligibility from the profile, and a follow-up | pass |
| 22 | PM-KISAN: why an instalment is held, and eKYC | pass |
| 23 | Photo diagnosis: upload and take a photo of a covered crop | manual |
| 24 | Photo diagnosis: crop the advisories do not cover | manual |
| 25 | Voice: live recording in English and Punjabi, answer read aloud | manual |
