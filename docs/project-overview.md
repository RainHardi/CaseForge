# Project Overview

## Case Study & Portfolio Generator (S1)

| | |
|---|---|
| **Category** | Software / AI Workflow |
| **Project Tab** | [HBAI Capstone Project Pool](HBAI_Capstone_project_pools.pdf) — S1: Case Study & Portfolio Generator |
| **Repository** | [CaseForge](https://github.com/RainHardi/CaseForge) |
| **Team** | Team 5 |
| **Development Period** | Fall 2026 Semester |
| **Status** | Midterm draft — design complete, implementation not yet started |
| **Last Updated** | 24 October 2026 |

---

## Table of Contents

1. [Project Name](#1-project-name)
2. [Problem](#2-problem)
3. [Target Users](#3-target-users)
4. [How Users Currently Solve the Problem](#4-how-users-currently-solve-the-problem)
5. [Proposed Solution](#5-proposed-solution)
6. [Why AI](#6-why-ai)
7. [Why Not Just Use a General AI Tool](#7-why-not-just-use-a-general-ai-tool)
8. [Inputs and Outputs](#8-inputs-and-outputs)
9. [Planned Core Features](#9-planned-core-features)
10. [Development Plan](#10-development-plan)
11. [Baseline](#11-baseline)
12. [Target](#12-target)
13. [Stretch](#13-stretch)
14. [What We Will Leave Out](#14-what-we-will-leave-out)
15. [Data Sources](#15-data-sources)
16. [Tools, Models, and Hardware](#16-tools-models-and-hardware)
17. [Technical Difficulties to Investigate First](#17-technical-difficulties-to-investigate-first)
18. [Testing and Evaluation](#18-testing-and-evaluation)
19. [Expected Final Result](#19-expected-final-result)
20. [Expected Value](#20-expected-value)
21. [Current Status and Next Steps](#21-current-status-and-next-steps)
22. [Project Documentation](#22-project-documentation)
23. [References](#23-references)

---

## 1. Project Name

**S1 - Case Study & Portfolio Generator**

The project repository is called **CaseForge**.

## 2. Problem

Companies can complete strong projects but often fail to present this work clearly after the project is finished.

For service companies, writing a professional case study can be difficult because project information may be spread across rough notes, messages, screenshots, documents, and other sources. Writing the case study is also usually not a direct part of the project work, so nobody may have clear responsibility for doing it.

As a result, companies may have:

- Old or incomplete portfolio information
- No professional case study for completed projects
- Difficulty collecting project information
- Inconsistent writing and formatting
- A large amount of time spent preparing project materials manually

The initial business context for this project is **HumbleBeeAI**, which works in areas such as AI development, R&D, cybersecurity, data science, and software engineering.

## 3. Target Users

### Primary Users

The primary users are service companies that sell their work based on previous projects and results, such as agencies, consultancies, development shops, and research firms.

Our beachhead market is small and mid-sized IT service and software development companies in the Seoul–Gyeonggi area, roughly 10–200 employees, that win client work by showing past projects.

The **end user** is the developer or project lead who is asked to write up a finished project. The **buyer** is the business development lead or manager who approves the purchase. They need to turn completed project information into professional materials that present the company's previous work.

### Secondary Users

A faster validation group will be our own team and our classmates.

Students often complete projects but do not have a polished case study or portfolio artifact that can be used for job applications. Because we can run our own and our classmates' projects through CaseForge during the semester, this group gives us the fastest real user feedback.

## 4. How Users Currently Solve the Problem

Currently, users collect information manually from different sources and write the case study themselves.

A typical process includes:

1. Finding project information.
2. Collecting notes, messages, screenshots, and other materials.
3. Selecting useful information.
4. Writing the case study.
5. Checking the information.
6. Formatting the document.
7. Creating a final PDF or presentation.

Because this takes hours and is not billable work, it is often skipped. When a prospective client asks about similar past work, someone puts something together in a hurry, or nothing is sent at all.

## 5. Proposed Solution

The team proposes an AI-based Case Study & Portfolio Generator.

The system will take messy and unstructured project information and transform it into a structured professional case study.

The planned workflow is:

```
Messy project input → Fact extraction → Case study writing → Faithfulness check → Human review → Final output
```

The system will first identify information that is actually stated in the source material. It will then use these facts to create a professional case study, and check every claim in the draft against the original input.

> [!IMPORTANT]
> A key requirement is that the system **must not invent information**. For example, if the source material does not contain a specific performance improvement, the system should not create a statement such as: *"The system reduced processing time by 40%."* Instead, missing information should be flagged for human review. A human must review and approve the generated content before it is finalized or published.

## 6. Why AI

A fixed template alone cannot solve this problem, because the input never arrives in template shape. It comes as rough notes, chat threads, screenshots, or whatever the engineer remembers.

AI can help by:

- Understanding unstructured project information
- Extracting important facts
- Organizing information into a fixed structure
- Generating professional written content
- Checking generated claims against the original information
- Identifying information that is missing or unsupported

The hard requirement is **accuracy, not fluency**. The project focuses on controlled AI generation, rather than simply asking an AI model to write a case study.

## 7. Why Not Just Use a General AI Tool

CaseForge runs on a general model (Google Gemini). We are not claiming a better model, and we could not build one. The difference is what we build **around** the model.

A general chat tool such as ChatGPT, Claude or Gemini is built to produce text that reads well. CaseForge is built to produce text that can be **proven**. Those are different objectives, and the second one requires a system, not a better prompt.

| | General AI chat tool | CaseForge |
|---|---|---|
| **Objective** | Produce fluent, helpful text | Produce text in which every claim is traceable to the input |
| **Given thin input** | May note what is missing, as advice the user is free to ignore | Flags it, and blocks export until the flag is resolved |
| **Verification** | None by default, or the model checking its own output in the same response | A separate pass that compares each claim against the stored source and labels it supported, reworded, unsupported, or contradicted |
| **Approval** | No concept of approval | Export is disabled until every flag is resolved and a person approves |
| **Memory** | Forgets between conversations | Stores a structured project record and regenerates every format from it |
| **Consistency** | A different story each time you ask | PDF, one-page summary and portfolio page all built from the same record |
| **Measurable accuracy** | Cannot be stated | Specified and tested: no unsupported claims across every test case (see [Test Plan](test-plan.md)) |
| **Fits the workflow** | The user must know how to prompt | Structured intake, fixed template, company's own house style |

> [!NOTE]
> To be precise about the claim: a careful user with a good prompt can often get a general tool to avoid inventing facts. The difference is that in CaseForge this is **guaranteed by the system, enforced before export, measured on every test case, and repeatable by a user who knows nothing about prompting**. We are not competing with the model. We are competing with the absence of verification around it.

### What we measured

We tested this rather than asserting it. On 24 October 2026 we gave one team-constructed project input to ChatGPT under two conditions — a natural request for a case study, and the same request with an explicit instruction not to invent detail — three runs each. The method and full results are in [Test Plan](test-plan.md), Section 3 Step 4 and Section 12.

**The result did not match our expectation, and we have changed what we claim because of it.** ChatGPT invented no performance metrics, no client name and no false dates in any of the six runs, and in every run it volunteered a list of details the user should verify before publishing. What it did produce consistently were unsupported inferences — in all three runs of the natural condition it stated that Python was used for the backend and React for the frontend, which our notes never said.

We no longer claim that general AI tools invent facts. The defensible claim, supported by what we observed, is:

1. **It advises, it does not enforce.** The tool told the user what to verify, but nothing recorded that advice, and nothing prevented the document being published without acting on it.
2. **Unsupported inferences still appeared**, at roughly four to six per run in normal use, in the form hardest to notice — plausible, probably true, and never actually stated.
3. **Faithfulness cost usability.** Under the constrained condition the output stated in the document itself that the client's name and results "were not provided in the available notes" — accurate, and unsendable. The user also had to know to ask for that condition.
4. **Three runs are not consistency.** A specification such as "zero unsupported claims on every test case" can be stated and tested for our system. It cannot be stated for a chat tool.

Our design addresses exactly that gap: generate the usable prose, then flag the unsupported parts separately, rather than degrading the prose in order to stay safe.

## 8. Inputs and Outputs

### Inputs

- Client problem
- Work completed
- Technical approach
- Tools and technologies
- Challenges
- Results
- Supporting images
- Rough notes or pasted conversations (Target)

We will deliberately test the system with poor and messy inputs. A system that only works with clean and well-written information has not solved the problem.

### Outputs

**Baseline:**

- A downloadable **PDF case study** following a fixed template
- A **one-page summary**

**Target (from the same project record):**

- Website portfolio page
- Partner-facing presentation

Every output should contain only information that is supported by the provided project information.

## 9. Planned Core Features

### Feature 1 - Structured Input Intake

The system will collect information about the client problem, work completed, approach, tools and technologies, challenges, results, and images.

### Feature 2 - Fact Extraction

The system will extract only facts that are stated in the input. If important information is missing, the system will flag it instead of creating unsupported information.

### Feature 3 - Case Study Generation

The extracted facts will be organized into a fixed case-study structure and converted into professional written content.

### Feature 4 - Automated Faithfulness Check

The system will compare generated claims with the original project information and flag claims that are not supported by the source.

### Feature 5 - Human Review

A human must review, edit, and approve the generated content before it is finalized. Nothing is published without approval.

### Feature 6 - PDF Case Study and One-Page Summary

The approved content will be exported as a downloadable PDF case study and a one-page summary.

## 10. Development Plan

We will get the full Baseline working before moving on to Target, and leave Stretch items until every Baseline item is complete.

1. Define the project structure and user workflow.
2. Collect safe project information and test examples, including messy inputs.
3. Build the input and fact extraction process.
4. Build the faithfulness check early, alongside generation rather than at the end.
5. Build the case-study generation process.
6. Add human review and editing.
7. Generate the PDF case study and one-page summary.
8. Test end to end on three real project inputs.
9. Record errors and limitations, and improve the system based on test results.
10. Move on to Target features.
11. Prepare the final demonstration and presentation.

## 11. Baseline

These are the official Baseline items from the project tab, and how we plan to meet each one.

| # | Baseline Item | Our Plan |
|---|---|---|
| B1 | Accepts structured input about a project: client problem, work done, technical approach, tools and technologies used, challenges, results, and supporting images | Input form covering each field, with image upload |
| B2 | Produces a one-page summary and a downloadable PDF case study following a fixed template | Fixed case-study template; PDF generation with ReportLab or WeasyPrint (choice TBD) |
| B3 | A human review and edit step before anything is final; nothing publishes without approval | Review screen where the user edits and approves the draft; export only works after approval |
| B4 | Works end to end on three real project inputs | Test with real inputs from our own projects, classmates' projects, and HumbleBeeAI projects if cleared |
| B5 | Generates no claim that was not in the input, verified by checking output against input on every test case | Fact extraction + automated faithfulness check + manual claim check on every test case (see [Test Plan](test-plan.md)) |

## 12. Target

After the Baseline is complete, we will work on the official Target items:

| # | Target Item |
|---|---|
| T1 | Multiple output formats from one project record: PDF case study, website portfolio page, one-page summary, partner-facing presentation |
| T2 | Brand rules applied and checkable: tone, structure, layout |
| T3 | Accepts messier input, such as rough notes or a pasted conversation, rather than requiring a clean form |
| T4 | Someone outside our team uses it successfully without instruction. We watch them use it and record what broke |
| T5 | A business case: time to produce a case study manually versus with our tool, measured rather than estimated |

### Proposed additions under consideration

At the progress review on 8 October 2026, the course TA suggested two additions: a **Telegram bot** so users can send project notes and receive a draft inside a chat, and **integration with tools such as Notion** so project information can be pulled from where teams already keep it.

Both are input channels rather than new capabilities, and neither appears in the official Definition of Done. We consider them Target-level work at the earliest, and they will not be started before the Baseline is complete. Which tier they belong to: **TBD**.

## 13. Stretch

If time allows after the Target is complete:

| # | Stretch Item |
|---|---|
| S1 | Images placed sensibly within the document rather than appended at the end |
| S2 | Flags weak input, for example noting that no measurable result was provided |
| S3 | Batch generation across a set of projects |
| S4 | Output in more than one language |

## 14. What We Will Leave Out

To keep the Baseline on track, the following are out of scope for now:

- **Automatic publishing.** Content is never published without human approval. This is a permanent design decision, not a temporary limitation.
- **Paid APIs or services.** We will use free tiers and ask the instructors before paying for anything.
- **Client confidential or internal company data.**
- **Training or fine-tuning our own model.** We use a hosted model through an API.
- **Stretch features** until every Baseline and Target item works.
- Which Stretch features we attempt, if any: **TBD**, depending on progress.

## 15. Data Sources

| Source | Access Status |
|---|---|
| HumbleBeeAI projects cleared for external sharing | TBD, not yet requested |
| Project information constructed by our team (clean and messy) | Available |
| Our own project material | Available |
| Classmates' project material (with permission) | TBD, permission needed |

We will not use client confidential material, internal company data, or protected information. Full details, usage conditions, collection dates and open questions are in [Data Sources](data-sources.md).

## 16. Tools, Models, and Hardware

| Area | Tool | Notes |
|---|---|---|
| **AI Model** | Google Gemini (via Google AI Studio) | Free tier, so no project budget is needed. Rate limits to be tested. |
| **Programming** | Python | Main workflow and supporting components |
| **PDF Generation** | ReportLab or WeasyPrint | Final choice TBD |
| **Development Environment** | Local machine or Google Colab | |
| **Hardware** | Standard laptop | The model runs through an API, so no GPU is needed |

> [!NOTE]
> API keys will never be placed in the public repository. Keys are stored in a `.env` file excluded from Git, and the repository includes a `.env.example` with blank values.

## 17. Technical Difficulties to Investigate First

These come from the project tab's Known Hard Parts, in the order we plan to investigate them:

1. **Keeping generated text faithful to the input.** This is the central difficulty. Invented metrics and plausible-sounding claims are hard to spot precisely because the writing is good, so we will build a way to check this from the beginning, not at the end.
2. **Consistent structured output.** The model's output must be parseable and correctly shaped every time, not most of the time.
3. **Layout that survives variable input length.** A two-sentence project and a three-page project must both produce a well-formatted document.
4. **Brand rules are harder to enforce than to state.** Tone and voice are easy to describe but hard to verify automatically. We will decide early how we will check them (Target).

## 18. Testing and Evaluation

We will test with both clean and messy project inputs. The main evaluation areas are:

| # | Evaluation Area | Description |
|---|---|---|
| 1 | **Claim Faithfulness** | No unsupported or contradicted claims in the final output, on every test case |
| 2 | **Handling Missing Information** | Gaps are flagged instead of filled in |
| 3 | **Output Quality** | Clear structure and professional writing that follows the template |
| 4 | **Human Review** | Users can edit and approve content before anything is final |
| 5 | **Final Output** | PDF case study and one-page summary are generated correctly |
| 6 | **Usability and Time Saved** (Target) | Outside user test and measured time comparison |

The full plan, including test cases and success criteria, is in [Test Plan](test-plan.md).

**No tests have been run yet**, because implementation has not started. See [Section 21](#21-current-status-and-next-steps).

## 19. Expected Final Result

By the end of the semester, we aim to demonstrate a working Case Study & Portfolio Generator that runs the complete workflow:

```
Raw project information → Fact extraction → Case study generation → Faithfulness check → Human review → PDF case study + one-page summary
```

The final demo will include running a classmate's project through the tool and showing the review step catching and correcting an unsupported claim.

## 20. Expected Value

For service companies, CaseForge can reduce the manual effort needed to turn completed projects into professional case studies:

- Faster creation of portfolio materials
- More consistent case-study structure
- Better reuse of completed project information
- Something ready to send when a prospective client asks
- Reduced risk of false claims in client-facing documents

For students, it can turn completed projects into portfolio materials for job applications.

## 21. Current Status and Next Steps

### What is complete

The design and planning stage is complete. The following are written and in the repository:

- Project overview (this document), team roles, team ground rules
- Definition of Done, aligned with the official Baseline, Target and Stretch
- C4 Level 1 System Context and Level 2 Container diagrams
- Data sources with usage conditions and open questions
- Test plan with test cases and success criteria
- Demo script

### What has not started

> [!IMPORTANT]
> **No code has been written and no tests have been run.** The repository currently contains documentation only. The Baseline is designed but not implemented.

### Remaining Baseline tasks

| ID | Task | Owner | Done when | Date |
|---|---|---|---|---|
| BT-1 | Set up the code structure, `requirements.txt`, and a working Gemini API call | Abdulaziz | A script sends project notes to Gemini and prints a structured draft | TBD |
| BT-2 | Prepare three real project inputs with hand-written fact lists | Odina | Three inputs and their fact lists are committed to the repository | TBD |
| BT-3 | Fact extraction step | Abdulaziz | Extracted facts match the hand-written fact list for each test input | TBD |
| BT-4 | Automated faithfulness check | Abdulaziz | Each generated claim is labelled supported, reworded, unsupported or contradicted; catch rate measured on the planted-claim test | TBD |
| BT-5 | Human review and approval step | Abdulaziz | Draft can be edited, approved or rejected; export is blocked until approval | TBD |
| BT-6 | PDF case study and one-page summary | Abdulaziz | Both open correctly and match the approved text | TBD |
| BT-7 | End-to-end run on three real inputs | Team | All three produce an approved PDF with no unsupported claims | TBD |
| BT-8 | Manual claim check on every test case | Odina, plus one reviewer | Every case study checked by two people and recorded in the results log | TBD |

Dates are TBD until the team agrees a schedule. Responsibilities are in [Team Roles](team-roles.md).

### Main risk and next action

The main risk to completing the Baseline is that implementation has not begun and the hardest part, the faithfulness check, is also the part the whole project depends on.

To reduce it, we will build the smallest end-to-end path first — project notes in, a draft out, and a list of which claims appear in the input — before building any interface or PDF output. That path proves the idea works and can be tested immediately, and everything else is formatting around it.

Details that are still undecided are marked **TBD** and tracked in the [Question Log](question-log.md).

## 22. Project Documentation

- [README](../README.md)
- [Team Roles & Responsibilities](team-roles.md)
- [Project Overview](project-overview.md)
- [Team Ground Rules](team-ground-rules.md)
- [Question Log](question-log.md)
- [System Context Diagram (C4 Level 1)](c4-context.md)
- [Container Diagram (C4 Level 2)](c4-container.md)
- [Data Sources](data-sources.md)
- [Test Plan](test-plan.md)
- [Definition of Done](definition-of-done.md)
- [Demo Script](demo-script.md)

## 23. References

- HumbleBeeAI, *HBAI Capstone Project Pool*, S1: Case Study & Portfolio Generator ([project tab](HBAI_Capstone_project_pools.pdf))
- Victoria Kim and Seunghyun Ko, *Inha Capstone Project Documentation Guide*, Capstone Design Course, Inha University, Fall 2026
- Google AI Studio / Gemini API documentation (link TBD)
- ReportLab and WeasyPrint documentation (link TBD, once the library is chosen)

---

> **The most important principle of the project: CaseForge should improve how project information is presented, without inventing what happened.**
