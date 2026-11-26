# Team Deployment Plan

| | |
|---|---|
| **Project** | CaseForge, Team 5 |
| **Purpose** | How we run the website for Demo Day (30 Nov 2026), what can break, and who does what |
| **Last Updated** | 26 November 2026 |

No API keys or passwords are written in this document or in the repository (see [Team Ground Rules](team-ground-rules.md)). Setup steps are in [DEPLOY.md](DEPLOY.md).

| Question | Answer |
|---|---|
| 1. Parts | **Frontend:** browser website (HTML/CSS/JS served by our server). **Backend:** Python FastAPI: accounts, pipeline (extract facts, draft, two checks), approval lock, PDF export. **Model:** none of our own; we call the Gemini API (`gemini-3.5-flash-lite`). If it is busy the server retries, tries backup models, then falls back to the offline rules mode. **Data:** Neon Postgres (SQLite on laptops); optional Notion import |
| 2. Inference | **Near-real-time.** The user waits tens of seconds for one request chain, then reviews the draft on screen. Not real-time streaming and not offline batch |
| 3. Hosting | Website and backend: Render free web service, deployed from this repository. Database: Neon free Postgres. Model: Gemini API free tier, key kept only as a Render environment variable. We hold no prepaid credits, so nothing expires on a date. Limits: Render sleeps after 15 min idle (about 1 min to wake), Neon sleeps after 5 min idle, Gemini has per-minute and per-day limits that reset daily. Our own cap is 30 case studies per user per day |
| 4. Risks | **(1) Cold start:** first visit after idle takes about a minute. Fix: open `/healthz` and run one example 10 minutes before our slot. **(2) Gemini busy or over the free limit:** Fix: automatic retries, backup models, offline rules mode, the built-in "Messy notes" example, and the recorded video as last resort |
| 5. Backup | Both: a local run of the same code on a team laptop (DevTunnel, see DEPLOY.md) and a recorded video of the full flow |
| 6. Owners and dates | Abdulaziz: final deploy by 27 Nov. Dilshodjon: backup video link by 28 Nov. Odina and Muhammadkodir: test on a second phone and laptop on 29 Nov. Anvarbek: warm-up and demo on 30 Nov |
| 7. Links | Public URL: https://caseforge-rcdu.onrender.com (health check `/healthz`). Repository: https://github.com/RainHardi/CaseForge. Backup video: https://drive.google.com/file/d/1ujopcPll4s91QzJDJR9LIflCgRubIPvK/view?usp=drivesdk |
