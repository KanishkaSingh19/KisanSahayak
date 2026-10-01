# KisanSahayak: real Gemini answer check

*2026-10-02 · 24 questions from `eval/test_set.json` · search embeddings: minilm*

| Metric | Result |
|---|---|
| Gemini answers generated (not fallback) | 24/24 (100%) |
| Gemini answers in the requested script | 24/24 (100%) |
| Gemini answers replaced: a number not in the sources | 1/24 (4%) |
| Answers shown with only source numbers | 24/24 (100%) |
| Gemini response time (median) | 2.0 s |

Every Gemini answer is checked in the app: an amount ("400 g") must appear in the retrieved text with the same unit, and any other number must appear in it (list numbering "1." is ignored). If not, the checked advisory text is shown instead. Full answers are in `eval/results_llm.json`.
