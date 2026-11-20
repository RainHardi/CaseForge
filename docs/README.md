# CaseForge — S1: Case Study & Portfolio Generator

**Category:** Software / AI Workflow
**One-liner:** Companies do excellent work and then fail to sell it, because writing it up is nobody's job.
**Project tab:** [HBAI Capstone Project Pool](./HBAI_Capstone_project_pools.pdf) — S1: Case Study & Portfolio Generator
**Status:** Built and live at **https://caseforge-rcdu.onrender.com** — website with accounts, pipeline, checker, review step, PDF export, designed report, Notion import, Verified links, client sign-off, anonymized versions and a proof library, all working on team-constructed samples. Real-input runs (BT-7) and the two-person claim check (BT-8) still to do (last updated 20 November 2026)

> [!IMPORTANT]
> **To try it:** open **https://caseforge-rcdu.onrender.com** and sign up (made-up notes only, see Q-021), or run it locally — see [Getting Started](#getting-started).

## Team

Team 5 — Mukhammadkodir (PM), Abdulaziz (AI/Engineering), Dilshodjon (Problem & Business), Odina (Data & Research), Anvarbek (Demo & Presentation). Full role assignments in [Team Roles](./team-roles.md).

## The Problem

Services companies (starting with HumbleBeeAI) complete strong client work, but the write-up never happens — it's unbillable, belongs to no one, and requires gathering scattered information into a professional, consistent format. The result: an out-of-date portfolio and no polished case study to hand a prospective client, even though the work itself was done and paid for.

## Who Buys This

- **Primary:** Small and mid-sized IT service and software development companies in the Seoul–Gyeonggi area (roughly 10–200 employees) that win work by showing past projects. The **end user** is the developer or project lead asked to write the project up; the **buyer** is the business development lead or manager.
- **Secondary (our fastest real validation loop):** Ourselves and classmates. Students finish real work and have no polished artifact for job applications — we can test on our own and our classmates' projects, in-semester, with real users.

## Proposed Solution

A tool that maps messy, unstructured project input (rough notes, chat threads, screenshots) into a strict, professional, multi-format case study — PDF, one-page summary, and later a portfolio page and partner presentation — and **checks every claim in the output against what was actually provided**. A mandatory human review and approval step sits before anything is finalized or published.

```
Messy project input → Fact extraction → Case study writing → Faithfulness check → Human review → Final output
```

**The core engineering challenge:** preventing the model from inventing plausible-sounding but fabricated metrics (e.g. "reduced processing time by 40%") that were never in the source input.

## Why Not Just Use ChatGPT?

CaseForge runs on a general model (Google Gemini). We are not claiming a better model — the difference is what we build around it.

A general chat tool is built to produce text that **reads well**. CaseForge is built to produce text that can be **proven**.

| | General AI chat tool | CaseForge |
|---|---|---|
| Given thin input | May note what is missing, as advice the user can ignore | Flags it, and blocks export until it is resolved |
| Verification | None, or the model checking itself | A separate pass comparing each claim against the source |
| Approval | No concept of approval | Export blocked until every flag is resolved and a person approves |
| Memory | Forgets between conversations | Stores a project record and regenerates every format from it |
| Accuracy | Cannot be stated | Specified and tested: no unsupported claims on any test case |
| Proof for the reader | The reader has to trust the text | A Verified link: click any sentence and see the quote from the notes behind it |
| Client approval | By email, outside the tool | One link for the client to confirm, fix or remove each number and quote |

