# KisanSahayak evaluation results

*2026-10-01 · 67 hand-written test questions in English, Punjabi, Hinglish and Hindi (`eval/test_set.json`) · search embeddings: **gemini** · answers: offline template (deterministic, no API quota)*

| Metric | Result |
|---|---|
| Right advisory ranked 1st | **41/42 (98%)** |
| Right advisory in top 3 | **42/42 (100%)** |
| Question type (intent) recognised | 41/42 (98%) |
| Weather: right place detected | 8/8 (100%) |
| Greetings / off-topic handled | 6/6 (100%) |
| Banned-pesticide questions warned | **5/5 (100%)** |
| False banned-pesticide warnings | 0 of 39 questions not about banned pesticides |
| Follow-up questions kept context | 6/6 (100%) |
| Response time without LLM (median / p95) | 601 ms / 696 ms |

## Retrieval by language

| Language | Right advisory 1st | In top 3 |
|---|---|---|
| en | 14/14 (100%) | 14/14 (100%) |
| pa | 5/5 (100%) | 5/5 (100%) |
| hinglish | 13/13 (100%) | 13/13 (100%) |
| hi | 9/10 (90%) | 10/10 (100%) |

## Failures

- Intent: "White flies under cotton leaves and the leaves are curling, what should I do?" → general_agriculture, expected crop_question
- Retrieval: "सरसों में सफेद रतुआ रोग का उपचार" → got *Mustard Aphid (Chetpa/Mahu) Management*, expected *White Rust*

## Notes

- The test questions were written by the team, not collected from farmers; a field test set is future work.
- Retrieval, intent, weather-place, safety and follow-up checks do not call the LLM, so they are repeatable.
- A false banned-pesticide warning means a warning on a question that is not about banned pesticides.
- "No invented numbers" means every number in a Gemini answer (doses, percentages, dates) appears in the retrieved advisory text or the question.
