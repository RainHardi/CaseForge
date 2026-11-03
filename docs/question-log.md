# Question Log

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator |
| **Repository** | CaseForge |
| **Team** | Team 5 |
| **Open questions** | 16 of 20 |
| **Last Updated** | 4 November 2026 |

Every undecided detail in our documents is marked **TBD** and recorded here, so that there is one place to look for what is still unresolved and who can resolve it.

**How we use this log**

- Anything marked TBD anywhere in the repository has a question here.
- Each question names who can answer it, not just that it is open. A question with no owner does not get answered.
- When a question is answered, the answer is written in the table, the status becomes **Decided**, and the document that depended on it is updated in the same week.
- Questions that came from a specific document keep their original reference (Q-D01, Q-T01) so that links from those documents still make sense.

---

## Most urgent

Now that the pipeline is built, the open questions that block the Baseline are all about **input and verification**, not code:

- **Q-001** and **Q-005** — Baseline item B4 requires three *real* project inputs. Neither HumbleBeeAI nor any classmate has been asked yet. This is the oldest open item in the project and the only thing standing between us and a complete Baseline.
- **Q-002** — if Google's free-tier terms do not allow sending real client project information, B4 needs a different data plan entirely.
- **Q-006** — the catch-rate target was never confirmed, and we have now reported a result against it.

Three questions were closed by the implementation on 31 October: **Q-012**, **Q-013** and **Q-015**. **Q-004** was answered by the test run itself.

---

## Open questions

| ID | Question | Raised | Asked by | Who can answer | Blocking | Status |
|---|---|---|---|---|---|---|
| **Q-001** *(Q-D01)* | Which HumbleBeeAI projects are cleared for external sharing, and in what format will we receive them? | 20 Sep 2026 | Odina | HumbleBeeAI / instructors | B4, BT-2, T-10 | Not yet asked |
| **Q-002** *(Q-D02)* | Do Google's Gemini free-tier terms allow us to send real client project information to the API? | 20 Sep 2026 | Odina | HumbleBeeAI / instructors | All use of DS-01 | Not yet asked |
| **Q-003** *(Q-D03)* | Can HumbleBeeAI project information be stored in our public repository, or only described? | 20 Sep 2026 | Odina | HumbleBeeAI | What we can publish | Not yet asked |
| **Q-004** *(Q-D04)* | Are the Gemini free-tier rate limits sufficient for our testing, including repeated runs? | 20 Sep 2026 | Odina | Team — Abdulaziz to test | T-05 repeats | **Answered 31 Oct 2026: yes, so far.** Nine runs (3 inputs × 3 repeats) completed on the free tier with rate-limit retry built into `caseforge/llm.py`. Not tested at higher volume |
| **Q-005** *(Q-D05)* | How many classmate teams are willing to let us run their project through the tool? | 20 Sep 2026 | Odina | Classmates | B4, T-14, demo step 5 | Not yet asked |
| **Q-006** *(Q-T01)* | Is the provisional catch-rate target — 18 of 20 planted claims — the right bar for the automated checker? | 23 Sep 2026 | Odina | Team | T-05 | **Still not confirmed, and now urgent.** We have reported a result (20 of 20, in all three repeats) against a target the team never agreed. The number also needs a false-flag bar, not just a catch bar |
| **Q-007** *(Q-T02)* | How many test inputs do we need in total, beyond the three the Baseline requires? | 23 Sep 2026 | Odina | Team | Test coverage | Not decided |
| **Q-008** *(Q-T03)* | What goes on the brand-rules checklist, and whose brand do we follow? | 23 Sep 2026 | Odina | Team / pilot company | T2, T-12 | Not decided — Target item, not urgent |
| **Q-009** *(Q-T04)* | Who will be our outside user for the no-instruction test? | 23 Sep 2026 | Odina | Team | T4, T-14 | Not decided |
| **Q-010** *(Q-T05)* | Who writes the manual case study for the time comparison, and on which project? | 23 Sep 2026 | Odina | Team | T5, T-15 | Not decided |
| **Q-011** | What are the target dates for Baseline tasks BT-1 to BT-8? | 23 Oct 2026 | Team | Mukhammadkodir | All implementation | Not decided |
| **Q-012** | ReportLab or WeasyPrint for PDF generation? | 20 Sep 2026 | Abdulaziz | Abdulaziz | BT-6, B2 | **Decided 31 Oct 2026: ReportLab** — pure Python, installs with pip on Windows/Mac with no system libraries (WeasyPrint needs Pango/GTK); `KeepInFrame` lets the one-page summary shrink to fit |
| **Q-013** | Streamlit or a command-line interface for the Baseline? The container diagram currently says "Streamlit or CLI". | 23 Sep 2026 | Abdulaziz | Abdulaziz | BT-1, BT-5 | **Decided 31 Oct 2026: both** — Streamlit (`app.py`) for users and the demo, CLI (`python -m caseforge`) for tests and batch runs. They share the same pipeline code |
| **Q-014** | Is `module-python-template` the right starter template, given that the Baseline is a pipeline rather than a web service? | 23 Oct 2026 | Anvarbek | Abdulaziz | BT-1 | Proposed, awaiting confirmation |
| **Q-015** | Which Gemini model and version do we pin, so that results can be reproduced? | 23 Oct 2026 | Odina | Abdulaziz | Reproducibility, results log | **Decided 31 Oct 2026: `gemini-3.5-flash-lite`**, recorded in every entry of `tests/results.md` and in `eval/results/` |
| **Q-016** | What is our fallback if the Gemini free tier becomes unavailable or rate-limited during the demo? | 23 Oct 2026 | Anvarbek | Team, then instructors | Demo, BT-1 | Not decided — we must ask the instructors before considering any paid option |
| **Q-017** | Do the TA's suggestions — a Telegram bot and Notion integration — belong in Target, in Stretch, or outside the project? Neither is in the official project pool requirements. | 8 Oct 2026 | Anvarbek | Team / course TA | Scope after Baseline | Not decided |
| **Q-018** | Does the baseline measurement hold on a second tool and a second input? Our finding currently rests on one tool, one input, six runs and a single labeller. | 24 Oct 2026 | Anvarbek | Team | How strongly we can state our differentiation | Open — still one tool, one input, one labeller |
| **Q-019** | Our planted claims are invented numbers and tool names. ChatGPT's real failures were subtle inferences. Does the checker catch those too? | 4 Nov 2026 | Anvarbek | Abdulaziz | How much the 31 Oct result is worth | Open — test **T-05b**, due 16 Nov |
| **Q-020** | Who reviews the AI-assisted Baseline code, and when? Pull requests #15–#19 were opened and merged by their author, which our ground rules do not allow. | 4 Nov 2026 | Anvarbek | Muhammadkodir | Ground rules compliance | Open — review due 9 Nov |