A careful user with a good prompt can often get a general tool to avoid inventing facts. The difference is that here it is **guaranteed by the system, enforced before export, measured on every test case, and repeatable by someone who knows nothing about prompting**. Full comparison in the [Project Overview](./project-overview.md#7-why-not-just-use-a-general-ai-tool).

**We measured this rather than asserting it, and the result changed our claim.** On 24 October 2026 we ran one messy project input through ChatGPT six times, under a natural request and under an explicit instruction not to invent detail. It invented no metrics, no client name and no false dates, and in every run it listed what the user should verify. What it did produce were unsupported inferences — four to six per run in normal use, including a backend/frontend split our notes never stated.

So we no longer claim that general AI tools invent facts. We claim that **they advise without enforcing**: nothing recorded the advice, nothing prevented publication without acting on it, the faithful version was unusable as a sales document, and three runs are not a guarantee about the fourth. Method and full results in [Test Plan](./test-plan.md), Section 3 Step 4 and Section 12.

## Baseline Scope

From the official [Definition of Done](./definition-of-done.md):

| | Requirement |
|---|---|
| **B1** | Accepts structured input: client problem, work done, technical approach, tools and technologies, challenges, results, supporting images |
| **B2** | Produces a one-page summary and a downloadable PDF case study on a fixed template |
| **B3** | A human review and edit step before anything is final — nothing publishes without approval |
| **B4** | Works end to end on three real project inputs |
| **B5** | Generates no claim that was not in the input, verified on every test case |

Target and Stretch items are listed separately in the [Definition of Done](./definition-of-done.md) and will not be started before the Baseline is complete.

## Planned Features

- Structured input intake (client problem, work done, approach, tools, challenges, results, images), uploaded files, pasted notes or a shared Notion page
- Extraction step that pulls only stated facts, flagging anything missing
- Writing step that formats verified facts into a fixed case study template
- Automated faithfulness check comparing every generated claim back to the source input
- Mandatory human review and edit step before anything is finalized
- Downloadable PDF case study and one-page summary *(Target: also a portfolio page and partner presentation)*
- Verified link: a public page and QR code where a reader checks each sentence against the notes and the approval
- Client sign-off: one link for the client to confirm, fix or remove each number and quote, and to say whether they may be named
- Anonymized version: only the names the team chooses are swapped, never a number
- Proof library: search approved case studies for a prospect and build a proof sheet quoting approved sentences only

## Data Documentation

Full details, usage conditions and open questions in [Data Sources](./data-sources.md).

| Source | Origin / URL | Usage conditions | Collected | Personal data | Preprocessing |
|---|---|---|---|---|---|
| HumbleBeeAI project information | HumbleBeeAI (via the project pool) | Only projects cleared for external sharing; no client-confidential or internal data | Not yet obtained — **TBD** | To be checked; client and employee names removed before use | Convert to text, label clean/messy, write a fact list |
| Team-constructed project information | Written by Team 5 | None — created by us | From October 2026, ongoing | None — invented company and people names | Same as above |
| Team's own project material | Team 5 | Used with all members' agreement; private details excluded | From September 2026 | Team member names only, by agreement | Same as above |
| Classmates' project material | Other course teams | Only with that team's permission; not published without agreement | Not yet obtained — **TBD** | Names removed or replaced unless the team asks otherwise | Same as above |

**Public pages:** a Verified link shows the approved sentences and, by default, the quotes behind them to anyone with the link; the owner can mask the quotes, show check results only, hide or anonymize the client, or unpublish. Client sign-off stores the name the client types. A Notion import uses the user's integration secret once and never stores it. Details in [Data Sources](./data-sources.md).

**External service transfer:** project text is sent to the Google Gemini API for processing. Only safe, cleared or team-constructed information is sent. Whether Google's free-tier terms permit sending real client project information is still open (**Q-002** in the [Question Log](./question-log.md)).

**Not used, and never committed to this repository:** client confidential material, internal company data, personal information without permission, recordings or video of people, and exported community chat messages.

## Tools & Models

- **LLM:** Google Gemini (free tier via Google AI Studio) — no cost, no HBAI budget required. Pinned to `gemini-3.5-flash-lite` (**Q-015**).
- **PDF generation:** ReportLab for the PDF case study and one-pager (**Q-012**); headless Chromium for the designed report and proof sheet; `segno` for QR codes
- **Interface:** FastAPI website; Streamlit and a command-line tool still work (**Q-013**)
- **Integrations:** Notion API, read only, with the user's own integration secret
- **Hosting:** Render + Neon, free tiers
- **Environment:** Local machine
- **Hardware:** A standard laptop. The model runs through an API, so no GPU is required.
- **Starter template:** [`module-python-template`](https://github.com/humblebeeai) — our Baseline is a Python processing pipeline (input → extraction → generation → check → export) rather than a web service, so the plain module template fits. Since CaseForge became a FastAPI web service as well, the code is laid out as its own package rather than from either template (**Q-014**, overtaken 14 Nov 2026).

## AI Tool Use

Per the course documentation guide, we record our use of AI tools:

- **Documentation.** AI assistants were used to help draft and revise the documents in `docs/` and this README. Every document was read, edited and approved by a team member before being committed, and the content reflects the team's own decisions.
- **Code.** The first implementation (`caseforge/`, `app.py`, `tests/`, `eval/`) and the later features (web app, designed report, Notion import, Verified links, client sign-off, anonymized version, proof library) were written with help from an AI assistant (Claude). Under our ground rules it is reviewed and understood by a team member before it is merged, and the reviewer is named in the pull request.
- **Verification.** Figures and sources cited in our documents — for example the Korean software industry statistics in our market analysis — were checked against the original sources by the team.

## Getting Started

Needs Python 3.11+ and a free Gemini API key from Google AI Studio (aistudio.google.com/apikey).

```bash
git clone https://github.com/RainHardi/CaseForge.git
cd CaseForge
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env  — add GEMINI_API_KEY and SECRET_KEY
python -m pytest                   # no API key needed
playwright install chromium        # once: renders the designed report to PDF
uvicorn web.main:app --reload      # website → http://localhost:8000
```

- **Website** (`web/`): landing page, accounts and team workspaces, upload → draft → check → approve → download, plus LinkedIn post, proposal paragraph and elevator pitch formats.
- **Designed report** (new): a 4–5 page branded report — big key numbers, process diagram, before/after chart — built only from the approved case study, checked again element by element, and locked until a person approves it. Brand kits (colours, fonts, logo, banned words) can be imported from a guidelines document. Two example kits: HumbleBeeAI and the fictional Northwind Digital Works.
- **Verified links, client sign-off, anonymized version** (on a project's Download tab), **Notion import** (on New case study) and the **proof library** (in the sidebar).
- **Share from your laptop** with Dev Tunnels, or **host for free** on Render + Neon: see [docs/DEPLOY.md](./DEPLOY.md).
- The first interface, `streamlit run app.py`, and the command line, `python -m caseforge --help`, still work and use the same pipeline.

Without a `GEMINI_API_KEY`, CaseForge runs in **offline mode**: no model is called and each sentence of the draft is a sentence from your notes.

API keys are never committed. Keys live in `.env`, which is excluded by `.gitignore`.

## Project Status

**Complete:** problem definition, target market and personas, Definition of Done, C4 diagrams, data sources, test plan, demo script, team roles and ground rules — and the Baseline implementation:

| Task | What exists | Where |
|---|---|---|
| BT-1 | Code structure, `requirements.txt`, Gemini client with JSON-schema output and rate-limit retry | `caseforge/llm.py`, `caseforge/config.py` |
| BT-3 | Fact extraction; every fact must quote the input, and facts whose quote is not found are dropped | `caseforge/extract.py` |
| BT-4 | Two-layer faithfulness checker (deterministic rules + an independent model pass); planted-claim test | `caseforge/checker.py`, `eval/planted_claims.py` |
| BT-5 | Review: edit, delete, add, add-to-source, gap acknowledgement, approve/reject; export locked until approved. Input by upload (PDF, Word, Excel, PowerPoint, text, images) or pasted notes | `caseforge/review.py`, `caseforge/ingest.py`, `app.py`, `caseforge/cli.py` |
| BT-6 | PDF case study, one-page summary (always one page), portfolio web page | `caseforge/render/` |

**Mentor feedback round (Nov 2026) — publishable reports:**

| What the mentor asked | What CaseForge does now | Where |
|---|---|---|
| Professional design, big numbers, real visuals, consistent brand | HTML/CSS report rendered by Chromium; brand kit drives colours, fonts (bundled, open licence), motif, logo; contrast rule keeps pale colours off text | `caseforge/report.py`, `caseforge/render/report_pdf.py`, `caseforge/brandkit.py`, `brands/` |
| Layout that fits the content, not one template | The notes decide the story (impact, before→after, timeline, quote-led, method-led), the cover, the page order and each block's shape; the reasons are shown to the reviewer | `caseforge/layout.py` |
| Short copy, each fact once, nothing left out | Standard case-study structure; pages grow with the notes; every approved sentence is on a designed page or in the Project facts table (coverage shown); length budgets per element; warning when the same number appears twice | `report.check_report`, `layout.compose`, `report.report_warnings` |
| Faithful; estimates stay labelled | Every report element re-checked; "estimate" wording in notes must survive; conflicting numbers become a blocking question; each fact shows file and line | `textutil.estimate_flags`, `extract.conflicts_from`, `gaps.py` |
| Human approves | Separate approval for the designed report, locked by a content hash | `report.approve_report` |
| Huge messy input + brand rules | Notes read in parts and merged; guideline documents imported into a brand kit | `extract.chunks`, `brandkit.from_guidelines` |
| A reason to choose this over a chatbot | Verified link with QR code, client sign-off, anonymized version, proof library, Notion import | `verify.py`, `signoff.py`, `anonymize.py`, `library.py`, `notion.py` |

**Measured:** the planted-claim test has been run with Gemini as well as offline. On 31 October 2026, `gemini-3.5-flash-lite`, 3 team-constructed inputs × 3 repeats: **all 20 planted errors caught in every repeat (60 of 60 observations), and no false flags on 109 genuine sentences.** Full log: [`tests/results.md`](../tests/results.md); raw output in `eval/results/`.

**Automated suite:** 114 tests pass offline (20 November 2026, author's run).

**Live:** the website runs at **https://caseforge-rcdu.onrender.com** (Render + Neon Postgres). Setup in [docs/DEPLOY.md](./DEPLOY.md). Auto-deploy from GitHub stopped working after 17 November, so deploys are manual for now (**Q-024**).

**Not done yet:** BT-2 three *real* project inputs, and the BT-7/BT-8 runs on them with the two-person claim check; the partner presentation format (Target); the outside-user test and time comparison (T4, T5); batch generation and multi-language output (Stretch).

**Main risk:** every number above comes from notes we wrote ourselves, where the planted errors are short and obvious. Nothing has been run on a real client project, and the checker has not been tested against the subtle, inference-style claims a general model actually produces. That is the next measurement that matters.

**Open questions:** tracked in the [Question Log](./question-log.md). Q-012 (ReportLab), Q-013 (Streamlit, CLI and now a web app) and Q-015 (model pinned to `gemini-3.5-flash-lite`) are decided; Q-017 is answered (Notion import built, no Telegram).

## Project Docs

| Document | What it covers |
|---|---|
| [Project Overview](./project-overview.md) | Problem, users, solution, scope, tools, current status and remaining tasks |
| [Definition of Done](./definition-of-done.md) | Official Baseline, Target and Stretch requirements, and how each is verified |
| [Team Roles & Responsibilities](./team-roles.md) | Who owns what, task status, contribution records |
| [Team Ground Rules](./team-ground-rules.md) | How we work: meetings, scope, secrets, data, AI tool use, honesty |
| [System Context Diagram (C4 L1)](./c4-context.md) | The system, its users, and the external services it uses |
| [Container Diagram (C4 L2)](./c4-container.md) | The main parts inside the system and how they communicate |
| [Data Sources](./data-sources.md) | Every data source, its conditions, collection dates and permissions |
| [Test Plan](./test-plan.md) | What we test, how, what counts as success, and current test status |
| [Demo Script](./demo-script.md) | The scenario we are building towards, and what we do if it fails |
| [Question Log](./question-log.md) | Everything still undecided, and who can decide it |

---

> **The most important principle of the project: CaseForge should improve how project information is presented, without inventing what happened.**
