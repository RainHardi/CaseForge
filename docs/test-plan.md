# Test Plan

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator |
| **Repository** | CaseForge |
| **Team** | Team 5 |
| **Reviewer** | Abdulaziz (AI / Engineering) |
| **Status** | Initial Draft |
| **Last Updated** | September 2026 |

This document explains what we plan to test, how we'll test it, and what counts as success. It follows our project's Definition of Done (Baseline, Target, Stretch). It's an initial draft, so details we haven't decided yet are marked **TBD**.

---

## 1. What Matters Most

CaseForge has one rule that outranks everything else: **it must never put a claim in the case study that wasn't in the input.** A case study is a client-facing sales document, so an invented number like "reduced processing time by 40%" is worse than a badly written sentence. It's a false claim with the company's name on it.

Because of that, most of this plan is about **faithfulness testing**, and we start it from the first working version, not at the end.

---

## 2. Test Inputs

We test with the project inputs described in [DATA_SOURCES.md](DATA_SOURCES.md). The test set will include:

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

This tells us how much the automated check can be trusted, and why the human review step is still required.

### Step 3: Missing information

For inputs with gaps (like no measurable results), we check that CaseForge **flags the gap** instead of filling it in.

---

## 4. Baseline Tests

These must all pass before we move on to Target work.

| Test ID | What We Test | How | Pass When |
|---|---|---|---|
| T-01 | Structured input | Enter project info covering client problem, work done, approach, tools, challenges, results, and images | All fields are saved and passed to the next step correctly |
| T-02 | Fact extraction | Compare extracted facts to our hand-written fact list | Facts are pulled from the input only; nothing is added |
| T-03 | Case study generation | Generate a case study from each test input | Output follows the fixed template, with every section filled or clearly marked as missing |
| T-04 | No invented claims | Manual claim check (Section 3, Step 1) on every test case | **Zero** Unsupported or Contradicted claims in the final approved output, on every test case |
| T-05 | Automated faithfulness check | Planted-claim test (Section 3, Step 2) | Catch rate and false-flag rate are recorded. Target rate: **TBD** |
| T-06 | Missing information | Run inputs with no measurable results | Gap is flagged; no number is invented |
| T-07 | Human review and editing | Edit a draft, reject a draft, approve a draft | Edits appear in the output; nothing exports without approval |
| T-08 | One-page summary | Generate a summary for each test input | Summary fits on one page and passes the same claim check as T-04 |
| T-09 | PDF generation | Export approved case studies | PDF opens, follows the template, and matches the approved text |
| T-10 | End-to-end run | Run three real project inputs through the whole workflow | All three produce an approved PDF with no invented claims |

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

Every test run is recorded in a results log (location in the repo: **TBD**, e.g. `tests/results.md`).

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
| Q-T01 | What catch rate should the automated faithfulness check reach to be useful? | Not decided |
| Q-T02 | How many test inputs do we need in total? | Not decided |
| Q-T03 | What goes on the brand rules checklist, and whose brand do we follow? | Not checked |
| Q-T04 | Who will be our outside user for T-14? | Not decided |
| Q-T05 | Who writes the manual case study for the time comparison (T-15), and on which project? | Not decided |

We'll update this plan as these are answered and as testing shows us what we missed.
