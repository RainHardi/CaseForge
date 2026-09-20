# Data Sources

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator |
| **Repository** | CaseForge |
| **Team** | Team 5 |
| **Document Owner** | Odina (Data & Research) |
| **Reviewer** | Abdulaziz (AI / Engineering) |
| **Status** | Initial Draft |
| **Last Updated** | September 2026 |

This document lists the data, APIs, and other sources CaseForge plans to use, the conditions for using each one, and what we still need to confirm. It's an initial draft, so anything we haven't settled yet is marked **TBD**. We'll update it as we collect data and get permissions.

---

## 1. What Data CaseForge Needs

CaseForge turns messy project information into a professional case study. To build and test it, we need **project information**: descriptions of real or realistic projects, including the client problem, the work done, the approach, tools used, challenges, results, and images.

We need two kinds of input:

- **Clean input:** well-organized project information, mostly filled into a structured form.
- **Messy input:** rough notes, pasted chat conversations, incomplete descriptions, and project information with missing results. This is the kind of input real users actually have, so a system that only works on clean input hasn't solved the problem.

For every test input, we also need a way to check the output. Our plan is to write down, by hand, the list of facts each input actually contains. That list is what we compare the generated case study against to catch invented claims.

---

## 2. Summary of Sources

| ID | Source | Type | Used For | Access Status | Contains Personal Info? |
|---|---|---|---|---|---|
| DS-01 | HumbleBeeAI projects cleared for external sharing | Project information | Main test cases (real business projects) | TBD, not yet requested | TBD, to be checked before use |
| DS-02 | Project information constructed by our team | Written test inputs | Clean and messy test cases, edge cases | Available (we create it) | No |
| DS-03 | Our own capstone project (CaseForge) | Project information | Test case and demo example | Available | No (team names only, with consent) |
| DS-04 | Classmates' capstone projects | Project information | Student-facing test cases, user testing, demo | TBD, permission needed from each team | Possibly (names), removed before use |
| API-01 | Google Gemini API (Google AI Studio) | External AI model | Fact extraction, case study writing, claim checking | Planned, free tier to be tested | We send no personal info |

---

## 3. Source Details

### DS-01: HumbleBeeAI Projects Cleared for External Sharing

- **What it is:** Information about completed HumbleBeeAI projects in areas like AI development, R&D, cybersecurity, data science, and software engineering.
- **Why we need it:** These are the real business cases CaseForge is designed for. They show what a services company's project information actually looks like.
- **Source link:** TBD
- **Usage conditions:** Only projects that HumbleBeeAI has cleared for external sharing. No client confidential material and no internal company data.
- **Access:** TBD. We need to ask which projects are cleared and in what form we'll receive the information.
- **Personal information:** TBD. Client and employee names will be removed or replaced before processing if present.
- **Can it go in the public repo?** TBD. Depends on what HumbleBeeAI allows. If not allowed, we'll keep it out of the repo and describe how to obtain it instead.

### DS-02: Team-Constructed Project Information

