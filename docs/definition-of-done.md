# Definition of Done

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator |
| **Repository** | CaseForge |
| **Team** | Team 5 |
| **Source** | [HBAI Capstone Project Pool](HBAI_Capstone_project_pools.pdf) — S1 |
| **Status** | Baseline and most Target work built, deployed and tested on team-constructed inputs; B4 real-input runs outstanding |
| **Last Updated** | 20 November 2026 |

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
| **B1** | Accepts structured input about a project: client problem, work done, technical approach, tools and technologies used, challenges, results, and supporting images | T-01 | BT-1 | **Built** — web upload of PDF, Word, Excel, PowerPoint, text and images, or pasted notes; `tests/test_ingest.py`, `tests/test_web.py` |
| **B2** | Produces a one-page summary and a downloadable PDF case study following a fixed template | T-03, T-08, T-09 | BT-6 | **Built** — PDF case study and a one-pager that is one page for a 1-sentence and a 400-sentence input, plus a designed 4–5 page branded report; `tests/test_review_export.py`, `tests/test_report.py` |
| **B3** | A human review and edit step before anything is final. Nothing publishes without approval. | T-07 | BT-5 | **Built** — export refused before approval; any edit after approval withdraws it; the designed report carries its own approval locked by a content hash; `tests/test_review_export.py`, `tests/test_report.py` |
| **B4** | Works end to end on three real project inputs | T-10 | BT-7 | **Not started** — the three samples are team-constructed, not real. Blocked on BT-2 and on permission (Q-001, Q-005) |
| **B5** | Generates no claim that was not in the input, verified by checking output against input on every test case | T-02, T-04, T-05, T-06 | BT-3, BT-4, BT-8 | **Partly verified** — T-05 measured 31 Oct (20 planted claims caught in all 3 repeats, 0/109 false flags) on team-constructed inputs. T-02, T-04 and T-06 not run |

### Notes on the Baseline items

- **B4** needs three *real* project inputs, not three variations of one invented example. Sourcing them is task **BT-2** and depends on permissions that have not yet been requested (**Q-D01**, **Q-D05** in [Data Sources](data-sources.md)).
- **B5** is the hardest requirement and the reason the project exists. It is not satisfied by the system producing good-looking output; it is satisfied only by checking every claim in every test case against the source and finding none that were invented. See [Test Plan](test-plan.md) Section 3.

---

## Target

Started only once every Baseline item is complete.

| | Requirement | Verified by | Status |
|---|---|---|---|
| **T1** | Multiple output formats from one project record: PDF case study, website portfolio page, one-page summary, partner-facing presentation | T-11 | **Built, one format short** — PDF case study, one-pager, portfolio page, designed 4–5 page report, LinkedIn post, proposal paragraph and elevator pitch all generate from one record (`caseforge/render/`, `caseforge/formats.py`). A partner-facing presentation is the only format still missing |
| **T2** | Brand rules applied and checkable: tone, structure, layout | T-12 | **Built** — brand kits carry colours, fonts, logo, motif and banned words, and can be imported from a guidelines document (`caseforge/brandkit.py`, `brands/`); a contrast rule keeps pale brand colours off text. Two kits exist: HumbleBeeAI and the fictional Northwind. Still ours rather than a pilot company's (Q-008) |
| **T3** | Accepts messier input, such as rough notes or a pasted conversation, rather than requiring a clean form | T-13 | **Built** — rough notes, pasted chat and uploaded office documents all run end to end; long notes are read in parts and merged (`extract.chunks`). Covered by `tests/test_ingest.py` |
| **T4** | Someone outside the team uses it successfully without instruction. We watch them do it and record what broke. | T-14 | Not started |
| **T5** | A business case: time to produce a case study manually versus with our tool, measured rather than estimated | T-15 | Not started |

### Proposed additions, not yet assigned to a tier

At the progress review on 8 October 2026 the course TA suggested a **Telegram bot** for chat-based input and **integration with tools such as Notion**. Both are input channels rather than new capabilities, and neither appears in the official project pool requirements. A **Notion page import** was built on 20 November 2026; the Telegram bot will not be built.

Also built on 20 November 2026, outside the official requirements: a **Verified link** with QR code, **client sign-off**, an **anonymized version** and a **proof library**. They are covered by automated tests only, and they do not make any Baseline, Target or Stretch item complete. They were built while B4 waits on permission (Q-001, Q-005), not instead of it.

---

## Stretch

Optional. Attempted only if the Baseline and Target are complete and time remains.

| | Requirement | Verified by | Status |
|---|---|---|---|
| **S1** | Images placed sensibly within the document rather than appended at the end | T-16 | **Built** — each image is tagged with the section it belongs beside and is placed there in the PDF and the portfolio page (`caseforge/models.py`, `caseforge/render/`). T-16 not formally recorded |
| **S2** | Flags weak input, for example noting that no measurable result was provided | T-17 | **Built** — `caseforge/gaps.py` reports missing topics instead of filling them, and conflicting numbers in the notes become a blocking question rather than a guess. A blocking gap must be answered before approval |
| **S3** | Batch generation across a set of projects | T-18 | **Not started** — projects are generated one at a time |
| **S4** | Output in more than one language | T-19 | **Not started** — English only |

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
> **Built is not the same as done.** The product is built, deployed and running at https://caseforge-rcdu.onrender.com, and the automated suite covers it. But **no Baseline item is formally complete**, because completion requires B4 — three *real* project inputs — and the two-person claim check in B5. All four sample inputs in `samples/` are team-constructed and fictional, as `samples/README.md` states. Every number we report comes from notes we wrote ourselves.

| Tier | Items | Built | Formally complete |
|---|---|---|---|
| Baseline | 5 | B1, B2, B3 built and tested; B5 measured on our own inputs | 0 — B4 outstanding |
| Target | 5 | T1 (one format short), T2, T3 built | 0 — T4 and T5 not run |
| Stretch | 4 | S1 and S2 built | 0 |

**What stands between us and a complete Baseline is not code.** It is three real project inputs and a second person checking the claims — tasks BT-2, BT-7 and BT-8, blocked on permission (Q-001, Q-005).

The remaining Baseline tasks, with owners and completion criteria, are in the [Project Overview](project-overview.md#21-current-status-and-next-steps). Every run recorded so far is in [`tests/results.md`](../tests/results.md); a test that is not recorded there is not counted as passed.

---

## Related documents

- [Project Overview](project-overview.md) — scope, approach and current status
- [Test Plan](test-plan.md) — how each requirement is checked
- [Demo Script](demo-script.md) — what we will show
- [Data Sources](data-sources.md) — where the three real inputs for B4 will come from
- [Question Log](question-log.md) — what is still undecided
