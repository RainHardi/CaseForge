# Sample inputs

All three are **team-constructed and fictional** (no real client, no confidential data), so they are
safe to send to the Gemini API. They exist so the pipeline can be run and tested before the real
inputs from BT-2 arrive. Replace or extend them with real, cleared project inputs.

| Folder | Input type | Deliberately weak spot |
|---|---|---|
| `01_clean_form/` | Structured form (`input.json`) + one image | — (the "good" case) |
| `02_rough_notes/` | Messy bullet notes (`notes.txt`) | No measured result, no stated client problem section |
| `03_pasted_chat/` | Pasted team chat (`chat.txt`) | No client name, no measured result, chit-chat mixed in |

Each folder has a `facts.md`: the hand-written fact list, written **before** running the input
through CaseForge (Test Plan §2). Use it for the manual claim check (T-04).

## Input formats

- `.json` — any of these keys: `title, client_name, client_problem, work_done, technical_approach,
  tools, challenges, results, raw_notes, images` (images: `[{"filename", "caption", "section"}]`,
  paths relative to the JSON file).
- `.txt` / `.md` — anything; it is treated as raw notes.