- **What it is:** Project descriptions we write ourselves, based on realistic but made-up projects.
- **Why we need it:** It lets us create exactly the test cases we need, especially bad ones, without waiting on permissions. Examples we plan to write:
  - A clean, complete project description
  - Rough bullet-point notes with no structure
  - A pasted chat conversation between team members
  - A project with **no measurable results** (to check that CaseForge doesn't invent a number)
  - A very short description (two sentences) and a very long one (several pages), to test layout
- **Source link:** Stored in this repository (folder TBD, e.g. `data/constructed/`).
- **Usage conditions:** Created by our team, so no restrictions.
- **Personal information:** None. We'll use made-up company and people names.
- **Can it go in the public repo?** Yes.

### DS-03: Our Own Capstone Project

- **What it is:** Information about CaseForge itself: our notes, meeting records, and progress as the semester goes on.
- **Why we need it:** It's a real project with naturally messy information, and we have full access to it. It also works well as a demo example.
- **Source link:** This repository.
- **Usage conditions:** Team members agree to its use. Private details (personal contacts, chat messages) are left out.
- **Personal information:** Team member names only, used with everyone's agreement.
- **Can it go in the public repo?** Yes, after removing anything private.

### DS-04: Classmates' Capstone Projects

- **What it is:** Project information from other teams in the course.
- **Why we need it:** Students are our secondary users, and classmates are the fastest real feedback we can get. Running a classmate's project through CaseForge is also a key part of our final demo.
- **Source link:** TBD, provided by each team that agrees to take part.
- **Usage conditions:** Only with permission from the team. We won't publish their material without their agreement.
- **Personal information:** Possibly names. We'll remove or replace identifiers before processing unless the team asks to keep them.
- **Can it go in the public repo?** Only if the team agrees. Otherwise it stays out of the repo.

---

## 4. External APIs and Tools

### API-01: Google Gemini API (Google AI Studio)

- **What it's for:** The language model behind fact extraction, case study writing, and the faithfulness check.
- **Access:** API key from Google AI Studio. We plan to use the free tier so the project doesn't need a budget.
- **Limitations:**
  - The free tier has rate limits. Exact limits for our use: **TBD**, to be tested by Abdulaziz.
  - Google's terms for the free tier may allow Google to use submitted content to improve its products. This is one more reason we only send safe, non-confidential information. We will confirm the current terms before sending any real project data.
- **Fallback if the free tier is unavailable or rate-limited:** TBD. We'll ask the instructors before paying for any service.
- **Security:** The API key is stored in a `.env` file that's excluded from Git. The repo includes a `.env.example` with blank values.

### PDF Generation Libraries

We plan to use either **ReportLab** or **WeasyPrint** (Python) to create the final PDF. These are software tools, not data sources, but we'll record the chosen library's version and license in the README once decided. Choice: **TBD**.

---

## 5. Data We Will Not Use

- Client confidential material
- Internal company data that isn't approved for sharing
- Personal information about people who haven't agreed to it
- Recordings or videos of people, or chat messages from community groups
- Any classmate's project information without their team's permission

---

## 6. Preparing the Data

Before a project input is used for testing, we will:

1. **Check permission.** Confirm the source is allowed and record it in the permission log below.
2. **Remove identifiers.** Replace personal names, contact details, and client names with placeholders unless we have agreement to keep them.
3. **Convert to text.** Save each input as a plain text or Markdown file. Images are kept as separate files.
4. **Label it.** Tag each input as *clean* or *messy*, and note what's missing (for example, "no measurable results").
5. **Write the fact list.** Record the facts the input actually states, which we use to check the generated case study for invented claims.

For the Baseline, we need at least **three real project inputs** that work end to end. Target number of total test inputs: **TBD**.

---

## 7. Permission Log

| Source | Project / Item | Permission From | Date Given | Allowed in Public Repo? | Notes |
|---|---|---|---|---|---|
| DS-01 | TBD | HumbleBeeAI | TBD | TBD | |
| DS-03 | CaseForge | Team 5 members | TBD | Yes | |
| DS-04 | TBD | TBD | TBD | TBD | |

---

## 8. Open Questions

| ID | Question | Who to Ask | Status |
|---|---|---|---|
| Q-D01 | Which HumbleBeeAI projects are cleared for external sharing, and in what format will we get them? | HumbleBeeAI / instructors | Not checked |
| Q-D02 | Are we allowed to send HumbleBeeAI project information to an external AI service like Gemini? | HumbleBeeAI / instructors | Not checked |
| Q-D03 | Can HumbleBeeAI project information be stored in our public repo, or only described? | HumbleBeeAI | Not checked |
| Q-D04 | Are the Gemini free tier rate limits enough for our testing? | Team (Abdulaziz to test) | Not checked |
| Q-D05 | How many classmate teams are willing to share their projects? | Classmates | Not checked |

We'll update this document as these questions get answered.
