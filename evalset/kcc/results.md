# Real farmer questions: Kisan Call Centre test set

*2026-10-01 · 200 questions (50 each English, Hindi, Punjabi, Hinglish) · source: Kisan Call Centre, Punjab, Jan-Jul 2025 (data.gov.in KCC transcripts, via huggingface.co/datasets/whitesnek/punjab_kcc) · answers: offline template (no API quota) · search embeddings: minilm*

## Coverage

| Questions | Count |
|---|---|
| Answered by our crop/safety advisories | 26 |
| Weather | 15 |
| PM-KISAN | 15 |
| Market prices (MSP / mandi) | 4 |
| **Outside our advisories** (weeds, nutrient deficiencies, varieties, MSP, other pests…) | **140** |

## Metrics

| Metric | Result |
|---|---|
| Retrieval: right advisory in top 3 (covered questions) | **23/25 (92%)** |
| Retrieval: right advisory first | 20/25 (80%) |
| Banned-pesticide questions warned | 1/1 (100%) |
| Weather questions answered with weather | 15/15 (100%) |
| Weather for the right district | 15/15 (100%) |
| PM-KISAN questions recognised | 15/15 (100%) |
| Price questions answered with the MSP / mandi price | 4/4 (100%) |
| Outside our advisories: answered from PAU's Package of Practices, right crop's chapter | **126/140 (90%)** |
| Outside our advisories: referred to KVK | 8/140 (6%) |
| Outside our advisories: shown advice on something else | 6/140 (4%) |
| Answer in the requested language (script) | 200/200 (100%) |
| Response time median / p95 | 64 ms / 833 ms |

| Language | Answer in the right script |
|---|---|
| en | 50/50 (100%) |
| hi | 50/50 (100%) |
| pa | 50/50 (100%) |
| hinglish | 50/50 (100%) |

## Covered questions where the right advisory was not in the top 3

- (pa) "ਕਣਕ ਦੀ ਫ਼ਸਲ ਵਿੱਚ ਪਾਣੀ ਦਾ ਪ੍ਰਬੰਧ ਕਿਵੇਂ ਕਰੀਏ?" → got Yellow Rust (Pila Rataua / Peeli Kungi) Identification and Management, Bacterial Leaf Blight (BLB / Peela Jhulsa) in Paddy, Brown Planthopper (BPH / Bhoora Tilla) Management; expected Wheat Sowing
- (hi) "तिलहन फसलों में सिंचाई का प्रबंधन कैसे करें?" → got Brown Planthopper (BPH / Bhoora Tilla) Management, Bacterial Leaf Blight (BLB / Peela Jhulsa) in Paddy, Pink Bollworm (Gulabi Sundhi) Integrated Management; expected Mustard Fertilizer

## Notes

- English questions are the exact text logged by the Kisan Call Centre; Hindi, Punjabi and Hinglish questions are translations of other real queries (the logs record queries in English). Weather calls are logged without text and are asked as a forecast question for the caller's district.
- Questions were chosen by how often farmers asked them, not by whether KisanSahayak can answer them.
- Answer and dose accuracy need an agronomist: see `review_sheet.csv`, which puts each answer next to the Kisan Call Centre advisor's answer.
