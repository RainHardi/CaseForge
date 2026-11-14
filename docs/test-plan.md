# Test Plan

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator |
| **Repository** | CaseForge |
| **Team** | Team 5 |
| **Reviewer** | Abdulaziz (AI / Engineering) |
| **Status** | Midterm draft — no system tests run; one baseline evaluation completed |
| **Last Updated** | 24 October 2026 |

This document explains what we plan to test, how we'll test it, and what counts as success. It follows our project's [Definition of Done](definition-of-done.md) (Baseline, Target, Stretch). Details we haven't decided yet are marked **TBD**.

> [!IMPORTANT]
> **Test status: no system tests run.** Implementation has not started, so no test T-01 to T-19 below has been run. One evaluation has been completed — the baseline measurement in Section 3, Step 4, carried out on 24 October 2026. Current status and the next tests are in [Section 12](#12-test-status-and-next-steps).

---

## 1. What Matters Most

CaseForge has one rule that outranks everything else: **it must never put a claim in the case study that wasn't in the input.** A case study is a client-facing sales document, so an invented number like "reduced processing time by 40%" is worse than a badly written sentence. It's a false claim with the company's name on it.

Because of that, most of this plan is about **faithfulness testing**, and we start it from the first working version, not at the end.

---

## 2. Test Inputs

We test with the project inputs described in [data-sources.md](data-sources.md). The test set will include:

| Input Type | Example | Why |
|---|---|---|
| Clean | Complete project info filled into the structured form | Checks the normal case works |
| Rough notes | Unstructured bullet points | Real users rarely have clean info |
| Pasted conversation | A chat thread between team members | Target requirement: messier input |
| Missing results | A project with no measurable results | The most likely place for the AI to invent a number |
| Very short | Two-sentence project description | Layout must still look right |
| Very long | Several pages of project info | Layout must still look right |
| Classmate project | A real capstone from another team (with permission) | Student users and the final demo |

**Fact list:** for every test input, we write down by hand the facts it actually states (the "fact list"). This is what we compare the generated case study against. The fact list is written *before* we run the input through CaseForge, so the output can't influence it.

Baseline needs at least **three real project inputs** working end to end. Total size of the test set: **TBD**.

---

## 3. How We Test Faithfulness

### Step 1: Manual claim check

For each generated case study, we go through it sentence by sentence and label every factual claim:

| Label | Meaning | Allowed? |
|---|---|---|
| **Supported** | The claim is stated in the input | Yes |
| **Reworded** | Same meaning as the input, said more professionally | Yes |
| **Unsupported** | Not in the input (invented metric, result, tool, client detail) | **No** |
| **Contradicted** | Goes against something in the input | **No** |

Two team members check each case study separately and then compare. If they disagree, the team decides together and we record the reason.

### Step 2: Testing the automated checker

CaseForge includes an automated faithfulness check that flags unsupported claims. We need to know whether it actually works, so we test it on its own:

- We take generated drafts and **deliberately plant unsupported claims** in them (for example, an invented percentage or a tool that was never mentioned).
- We run the automated check and count how many planted claims it catches.
- We also count how often it wrongly flags claims that *are* supported.

**Test conditions and provisional target** (to be confirmed by the team — **Q-T01**):

| | |
|---|---|
| Sample | 20 planted claims spread across at least 5 generated drafts, from at least 3 different inputs |
| Types of planted claim | Invented numeric result, invented tool or technology, invented client detail, exaggerated outcome |
| **Catch rate** | Provisional target: the checker flags at least **18 of 20** planted claims (90%) |
| **False-flag rate** | Recorded, not targeted at Baseline. A checker that flags too much is annoying; one that misses claims is dangerous, so we prioritise catch rate first. |
| Repeats | Each draft is checked three times, because model output varies between runs |

This tells us how far the automated check can be trusted, and it is also the evidence for why the human review step stays mandatory regardless of the score.

### Step 4: Comparison against a general AI tool

Our Core is faithfulness verification, so we test that claim directly rather than asserting it.

- The **same messy project input** is given to a general AI chat tool (ChatGPT or Gemini, with a reasonable prompt asking for a case study) and to CaseForge.
- Two people independently label every factual claim in both outputs as supported, reworded, unsupported or contradicted, using the hand-written fact list for that input.
- We record the number of unsupported and contradicted claims produced by each, and whether each tool flagged anything as missing.

#### Baseline measurement — completed 24 October 2026

Because implementation has not started, we could not compare the two systems. We instead measured the general AI tool on its own, which establishes the figure our Baseline requirement B5 will be measured against.

**Method.** One team-constructed input (rough notes plus a pasted chat fragment, with no measurable result, no client name and no exact dates). Its stated facts were listed by hand before anything was generated. The input was then given to ChatGPT in a fresh conversation under two conditions, three runs each.

| Condition | Runs | Invented metrics | Unsupported inferences | Flagged missing information |
|---|---|---|---|---|
| A — natural request for a case study | 3 | 0 | 4 to 6 per run | 3 of 3 |
| B — same request, told not to invent detail | 3 | 0 | 0 to 1 per run | 3 of 3 |
| CaseForge | — | *not yet testable — no implementation* | | |

**Findings.** The result did not match our expectation, and we report it as observed. ChatGPT invented no performance metrics, no client name and no false dates in any run, and in every run it appended a list of details the user should verify before publishing.

What it did produce consistently were unsupported inferences. In all three runs of condition A it stated that Python was used for the backend and React for the frontend; our notes say only "python + react." Other examples: describing the dashboard as supporting "day-to-day decision-making" and providing "centralized data access," neither of which appears in the input. These are plausible, probably true, and for that reason harder to catch than an invented percentage.

Condition B produced faithful text that was unusable. The output stated within itself that the client's name and results "were not provided in the available notes" — accurate, and impossible to send to a prospective client.

**What this changes.** We no longer claim that general AI tools invent facts; our own measurement does not support that. The defensible claim is that they advise without enforcing — nothing recorded the advice, nothing prevented publication without acting on it, the faithful version was unusable, and three runs are not a guarantee about the fourth.

**Limitations.** One tool, one input, six runs, and labelling by a single team member rather than the two our method requires. Read as an initial measurement, not a general finding about AI writing tools. Gemini was not tested, and the checker-preview test was not run.

### Step 3: Missing information

For inputs with gaps (like no measurable results), we check that CaseForge **flags the gap** instead of filling it in.

---

## 4. Baseline Tests

These must all pass before we move on to Target work.

| Test ID | What We Test | How | Pass When | Status |
|---|---|---|---|---|
| T-01 | Structured input | Enter project info covering client problem, work done, approach, tools, challenges, results, and images | All fields are saved and passed to the next step correctly | Not run |
| T-02 | Fact extraction | Compare extracted facts to our hand-written fact list | Facts are pulled from the input only; nothing is added | Not run |
| T-03 | Case study generation | Generate a case study from each test input | Output follows the fixed template, with every section filled or clearly marked as missing | Not run |
| T-04 | No invented claims | Manual claim check (Section 3, Step 1) on every test case | **Zero** Unsupported or Contradicted claims in the final approved output, on every test case | Not run |
| T-05 | Automated faithfulness check | Planted-claim test (Section 3, Step 2) | Catch rate and false-flag rate recorded; provisional target in Section 3, Step 2 | Not run |
| T-06 | Missing information | Run inputs with no measurable results | Gap is flagged; no number is invented | Not run |
| T-07 | Human review and editing | Edit a draft, reject a draft, approve a draft | Edits appear in the output; nothing exports without approval | Not run |
| T-08 | One-page summary | Generate a summary for each test input | Summary fits on one page and passes the same claim check as T-04 | Not run |
| T-09 | PDF generation | Export approved case studies | PDF opens, follows the template, and matches the approved text | Not run |
| T-10 | End-to-end run | Run three real project inputs through the whole workflow | All three produce an approved PDF with no invented claims | Not run |

### Which test proves which Baseline requirement

| Baseline item (Definition of Done) | Proved by | Result that shows it is met |
|---|---|---|
| B1 — accepts structured project input | T-01 | Every field is captured and reaches the generation step |
| B2 — one-page summary and PDF case study on a fixed template | T-03, T-08, T-09 | Both documents open, follow the template, and match the approved text |
| B3 — human review before anything is final | T-07 | Export is impossible until a person approves; edits appear in the output |
| B4 — works end to end on three real project inputs | T-10 | Three approved PDFs produced from three real inputs |
| B5 — no claim that was not in the input, verified on every test case | T-02, T-04, T-05, T-06 | Zero unsupported or contradicted claims across every test case, with the automated checker's catch rate recorded |

---

## 5. Target Tests

| Test ID | What We Test | How | Pass When |
|---|---|---|---|
| T-11 | Multiple output formats | Generate a PDF case study, portfolio page, one-page summary, and partner presentation from one project record | All four are produced and all pass the claim check |
| T-12 | Brand rules | Check outputs against a written checklist for tone, structure, and layout (checklist: **TBD**) | Every checklist item passes |
| T-13 | Messy input | Run rough notes and pasted conversations instead of the form | Output quality and faithfulness match the clean-input results |
| T-14 | Outside user test | Someone outside our team uses CaseForge **without instructions** while we watch | They finish a case study on their own. We record everything that broke or confused them |
| T-15 | Time comparison | Time someone writing a case study by hand vs. with CaseForge, for the same project | Both times are **measured**, not estimated, and reported honestly |

---

## 6. Stretch Tests

Only if all Baseline and Target tests pass.

| Test ID | What We Test | Pass When |
|---|---|---|
| T-16 | Image placement | Images appear next to the text they relate to, not stacked at the end |
| T-17 | Weak input flags | CaseForge warns the user about weak input (e.g. "no measurable result was provided") before generating |
| T-18 | Batch generation | Several projects are processed in one run, and each passes the claim check |
| T-19 | Other languages | Output in a second language passes the claim check (language: **TBD**) |

---

## 7. Other Checks

- **Consistent structured output:** the AI's output must be in the right shape *every* time, not most of the time. We'll run each test input several times (number: **TBD**) and record any run where the output couldn't be parsed.
- **Layout with different input lengths:** the very short and very long inputs are checked visually in the final PDF.
- **Free-tier limits:** we record any rate-limit errors from the Gemini free tier during testing.

---

## 8. Recording Results

Every test run is recorded in a results log at `tests/results.md`. **This file does not exist yet** — it will be created with the first test run.

| Date | Test ID | Input Used | Result (Pass / Fail) | Unsupported Claims Found | Notes | Tested By |
|---|---|---|---|---|---|---|
| | | | | | | |

Rules we follow:

- We only mark a test as passed if we actually ran it.
- Failures stay in the log, even after they're fixed.
- Known errors and limitations are listed in the README honestly.

---

## 9. Who Tests What

- Each feature owner tests their own work and agrees on the testing method with Odina (Data & Research) first.
- Odina prepares the test inputs, fact lists, and the results log.
- Claim checks (T-04) are always done by two people.
- The outside user test (T-14) is run by the whole team, with one person watching and taking notes.

---

## 10. When We Test

| Stage | Tests |
|---|---|
| Early development | T-02, T-04, and T-05 start as soon as extraction and generation produce anything. Faithfulness is checked from the beginning. |
| Baseline complete | Full run of T-01 to T-10 |
| Target development | T-11 to T-15, plus re-running Baseline tests after changes |
| Before the final demo | Full re-run of every test we claim passes |

Exact dates: **TBD**, to be set with the PM.

---

## 11. Open Questions

| ID | Question | Status |
|---|---|---|
| Q-T01 | Is the provisional catch-rate target of 18 out of 20 planted claims the right bar? | Provisional target set in Section 3, Step 2 — to be confirmed by the team |
| Q-T02 | How many test inputs do we need in total? | Not decided |
| Q-T03 | What goes on the brand rules checklist, and whose brand do we follow? | Not checked |
| Q-T04 | Who will be our outside user for T-14? | Not decided |
| Q-T05 | Who writes the manual case study for the time comparison (T-15), and on which project? | Not decided |

We'll update this plan as these are answered and as testing shows us what we missed.

---

## 12. Test Status and Next Steps

### Tests performed so far

**No system test has been run**, because no code exists. Every test T-01 to T-19 is planned, not completed, and the results log at `tests/results.md` will be created with the first run.

**One evaluation has been completed:** the baseline measurement of the problem, carried out on 24 October 2026 and recorded in Section 3, Step 4. Its supporting evidence is the set of six generated outputs, retained by the team. Its headline finding is that the general AI tool we tested invented no metrics but produced four to six unsupported inferences per run in normal use, and advised without enforcing — which revised the claim we make about our own differentiation.

### Issues still to resolve before testing can begin

| Issue | Blocking | Owner |
|---|---|---|
| No code exists — no pipeline to test | Every test | Abdulaziz (**BT-1**) |
| No test inputs and no hand-written fact lists | T-02, T-04, T-05, T-06, T-10 | Odina (**BT-2**) |
| Catch-rate target not confirmed | T-05 | Team (**Q-T01**) |
| Permission for HumbleBeeAI and classmate material not requested | T-10, T-14 | Odina (**Q-D01**, **Q-D05**) |
| Gemini free-tier rate limits unknown | Repeated runs in T-05 | Abdulaziz (**Q-D04**) |

### The first tests we will run

In this order, as soon as the smallest end-to-end path exists:

1. **Repeat the baseline measurement on Gemini**, so the finding does not rest on one tool.
2. **Run the checker-preview test**: give a generated draft and the original notes to a separate model call and ask it to label every claim. If it catches the backend/frontend inference that generation produced in three runs out of three, that is our first direct evidence that a separate checking pass works.
3. **T-02 — fact extraction.** The first thing worth knowing is whether the model reports only what is in the input. This can be tested with one input and one fact list, before any interface or PDF work exists.
4. **T-04 — manual claim check.** Two people label every claim in the first generated draft. This gives us our first real measurement of the problem the project exists to solve.
5. **T-05 — planted-claim test.** Once a checker exists, measure whether it catches claims we know are false.

T-01, T-03 and T-06 to T-10 follow as the corresponding features are built.

### What we expect to find

We expect early drafts to contain unsupported claims, and we expect the first version of the automated checker to miss some of them. Recording those failures is the point of the exercise: the gap between what the checker catches and what the manual check catches is the measurement that tells us whether the Core of this project actually works.
