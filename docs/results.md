# Test Results Log

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator (CaseForge) |
| **Team** | Team 5 |
| **Started** | 31 October 2026 |
| **Last Updated** | 20 November 2026 |

This is the record referred to by the [Definition of Done](../docs/definition-of-done.md) and the [Test Plan](../docs/test-plan.md). **A test is counted as passed only if it appears here.** A test source file is not evidence that a test passed — only a dated run with its result is.

Failures stay in this log after they are fixed.

---

## Summary

| Test | What it checks | Last run | Result |
|---|---|---|---|
| T-05 | Planted-claim catch rate (faithfulness checker) | 31 Oct 2026 | Pass — 20/20 planted claims caught in all 3 repeats, 0/109 false flags |
| T-07 | Nothing exports without approval | 31 Oct 2026 | Pass |
| T-08, T-09 | PDF and one-page summary layout | 31 Oct 2026 | Pass |
| T-01, T-03 | Input intake and template structure | 31 Oct 2026 | Covered by the automated suite; not separately recorded |
| T-02 | Extraction against the hand-written fact lists | — | **Not run** |
| T-04 | Two-person manual claim check | — | **Not run** |
| T-06 | — | — | **Not run** |
| T-10 | End to end on three **real** project inputs | — | **Not run** — no real inputs yet (BT-2) |
| T-11 to T-19 | Target and Stretch | — | **Not run** — the features exist, the measurements do not |
| Automated suite | 114 tests across ingest, pipeline, rules, review/export, designed report, web API, Notion, Verified link, sign-off, anonymized version, proof library | 20 Nov 2026 | Reported passing by the author; independent clean-clone run still outstanding |

---

## Runs

### 2026-10-31 · T-05 · Planted-claim test (Gemini)

| | |
|---|---|
| **Run by** | Abdulaziz |
| **Engine** | `gemini:gemini-3.5-flash-lite` (free tier) |
| **Command** | `python eval/planted_claims.py --repeats 3` |
| **Inputs** | 3 team-constructed samples: `01_clean_form/input.json`, `02_rough_notes/notes.txt`, `03_pasted_chat/chat.txt` |
| **Design** | 20 planted claims per pass (7 + 7 + 6 across the three inputs), 3 repeats = 60 observations |
| **Catch rate** | **60 / 60 observations (100%)** — i.e. every one of the 20 planted claims was caught in all three repeats |
| **False flags** | **0 / 109** genuine draft claims |
| **Raw output** | `eval/results/planted_20261031_2301.md` |

By planted type, across all repeats: invented number 15/15, invented tool 15/15, invented client detail 15/15, exaggerated outcome 15/15. No planted claim was missed.

**Limits, stated plainly:**

- All three inputs are **team-constructed and fictional**. Nothing here has been tested on a real client project.
- The planted claims are short and obvious — an invented number, an invented tool name. The unsupported claims that actually matter are the subtle inferences a general model produces (see the 24 October measurement below, where ChatGPT named a backend framework our notes never mentioned). **This run is not evidence that those would be caught.**
- The same person wrote the checker and wrote the planted-claim set.
- Three repeats of the same 20 claims are not 60 independent samples.
- The provisional target (18 of 20) was never confirmed by the team — see **Q-006**.

**Follow-up:** test **T-05b**, planted claims written as inferences rather than invented facts, due 16 November.

### 2026-10-31 · T-05 · Planted-claim test (offline rules only)

| | |
|---|---|
| **Run by** | Abdulaziz |
| **Engine** | `offline rules` — no model call |
| **Inputs** | Same three samples, 1 repeat |
| **Catch rate** | 20 / 20 (100%) |
| **False flags** | 0 / 36 |
| **Raw output** | `eval/results/planted_20261031_1153.md` |

Recorded for completeness and kept separate on purpose. In offline mode each draft sentence is copied from the notes, so this measures the **deterministic rules**, not the model pass. It is not evidence about the checker as a whole.

A second Gemini run earlier the same evening (`planted_20261031_2232.md`) gave the same catch rate with a smaller denominator for false flags (0/98).

### 2026-10-31 · T-07 · Approval lock

| | |
|---|---|
| **Run by** | Abdulaziz |
| **How** | `tests/test_review_export.py`, run offline |
| **Result** | **Pass** |

Checks performed: export is refused before approval; any edit made after approval withdraws that approval; a blocking gap must be answered before approval is possible.

### 2026-10-31 · T-08, T-09 · Output layout

| | |
|---|---|
| **Run by** | Abdulaziz |
| **How** | `tests/test_review_export.py`, parametrised over a 1-sentence and a 400-sentence input |
| **Result** | **Pass** |

