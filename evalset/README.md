# Feature test set (28 questions)

End-to-end checks that every feature of KisanSahayak works: crop advice in four languages, diagnosis from symptoms, multi-turn memory, safety guardrails, weather, the farm profile, PM-KISAN, photo diagnosis and voice.

| File | What it is |
|---|---|
| [`questions.md`](questions.md) | The 28 questions with pass criteria, for testing by hand in the app |
| [`questions.json`](questions.json) | The same cases in machine-readable form |
| [`run_evalset.py`](run_evalset.py) | Runs cases 1–22 and 26–28 through the pipeline and checks them automatically |
| [`results.md`](results.md) | Latest results (written by the script) |
| `results.json` | Every answer from the latest run, for review |

## Run it

```bash
python evalset/run_evalset.py
```

This uses offline template answers, so it is repeatable and uses no Gemini quota. Weather uses live Open-Meteo data. To check real Gemini answers instead (uses API quota):

```bash
python evalset/run_evalset.py --llm
```

With `--llm`, results go to `results_llm.md` / `results_llm.json`, and the report lists which Gemini model wrote each answer. If every model runs out of quota, the run stops without writing results, so offline answers are never counted as LLM ones. Change the key and run again. On the free tier, add `--pause 5` to stay under the per-minute request limit.

Cases 23–25 (photo upload, taking a photo, and voice) need a real camera or microphone. Check them by hand as described in `questions.md`.

## How it differs from `eval/`

- **`eval/`** measures *accuracy*: 67 short questions scoring how often the right advisory is found (ranked first: 83% with local MiniLM search, 98% with Gemini search).
- **`evalset/`** checks *features*:
  - whole conversations
  - farm profiles
  - PM-KISAN eligibility
  - weather
  - the "crop not covered" guard
  - photo and voice

Both sets were written by the team, not collected from farmers.
