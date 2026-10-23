# CaseForge — S1: Case Study & Portfolio Generator

**Category:** Software / AI Workflow
**One-liner:** Companies do excellent work and then fail to sell it, because writing it up is nobody's job.
**Project tab:** [HBAI Capstone Project Pool](./docs/HBAI_Capstone_project_pools.pdf) — S1: Case Study & Portfolio Generator
**Status:** Midterm draft — design complete, implementation not yet started (last updated 23 October 2026)

> [!IMPORTANT]
> **No code has been written yet.** This repository currently contains documentation only. The Baseline is designed but not implemented. See [Project Status](#project-status).

## Team

Team 5 — Mukhammadkodir (PM), Abdulaziz (AI/Engineering), Dilshodjon (Problem & Business), Odina (Data & Research), Anvarbek (Demo & Presentation). Full role assignments in [Team Roles](./docs/team-roles.md).

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
| Given thin input | Fills the gap with a plausible figure | Flags the gap and refuses to invent one |
| Verification | None, or the model checking itself | A separate pass comparing each claim against the source |
| Approval | No concept of approval | Export blocked until every flag is resolved and a person approves |
| Memory | Forgets between conversations | Stores a project record and regenerates every format from it |
| Accuracy | Cannot be stated | Specified and tested: no unsupported claims on any test case |

A careful user with a good prompt can often get a general tool to avoid inventing facts. The difference is that here it is **guaranteed by the system, enforced before export, measured on every test case, and repeatable by someone who knows nothing about prompting**. Full comparison in the [Project Overview](./docs/project-overview.md#7-why-not-just-use-a-general-ai-tool).

We plan to show this rather than assert it: the same messy notes run through a general AI tool and through CaseForge, with every claim that was not in the input recorded for both. Method in [Test Plan](./docs/test-plan.md), Section 3, Step 4.

## Baseline Scope

From the official [Definition of Done](./docs/definition-of-done.md):

| | Requirement |
|---|---|
| **B1** | Accepts structured input: client problem, work done, technical approach, tools and technologies, challenges, results, supporting images |
| **B2** | Produces a one-page summary and a downloadable PDF case study on a fixed template |
| **B3** | A human review and edit step before anything is final — nothing publishes without approval |
| **B4** | Works end to end on three real project inputs |
| **B5** | Generates no claim that was not in the input, verified on every test case |

Target and Stretch items are listed separately in the [Definition of Done](./docs/definition-of-done.md) and will not be started before the Baseline is complete.

## Planned Features

- Structured input intake (client problem, work done, approach, tools, challenges, results, images)
- Extraction step that pulls only stated facts, flagging anything missing
- Writing step that formats verified facts into a fixed case study template
- Automated faithfulness check comparing every generated claim back to the source input
- Mandatory human review and edit step before anything is finalized
- Downloadable PDF case study and one-page summary *(Target: also a portfolio page and partner presentation)*

## Data Documentation

Full details, usage conditions and open questions in [Data Sources](./docs/data-sources.md).

| Source | Origin / URL | Usage conditions | Collected | Personal data | Preprocessing |
|---|---|---|---|---|---|
| HumbleBeeAI project information | HumbleBeeAI (via the project pool) | Only projects cleared for external sharing; no client-confidential or internal data | Not yet obtained — **TBD** | To be checked; client and employee names removed before use | Convert to text, label clean/messy, write a fact list |
| Team-constructed project information | Written by Team 5 | None — created by us | From October 2026, ongoing | None — invented company and people names | Same as above |
| Team's own project material | Team 5 | Used with all members' agreement; private details excluded | From September 2026 | Team member names only, by agreement | Same as above |
| Classmates' project material | Other course teams | Only with that team's permission; not published without agreement | Not yet obtained — **TBD** | Names removed or replaced unless the team asks otherwise | Same as above |

**External service transfer:** project text is sent to the Google Gemini API for processing. Only safe, cleared or team-constructed information is sent. Whether Google's free-tier terms permit sending real client project information is still open (**Q-002** in the [Question Log](./docs/question-log.md)).

**Not used, and never committed to this repository:** client confidential material, internal company data, personal information without permission, recordings or video of people, and exported community chat messages.

## Tools & Models

- **LLM:** Google Gemini (free tier via Google AI Studio) — no cost, no HBAI budget required. Model version to be pinned (**Q-015**).
- **PDF generation:** Python (ReportLab or WeasyPrint — choice open, **Q-012**)
- **Interface:** Streamlit or a command-line tool for the Baseline (**Q-013**)
- **Environment:** Local machine or Google Colab
- **Hardware:** A standard laptop. The model runs through an API, so no GPU is required.
- **Starter template:** [`module-python-template`](https://github.com/humblebeeai) — our Baseline is a Python processing pipeline (input → extraction → generation → check → export) rather than a web service, so the plain module template fits. If we add a web interface at Target stage we will reconsider `rest-fastapi-template`. To be confirmed (**Q-014**).

## AI Tool Use

Per the course documentation guide, we record our use of AI tools:

- **Documentation.** AI assistants were used to help draft and revise the documents in `docs/` and this README. Every document was read, edited and approved by a team member before being committed, and the content reflects the team's own decisions.
- **Code.** No code has been written yet. When it is, any AI-assisted code will be noted here, and reviewed and understood by a team member before use.
- **Verification.** Figures and sources cited in our documents — for example the Korean software industry statistics in our market analysis — were checked against the original sources by the team.

## Getting Started

> [!NOTE]
> There is nothing to run yet. These instructions describe the intended setup and will be completed once the first code lands.

```bash
git clone https://github.com/RainHardi/CaseForge.git
cd CaseForge
cp .env.example .env   # then fill in your own GEMINI_API_KEY
```

`requirements.txt`, run instructions and expected outputs will be added with the first working script (task **BT-1** in the [Project Overview](./docs/project-overview.md#21-current-status-and-next-steps)). A clean-clone run has **not** been verified yet.

API keys are never committed. Keys live in `.env`, which is excluded by `.gitignore`; `.env.example` holds blank placeholders.

## Project Status

**Complete:** problem definition, target market and personas, Definition of Done, C4 Level 1 and Level 2 diagrams, data sources, test plan, demo script, team roles and ground rules.

**Not started:** all implementation. No tests have been run, and `tests/results.md` does not exist yet.

**Next step:** build the smallest end-to-end path first — project notes in, a draft out, and a list of which claims appear in the input — before any interface or PDF work. Remaining Baseline tasks, with owners and completion criteria, are in the [Project Overview](./docs/project-overview.md#21-current-status-and-next-steps).

**Main risk:** implementation has not begun, and the hardest part — the faithfulness check — is the part the whole project depends on.

**Open questions:** 17, tracked in the [Question Log](./docs/question-log.md). The three most urgent concern permission to use real project data and target dates for the Baseline tasks.

## Project Docs

| Document | What it covers |
|---|---|
| [Project Overview](./docs/project-overview.md) | Problem, users, solution, scope, tools, current status and remaining tasks |
| [Definition of Done](./docs/definition-of-done.md) | Official Baseline, Target and Stretch requirements, and how each is verified |
| [Team Roles & Responsibilities](./docs/team-roles.md) | Who owns what, task status, contribution records |
| [Team Ground Rules](./docs/team-ground-rules.md) | How we work: meetings, scope, secrets, data, AI tool use, honesty |
| [System Context Diagram (C4 L1)](./docs/c4-context.md) | The system, its users, and the external services it uses |
| [Container Diagram (C4 L2)](./docs/c4-container.md) | The main parts inside the system and how they communicate |
| [Data Sources](./docs/data-sources.md) | Every data source, its conditions, collection dates and permissions |
| [Test Plan](./docs/test-plan.md) | What we test, how, what counts as success, and current test status |
| [Demo Script](./docs/demo-script.md) | The scenario we are building towards, and what we do if it fails |
| [Question Log](./docs/question-log.md) | Everything still undecided, and who can decide it |

---

> **The most important principle of the project: CaseForge should improve how project information is presented, without inventing what happened.**
