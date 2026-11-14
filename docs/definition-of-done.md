# Definition of Done

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator |
| **Repository** | CaseForge |
| **Team** | Team 5 |
| **Source** | [HBAI Capstone Project Pool](HBAI_Capstone_project_pools.pdf) — S1 |
| **Status** | Nothing complete — implementation not yet started |
| **Last Updated** | 23 October 2026 |

This document holds the official Baseline, Target and Stretch requirements for S1 as written in the project pool, together with how each one will be verified and where it currently stands.

## How we use this document

- An item is **done** only when the check in the "Verified by" column has actually been run and passed, and the result is recorded in `tests/results.md`. A feature that appears to work but has not been tested is not done.
- We complete the whole **Baseline** before starting Target work, and the whole Target before Stretch.
- Items are not reworded to make them easier. If we think a requirement needs interpreting, we record the question in the [Question Log](question-log.md) and ask.
- Test IDs refer to the [Test Plan](test-plan.md). Task IDs (BT-n) refer to the implementation tasks in the [Project Overview](project-overview.md#21-current-status-and-next-steps).

---

## Baseline

The minimum scope. All five items must be complete before any Target work begins.

| | Requirement | Verified by | Build task | Status |
|---|---|---|---|---|
| **B1** | Accepts structured input about a project: client problem, work done, technical approach, tools and technologies used, challenges, results, and supporting images | T-01 | BT-1 | Not started |
| **B2** | Produces a one-page summary and a downloadable PDF case study following a fixed template | T-03, T-08, T-09 | BT-6 | Not started |
| **B3** | A human review and edit step before anything is final. Nothing publishes without approval. | T-07 | BT-5 | Not started |
| **B4** | Works end to end on three real project inputs | T-10 | BT-7 | Not started |
| **B5** | Generates no claim that was not in the input, verified by checking output against input on every test case | T-02, T-04, T-05, T-06 | BT-3, BT-4, BT-8 | Not started |

### Notes on the Baseline items

- **B4** needs three *real* project inputs, not three variations of one invented example. Sourcing them is task **BT-2** and depends on permissions that have not yet been requested (**Q-D01**, **Q-D05** in [Data Sources](data-sources.md)).
- **B5** is the hardest requirement and the reason the project exists. It is not satisfied by the system producing good-looking output; it is satisfied only by checking every claim in every test case against the source and finding none that were invented. See [Test Plan](test-plan.md) Section 3.

---

## Target

Started only once every Baseline item is complete.

| | Requirement | Verified by | Status |
|---|---|---|---|
| **T1** | Multiple output formats from one project record: PDF case study, website portfolio page, one-page summary, partner-facing presentation | T-11 | Not started |
| **T2** | Brand rules applied and checkable: tone, structure, layout | T-12 | Not started |
| **T3** | Accepts messier input, such as rough notes or a pasted conversation, rather than requiring a clean form | T-13 | Not started |
| **T4** | Someone outside the team uses it successfully without instruction. We watch them do it and record what broke. | T-14 | Not started |
| **T5** | A business case: time to produce a case study manually versus with our tool, measured rather than estimated | T-15 | Not started |

### Proposed additions, not yet assigned to a tier

At the progress review on 8 October 2026 the course TA suggested a **Telegram bot** for chat-based input and **integration with tools such as Notion**. Both are input channels rather than new capabilities, and neither appears in the official project pool requirements. They are Target-level work at the earliest and will not begin before the Baseline is complete. Which tier they belong to, if any: **TBD**.

---

## Stretch

Optional. Attempted only if the Baseline and Target are complete and time remains.

| | Requirement | Verified by | Status |
|---|---|---|---|
| **S1** | Images placed sensibly within the document rather than appended at the end | T-16 | Not started |
| **S2** | Flags weak input, for example noting that no measurable result was provided | T-17 | Not started |
| **S3** | Batch generation across a set of projects | T-18 | Not started |
| **S4** | Output in more than one language | T-19 | Not started |

---

## Out of scope

These are deliberately excluded, and excluding them is a decision rather than a gap:

- **Automatic publishing.** Nothing is published without human approval. This is permanent, not a limitation of the current version — it is the point of B3.
- **Paid APIs or services.** We work within free tiers and ask the instructors before paying for anything.
- **Client confidential or internal company data.**
- **Training or fine-tuning our own model.** We use a hosted model through an API.
- **Guaranteeing that the underlying model never produces an unsupported claim.** We cannot control the model. What we control, and what B5 requires, is that such claims are detected and cannot reach a published document unchecked.

---

## Current status

> [!IMPORTANT]
> **No item in this document is complete.** The repository contains documentation only. No code has been written and no test has been run.

| Tier | Items | Complete |
|---|---|---|
| Baseline | 5 | 0 |
| Target | 5 | 0 |
| Stretch | 4 | 0 |

The remaining Baseline tasks, with owners and completion criteria, are in the [Project Overview](project-overview.md#21-current-status-and-next-steps). The first tests we will run are listed in [Test Plan](test-plan.md) Section 12.

---

## Related documents

- [Project Overview](project-overview.md) — scope, approach and current status
- [Test Plan](test-plan.md) — how each requirement is checked
- [Demo Script](demo-script.md) — what we will show
- [Data Sources](data-sources.md) — where the three real inputs for B4 will come from
- [Question Log](question-log.md) — what is still undecided
