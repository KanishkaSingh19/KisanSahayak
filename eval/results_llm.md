# KisanSahayak: real Gemini answer check

*2026-09-29 · 8 questions from `eval/test_set.json` · search embeddings: minilm*

| Metric | Result |
|---|---|
| Gemini answers generated (not fallback) | 8/8 (100%) |
| Gemini answers in the requested script | 8/8 (100%) |
| Gemini answers with no invented numbers | 8/8 (100%) |
| Gemini response time (median) | 3.3 s |

"No invented numbers": every number in the answer (doses, percentages, dates) appears in the retrieved advisory text or the question; list numbering ("1.") is ignored. Full answers are in `eval/results_llm.json`.
