# Answers from PAU's Package of Practices

KisanSahayak's own 14 advisories cover a few pests and diseases of wheat, mustard, paddy and cotton. Most real farmer questions are about other topics for those crops: weeds, varieties, nutrient deficiencies, other pests, nursery, harvest. Those are now answered from PAU's *Package of Practices for Crops of Punjab* (Rabi 2025-26, Kharif 2026), citing PAU's page numbers.

```bash
python scripts/build_pau_kb.py     # once: downloads PAU's PDFs and extracts the chapters (git-ignored, copyrighted)
python evalset/pau/run_pau.py      # offline answers, MiniLM search
```

## How a question is routed

- **A topic our advisories cover** (yellow rust, aphids, BLB…), and **symptom descriptions**: our checked advisories, as before.
- **Another topic for a covered crop** (weeds in wheat, varieties of mustard, zinc in paddy, mealybug in cotton): PAU's chapter for that crop only (plus the general spraying chapter). It is searched with the topic's English words, because PAU's book is in English ("गेहूं में गुल्ली डंडा" is searched as "Wheat Phalaris minor weed control"), and sections whose title names the topic rank higher.
- **No crop named, or another crop**: referred to the Kisan Call Centre / KVK, as before.

Follow-ups stay on PAU ("And weeds?" after a wheat question; "What is the dose?" after a PAU answer).

## Results (`results.md`)

| | First run | After adding missing keywords |
|---|---|---|
| Answered from PAU (not referred) | 23/28 | **28/28** |
| From the right crop's chapter | 23/28 | 28/28 |
| Expected PAU section first | 20/28 | **24/28** |
| Expected PAU section in the top 3 | 23/28 | 28/28 |

With Gemini embeddings (the live app's search), after adding the keywords: 28/28 from PAU, expected section first **27/28**, in the top 3 28/28.

The first run is the fair number: these 28 questions were written after the search was built. Its 5 misses were all routing (mealybug, painted bug, paddy straw, Bt hybrids, Punjabi "ਜੈਸਿਡ" were not in the topic word lists, so they went to an unrelated advisory). The words were then added, so the second column is no longer a held-out score.

On the 200 real Kisan Call Centre questions, the 140 outside our advisories are now: **126 answered from the right crop's PAU chapter**, 8 referred to the KVK, 6 shown advice on something else (as before). On 74 held-out KCC queries: 55 from PAU, 6 referred, 13 something else (unchanged).

## Fast start on Streamlit Cloud

Embedding ~400 chunks with Gemini on every cold start took 13 minutes on the free quota. The vectors are computed once by `scripts/build_embedding_cache.py` and shipped in `data/vectors/gemini_embedding_cache.npz` (numbers only, no PAU text); a cold start reuses them and takes about 15 seconds. On Gemini, PAU's chapters are searched only when that file covers them (PyMuPDF is pinned so the extracted text matches).

## Limits

- **Offline answers show PAU's English text** with a note in the farmer's language; the Gemini answer translates it. There are no checked translations of PAU's book.
- **One passage, not a summary:** the offline answer shows the best-matching passage of the best section; the LLM sees the top 3 sections.
- **Searching both sources for every question was tried and dropped:** PAU's English text then beat our advisories on Hindi/Punjabi symptom questions (KCC covered questions in the top 3 fell from 23/25 to 13/25).
- **Not reviewed by an agronomist.** PAU states that it accepts no legal responsibility for the use of its recommendations; answers say to check the product label and ask the KVK.
