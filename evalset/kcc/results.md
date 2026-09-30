# Real farmer questions: Kisan Call Centre test set

*2026-10-01 · 200 questions (50 each English, Hindi, Punjabi, Hinglish) · source: Kisan Call Centre, Punjab, Jan-Jul 2025 (data.gov.in KCC transcripts, via huggingface.co/datasets/whitesnek/punjab_kcc) · answers: offline template (no API quota) · search embeddings: minilm*

## Coverage

| Questions | Count |
|---|---|
| Answered by our crop/safety advisories | 26 |
| Weather | 15 |
| PM-KISAN | 15 |
| **Outside our advisories** (weeds, nutrient deficiencies, varieties, MSP, other pests…) | **144** |

## Metrics

| Metric | Result |
|---|---|
| Retrieval: right advisory in top 3 (covered questions) | **25/25 (100%)** |
| Retrieval: right advisory first | 21/25 (84%) |
| Banned-pesticide questions warned | 1/1 (100%) |
| Weather questions answered with weather | 15/15 (100%) |
| Weather for the right district | 15/15 (100%) |
| PM-KISAN questions recognised | 15/15 (100%) |
| Outside our advisories: referred to KVK (not shown another topic's advice) | **138/144 (96%)** |
| Answer in the requested language (script) | 200/200 (100%) |
| Response time median / p95 | 2 ms / 664 ms |

| Language | Answer in the right script |
|---|---|
| en | 50/50 (100%) |
| hi | 50/50 (100%) |
| pa | 50/50 (100%) |
| hinglish | 50/50 (100%) |

## Notes

- English questions are the exact text logged by the Kisan Call Centre; Hindi, Punjabi and Hinglish questions are translations of other real queries (the logs record queries in English). Weather calls are logged without text and are asked as a forecast question for the caller's district.
- Questions were chosen by how often farmers asked them, not by whether KisanSahayak can answer them.
- Answer and dose accuracy need an agronomist: see `review_sheet.csv`, which puts each answer next to the Kisan Call Centre advisor's answer.