---

## Decisions already made

Recorded here so that settled questions are not reopened without reason.

| Date | Decision | Where it is recorded |
|---|---|---|
| 20 Sep 2026 | The whole Baseline is completed before any Target work begins | [Definition of Done](definition-of-done.md) |
| 20 Sep 2026 | Nothing is ever published automatically; human approval is mandatory and permanent | [Definition of Done](definition-of-done.md), out of scope |
| 20 Sep 2026 | Google Gemini free tier only — no paid service without asking the instructors first | [Team Ground Rules](team-ground-rules.md) |
| 20 Sep 2026 | No client-confidential or internal company data, and no recordings or chat exports in the public repository | [Team Ground Rules](team-ground-rules.md), [Data Sources](data-sources.md) |
| 14 Oct 2026 | Our Core is faithfulness verification, not writing quality or distribution | Week 5 Worksheet 1; [Project Overview](project-overview.md#7-why-not-just-use-a-general-ai-tool) |
| 14 Oct 2026 | Beachhead market: small and mid-sized IT service and software companies in Seoul–Gyeonggi, roughly 10–200 employees | Week 3 and Week 5 business worksheets |
| 23 Oct 2026 | Build the smallest end-to-end path first — notes in, draft out, claim list — before any interface or PDF work | [Project Overview](project-overview.md#21-current-status-and-next-steps) |
| 23 Oct 2026 | Test results are recorded in `tests/results.md`; a test not recorded there is not counted as passed | [Test Plan](test-plan.md), [Definition of Done](definition-of-done.md) |
| 24 Oct 2026 | Differentiation claim revised, on the evidence of our own measurement: we no longer claim that general AI tools invent facts, but that they advise without enforcing | [Project Overview](project-overview.md#7-why-not-just-use-a-general-ai-tool), [Test Plan](test-plan.md) Section 3 Step 4 |
| 31 Oct 2026 | **Q-012** ReportLab, not WeasyPrint — pure Python, no system libraries needed on Windows or Mac | [README](../README.md#tools--models) |
| 31 Oct 2026 | **Q-013** Both Streamlit and a CLI, sharing one pipeline — Streamlit for users and the demo, CLI for tests and batch runs | [Container Diagram](c4-container.md) |
| 31 Oct 2026 | **Q-015** Model pinned to `gemini-3.5-flash-lite` | [`tests/results.md`](../tests/results.md) |
| 31 Oct 2026 | The checker runs as two layers — deterministic rules first, then an independent model pass — rather than one model call | [Container Diagram](c4-container.md), `caseforge/checker.py` |
| 4 Nov 2026 | A test counts only when it is in `tests/results.md`. Test source files are not evidence that a test passed | [Definition of Done](definition-of-done.md), [`tests/results.md`](../tests/results.md) |

---

## Questions for the instructors

To raise in the class Telegram group or at the next feedback session:

1. **Q-002** — whether sending real project information to an external AI service is acceptable for this course, and under what conditions.
2. **Q-016** — what we should do if the free tier cannot support the demo, since the ground rules require us to ask before considering anything paid.
3. **Q-017** — whether adding a Telegram bot and Notion integration is a sensible use of our remaining time, given that neither appears in the official requirements and the Baseline is not yet built.