The one-page summary is exactly one page for both extremes, and every approved sentence appears in the PDF.

### 2026-11-20 · Automated suite and deployment

| | |
|---|---|
| **Run by** | Abdulaziz |
| **Command** | `python -m pytest` |
| **Suite** | 114 collected tests: `test_ingest` 8, `test_pipeline` 15, `test_rules` 8, `test_review_export` 10, `test_report` 39, `test_web` 10, `test_notion` 5, `test_verify` 5, `test_signoff` 4, `test_anonymize` 6, `test_library` 4 |
| **Result as reported** | **114 passed** as reported by the author. **Commit hash TBD:** `1e494c1`, quoted in an earlier version of this log, is not in the repository history; Abdulaziz to confirm the commit this run used. Per-file counts above not yet reconciled with `def test_` counts in `tests/` (111 found by search; parametrized tests may account for the difference) |
| **Deployment** | Pushes on 19–20 November did not trigger Render; deployed manually from the dashboard. Checked `/healthz`, the new screens in `app.js`, and that `/v/…`, `/s/…` and `/api/library` respond. Not clicked through on the live site |

New coverage: Notion import, Verified link, client sign-off, anonymized version and proof library. These were also checked by hand in a local browser; five bugs found that way were fixed.

> [!IMPORTANT]
> Same limits as the 14 November entry: author's run, team-constructed inputs, no clean-clone run by a second person, and **no user outside the team has tried the new features**.

### 2026-11-14 · Automated suite, after the web app and designed report

| | |
|---|---|
| **Run by** | Abdulaziz |
| **Command** | `python -m pytest` |
| **Suite** | 86 test functions: `test_ingest` 8, `test_pipeline` 13, `test_rules` 8, `test_review_export` 9, `test_report` 38, `test_web` 10 |
| **Result as reported** | Passing at the time of commit `438de94` |

The suite runs offline — the model is stubbed, so no API key is needed. It now covers the designed report (layout choice, length budgets, re-checking of every report element, brand kits, the approval hash) and the web API (signup, login, projects, approval, export).

> [!IMPORTANT]
> **Still to do:** nobody outside the author has run this suite, and the tests were written by the same person who wrote the code they test. A clean-clone run by a second person, with the exact output recorded here, is assigned to **Anvarbek**.

### 2026-11-14 · Deployment

| | |
|---|---|
| **Run by** | Abdulaziz |
| **Where** | Render (web service) + Neon (Postgres) |
| **URL** | https://caseforge-rcdu.onrender.com |
| **Checked** | The landing page, the sign-up and log-in screens and `/healthz` all respond |

Setup and environment variables are documented in [`docs/DEPLOY.md`](../docs/DEPLOY.md). No end-to-end run on the deployed instance has been recorded here yet — that is part of BT-7.

### 2026-10-31 · Automated suite

| | |
|---|---|
| **Run by** | Abdulaziz |
| **Command** | `python -m pytest` |
| **Environment** | Linux, Python 3.13 |
| **Result as reported** | 34 passed |
| **Also run** | Windows, Python 3.14.2, same day: 26 passed — before the file-upload tests were added, so that run does not cover the current code |

> [!IMPORTANT]
> **This entry needs re-running before it can be cited.** A further test was added on 1 November (commit `c4069d2`, product-code false flags), so the current suite is larger than 34. Nobody has re-run it since, and no one outside the author has run it from a clean clone. Re-running from a fresh clone and recording the exact output here is assigned to **Anvarbek, due 16 November**.

### 2026-10-24 · Baseline measurement of a general AI tool

| | |
|---|---|
| **Run by** | Anvarbek |
| **Tool** | ChatGPT, web interface |
| **Design** | 1 messy project input, 6 runs — 3 under a natural request, 3 instructed not to invent detail |
| **Result** | 0 invented metrics, client names or dates. 4–6 unsupported inferences per run (natural), 0–1 (constrained). Missing information flagged in 3 of 3 runs under both conditions |
| **Recorded in** | [Test Plan](../docs/test-plan.md) Section 3, Step 4 |

This measured a competitor, not CaseForge. It disproved the team's expected claim — general AI tools did not invent facts — and the claim was revised to "they advise without enforcing". Limits: one tool, one input, one labeller. Repeating it on Gemini with a second labeller is **Q-018**.

---

## What has never been tested

Stated here so it cannot be lost between documents:

- **Any real project input.** Every run above used material the team wrote itself.
- **Subtle unsupported inferences**, as opposed to obvious planted facts.
- **A clean-clone run by anyone other than the author.**
- **The code itself, by a second reviewer** — pull requests #15–#19 were opened and merged by their author, which our [ground rules](../docs/team-ground-rules.md) do not allow. Review due 9 November.
