# S1: Case Study & Portfolio Generator

**Category:** Software / AI Workflow
**One-liner:** Companies do excellent work and then fail to sell it, because writing it up is nobody's job.

## Team

Team 5 — Mukhammadkodir (PM), Abdulaziz (AI/Engineering), Dilshodjon (Problem & Business), Odina (Data & Research), Anvarbek (Demo & Presentation). Full role assignments in [Team Roles](./docs/team-roles.md).

## The Problem

Services companies (starting with HumbleBeeAI) complete strong client work, but the write-up never happens — it's unbillable, belongs to no one, and requires gathering scattered info into a professional, consistent format. The result: an out-of-date portfolio and no polished case study to hand a prospective client, even though the work itself was done and paid for.

## Who Buys This

- **Primary:** Services companies that sell based on past work (starting with HumbleBeeAI, across AI dev, R&D, cybersecurity, data science, software engineering). Buyer = business development/marketing owner.
- **Secondary (our fastest real validation loop):** Ourselves and classmates. Every capstone team finishes with a project and no polished artifact for job applications — we can test this on our own capstone and our classmates', in-semester, with real users.

## Proposed Solution

A tool that maps messy, unstructured project input (rough notes, chat threads, screenshots) into a strict, professional, multi-format case study — PDF, portfolio page, one-pager, partner presentation — while guaranteeing every claim is faithful to what was actually provided. A mandatory human review/approval step sits before anything is finalized or published.

**The core engineering challenge:** preventing the model from inventing plausible-sounding but fabricated metrics (e.g., "reduced processing time by 40%") that were never in the source input.

## Planned Features

- Structured input intake (client problem, work done, approach, tools, challenges, results, images)
- Extraction step that pulls only stated facts, flagging anything missing
- Writing step that formats verified facts into a fixed case study template
- Automated faithfulness check comparing every generated claim back to source input
- Mandatory human review/edit step before anything is finalized
- Downloadable PDF case study (Target: also a portfolio page, one-pager, and partner presentation)

## Data Path

- HumbleBeeAI project information cleared for external sharing, or project info the team constructs itself
- Team's own and classmates' capstone projects, **with permission**
- **No client confidential material, no internal company data**
- Deliberately collect poor/messy inputs early — a system that only handles well-written input hasn't solved the actual problem

## Tools & Models

- **LLM:** Google Gemini (free tier via AI Studio) — no cost, no HBAI budget required
- **PDF generation:** Python (reportlab / weasyprint)
- **Environment:** Local machine or Google Colab for development

## Getting Started

```bash
git clone <this-repo-url>
cd <repo-name>
cp .env.example .env   # then fill in your own GEMINI_API_KEY
pip install -r requirements.txt
```
*(requirements.txt and run instructions will be added as the build progresses — see [Question Log](./docs/question-log.md) for open setup questions.)*

## Project Docs

- [Team Roles & Responsibilities](./docs/team-roles.md)
- [Project Overview](./docs/project-overview.md)
- [Team Ground Rules](./docs/team-ground-rules.md)
- [Question Log](./docs/question-log.md)
- [System Context Diagram (C4 L1)](./docs/c4-context.md)
- [Container Diagram (C4 L2)](./docs/c4-container.md)
- [Data Sources](./docs/data-sources.md)
- [Test Plan](./docs/test-plan.md)
- [Definition of Done](./docs/definition-of-done.md)
- [Demo Script](./docs/demo-script.md)

## Status

Initial draft stage. Details marked TBD in the linked docs are still being resolved with the team and course instructors — see the [Question Log](./docs/question-log.md) for what's currently open.
