# Demo Script

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator |
| **Repository** | CaseForge |
| **Team** | Team 5 |
| **Status** | Planned — nothing is demonstrable yet |
| **Last Updated** | 23 October 2026 |

> [!IMPORTANT]
> **There is nothing to demonstrate yet.** Implementation has not started. This document is the scenario we are building towards, so that the demo shapes the build rather than being assembled at the end.

## What the demo has to prove

That messy project information can be turned into a document a company would actually send to a client, **without anything being invented along the way**.

Everything else — the interface, the template, the speed — is secondary. If the audience remembers one thing, it should be the moment the system catches a claim that was never in the input and refuses to let it through.

## Audience

The course instructors and classmates, and through them the kind of buyer we are designing for: someone who sells work based on past projects and cannot afford a false claim in a client-facing document.

---

## Sample input

A team-constructed example (source DS-02 in [Data Sources](data-sources.md)) — deliberately messy, the way the information actually arrives:

```
logistics client - wanted a dashboard
we used python + react, took about 3 months
hard part was their old database, lots of weird date formats
2 devs on it, me and one other
they seemed happy with it

pasted from team chat:
"do u remember when we finished the phase 2 part? was it march?"
"yeah march i think, before the demo anyway"

[screenshot_dashboard.png]
```

Note what is **not** in this input: no measurable result, no client name, no exact dates, no project value. A general AI writing tool asked to produce a case study from this will usually supply some of them. That is the point of the demo.

---

## The 2–3 minute video

| Time | What is shown | What is said |
|---|---|---|
| 0:00–0:20 | Title, then the problem | A case study takes an engineer three to four unbillable hours, so it rarely gets written. Companies finish good work and have nothing to show for it. |
| 0:20–0:40 | The messy input above, pasted in | This is what the information actually looks like. Rough notes and a chat thread. |
| 0:40–1:05 | Generation runs; the draft appears with flags | The system writes the case study, then checks every claim in it against what was pasted in. |
| 1:05–1:50 | **The review step.** An unsupported claim is highlighted; the missing-result gap is highlighted. The user corrects one and removes the other, then approves. | This sentence contains a figure that was never in the notes, so it is flagged. The system will not export until a person has dealt with it. |
| 1:50–2:15 | The approved PDF case study and the one-page summary open | Here is the finished document, and every sentence in it traces back to something that was actually provided. |
| 2:15–2:40 | A classmate's own project run through the tool | This is a real project belonging to someone in this room, and this is their portfolio piece. |
| 2:40–3:00 | The measured time comparison | Three and a half hours by hand, about thirty minutes of review with the tool, measured rather than estimated. |

**The strongest moment is 2:15.** Running a real project belonging to someone in the room turns the demo from a claim into a demonstration, because that person can verify every line of the output themselves.

---

## Live demo (in class)

The same six steps, with more room to pause:

1. **State the business case.** What a case study costs to produce today, and how many the company is missing.
2. **Paste in genuinely messy notes** about a real project. Not a cleaned-up example.
3. **Generate live and open the PDF.**
4. **Show the review step catching something and being corrected.** Say plainly that the approval stage is a feature, not a limitation — a buyer who is publishing this under their own company name wants it there.
5. **Run a classmate's project through it** and show the student-facing output.
6. **Show the measured time comparison.**

### Optional: the comparison

If time allows, run the same input through ChatGPT or Gemini beforehand and put the two outputs side by side, with every claim that was not in the input marked on each. This is the clearest way to show what the system adds, and the method is defined in [Test Plan](test-plan.md) Section 3, Step 4.

We report this honestly, including runs where the general tool performs well.

---

## Expected output

- A PDF case study on the fixed template, with sections for the client problem, approach, work done, challenges and results
- A one-page summary of the same project
- Every claim in both traceable to the pasted input
- The missing result reported as missing, not filled in with a number

---

## If it fails

Section 8.3 asks what we would do if the demo failed. Our plan:

| Failure | What we do |
|---|---|
| The Gemini API is rate-limited or unavailable | Fall back to a recorded run of the same input, saved in advance. We say openly that this is a recording and why. |
| Generation produces badly formatted or unparseable output | Show it. Explain that consistent structured output is one of our four known hard parts, and show the handling we have built for it. |
| The automated checker misses a planted claim | Show that too, and show the manual claim check catching it. This is exactly why human approval is mandatory and not optional — a miss supports our design rather than undermining it. |
| Nothing runs at all | Walk through the recorded demo and the test results log, and explain honestly where the build stopped. |

We do not present a pre-recorded run as a live one, and we do not demonstrate on an input we have quietly cleaned up beforehand.

---

## Collecting feedback

After the demo:

- Ask two or three classmates to run **their own** project through the tool while we watch without helping. We record what confused them and what broke. This is Target item **T4** and test **T-14**.
- A short three-question form: Would you send this document to an employer or a client? What is wrong with it? What stopped you?
- Every issue goes into the results log at `tests/results.md` and, where it changes the plan, into the [Question Log](question-log.md).

---

## Before the demo — checklist

- [ ] The messy input is genuinely messy and has not been tidied up
- [ ] A recorded fallback run of the same input is saved and tested
- [ ] Permission obtained from the classmate whose project we run (see [Data Sources](data-sources.md))
- [ ] The time comparison figure is measured, with the method written down
- [ ] Known limitations are written down so we can state them before anyone asks
- [ ] API key is in `.env` and is not visible on screen, in slides, or in the recording

---

## Related documents

- [Definition of Done](definition-of-done.md) — what the demo must show to count as complete
- [Test Plan](test-plan.md) — how each claim in the demo is verified
- [Project Overview](project-overview.md) — scope and current status
