# Real farmer questions: Kisan Call Centre test set (200)

200 real farmer queries from the **Kisan Call Centre (KCC)**, 50 each in English, Hindi, Punjabi and Hinglish, covering wheat, paddy, cotton, mustard, weather, PM-KISAN and pesticide use.

## Source
- **Data:** Punjab KCC query logs, January–July 2025: 80,613 calls, each with the Farm Tele Advisor's answer.
- **Where it comes from:** the government's *KCC transcripts of farmers' queries and answers* (data.gov.in, Open Government License). We used the public mirror [`whitesnek/punjab_kcc`](https://huggingface.co/datasets/whitesnek/punjab_kcc) (MIT) because data.gov.in and the ICAR KCC portal were not reachable from our network.
- **Download:** the raw file (`data/kcc/punjab.csv`, 53 MB) is not committed:
  ```bash
  curl -L -o data/kcc/punjab.csv https://huggingface.co/datasets/whitesnek/punjab_kcc/resolve/main/punjab.csv
  ```

## How the questions were chosen
1. **`select_questions.py`** groups the logs by topic, merges near-duplicate wordings and skips entries that aren't questions (call transfers, survey calls, contact-number requests, rows where the answer was pasted into the question field).
2. It takes the **most frequently asked** distinct queries per topic: wheat 52, paddy 52, cotton 30, mustard 26, weather 15, PM-KISAN 15, pesticide use 10. They were chosen by what farmers ask most, **not** by whether KisanSahayak can answer them.
3. **`build_testset.py`** rotates the languages through each topic, so every topic is asked in every language:
   - **English** questions are the exact logged text.
   - **Hindi, Punjabi and Hinglish** questions are translations of *other* real queries. KCC logs record queries only in English, as written by the advisor. The translations were made with an AI assistant and should be spot-checked by native speakers.
   - **Weather** calls are logged without any question text, so they are asked as "weather today" in the caller's district.
4. Each question is labelled with what a correct answer needs: the advisory section that covers it, weather for the district, PM-KISAN, a banned-pesticide warning, or **not in our advisories**. The labelling rules are in `build_testset.py`.

## Run
```bash
python evalset/kcc/run_kcc.py                  # offline answers, repeatable, no API quota
python evalset/kcc/run_kcc.py --llm --pause 5  # real Gemini answers
python evalset/kcc/heldout.py                  # held-out check (see below)
```

## Results
See [`results.md`](results.md).

**Coverage is the main finding.** Only **26 of 200** real questions are about topics our advisories cover. Most farmer calls are about weeds and herbicides, nutrient deficiencies (zinc, iron, manganese), varieties, fertilizer for paddy and cotton, and other pests. (MSP price questions are now answered by the market-price feature.)

For those questions the wrong behaviour is to show the nearest advisory for a different problem. Before this test set, the app did that for 99% of them. It then referred 96% to the **Kisan Call Centre (1800-180-1551)** or the local **KVK**. Now, with PAU's *Package of Practices* chapters indexed (see [`../pau/README.md`](../pau/README.md)), **125 of 140 (89%)** are answered from PAU's chapter for the right crop, 9 are referred and 6 still get advice on something else.

**Held-out check.** The routing rules were improved using this set, so it is partly a development set. `heldout.py` checks the next 85 most-asked real queries, which were never looked at while tuning. There, out of 74 out-of-scope questions, **55 (74%)** are answered from the right crop's PAU chapter, 6 are referred and 13 get advice on something else. That is the fair number to quote. Whether each PAU passage fully answers the question is for the agronomist review below.

## Agronomist review
Answer and dose accuracy need an expert. **`review_sheet.csv`** lists every answer to a covered question, and every answer from PAU's chapters, next to the KCC advisor's answer, with columns for *answer correct*, *dose correct* and comments.

Example of what the review should catch: an early version of our wheat aphid advisory gave a different Actara dose from PAU's (now corrected to PAU's 20 g per acre); the sheet puts each dose next to the KCC advisor's.

## Files
| File | What it is |
|---|---|
| `select_questions.py` | picks the most-asked real queries from the logs → `selected.json` |
| `translations.json` | Hindi, Punjabi and Hinglish versions (AI-translated) |
| `build_testset.py` | builds `kcc_200.json` with languages and expected answers |
| `run_kcc.py` | runs the 200 questions → `results.md`, `results.json`, `review_sheet.csv` |
| `heldout.py` | held-out check on queries not used for tuning → `heldout_results.md` |
