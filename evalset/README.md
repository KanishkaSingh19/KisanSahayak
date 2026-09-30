# Feature test set (25 questions)

End-to-end checks that every feature of KisanSahayak works: crop advice in four languages, diagnosis from symptoms, multi-turn memory, safety guardrails, weather, the farm profile, PM-KISAN, photo diagnosis and voice.

| File | What it is |
|---|---|
| [`questions.md`](questions.md) | The 25 questions with pass criteria, for testing by hand in the app |
| [`questions.json`](questions.json) | The same cases in machine-readable form |
| [`run_evalset.py`](run_evalset.py) | Runs cases 1–22 through the pipeline and checks them automatically |
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

Cases 23–25 (photo upload, taking a photo, and voice) need a real camera or microphone. Check them by hand as described in `questions.md`.

## How it differs from `eval/`

- **`eval/`** measures *accuracy*: 67 short questions scoring how often the right advisory is found (93–98% first).
- **`evalset/`** checks *features*:
  - whole conversations
  - farm profiles
  - PM-KISAN eligibility
  - weather
  - the "crop not covered" guard
  - photo and voice

Both sets were written by the team, not collected from farmers.
