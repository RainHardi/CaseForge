# Container Diagram (C4 Level 2)

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator (CaseForge) |
| **Team** | Team 5 |
| **Status** | Built and deployed (14 Nov 2026) — live at https://caseforge-rcdu.onrender.com; code map in the [README](../README.md#project-status) |
| **Last Updated** | 18 November 2026 |

Shows the main parts inside CaseForge, what each is responsible for, and how they communicate. External services sit outside the system boundary.

```mermaid
flowchart TB
    User(["<b>Content Author / Reviewer</b>"])

    subgraph Boundary["CaseForge — System Boundary"]
        direction TB
        Web["<b>Web Application</b><br/>Python — FastAPI + static front end<br/>Serves the landing page and the app,<br/>handles sign-up, log-in and workspaces,<br/>and exposes the project API"]
        UI["<b>Review Interface</b><br/>Browser front end (also Streamlit / CLI)<br/>Shows the draft with flagged claims,<br/>captures edits and approval,<br/>triggers export"]
        Pipeline["<b>Extraction &amp; Generation Pipeline</b><br/>Python<br/>Extracts only the facts stated in the input,<br/>then writes the case study from those facts"]
        Checker["<b>Faithfulness Checker</b><br/>Python<br/>Compares every claim against the source<br/>and the extracted facts; labels each one<br/>and flags missing information"]
        Store[("<b>Project Store</b><br/>Postgres in production, SQLite locally<br/>Workspaces, users, projects, images,<br/>brand kits, claim labels, approvals")]
        Renderer["<b>Document Renderer</b><br/>Python — ReportLab + Chromium<br/>PDF case study, one-page summary,<br/>portfolio page, designed 4–5 page report"]
    end

    LLM[["<b>LLM API</b> — Google Gemini, free tier<br/>(outside the system boundary)"]]

    User -- "Signs up, logs in, submits notes,<br/>images and brand kit" --> Web
    Web -- "Authenticates and scopes<br/>every request to a workspace" --> Store
    Web -- "Hands the project to the pipeline" --> Pipeline
    Web -- "Serves the review screen" --> UI
    Pipeline -- "Prompt + notes →<br/>stated facts, then draft" --> LLM
    Pipeline -- "Saves input, facts and draft" --> Store
    Pipeline -- "Hands over the draft<br/>for checking" --> Checker
    Checker -- "Reads the draft, the source input<br/>and the extracted facts" --> Store
    Checker -- "Claim vs source comparison" --> LLM
    Checker -- "Writes a label for every claim<br/>and any missing-information flags" --> Store
    UI -- "Reads draft and flags for review;<br/>writes edits and approval" --> Store
    UI -- "Triggers export —<br/>only once approved" --> Renderer
    Renderer -- "Reads the approved content" --> Store
    Renderer -- "Returns the rendered documents" --> UI

    classDef person fill:#1168bd,color:#fff,stroke:#0b4884,stroke-width:2px
    classDef container fill:#438dd5,color:#fff,stroke:#2d6ca8,stroke-width:2px
    classDef store fill:#438dd5,color:#fff,stroke:#2d6ca8,stroke-width:2px,stroke-dasharray: 4 2
    classDef external fill:#999999,color:#fff,stroke:#6b6b6b,stroke-width:2px

    class User person
    class Web,UI,Pipeline,Checker,Renderer container
    class Store store
    class LLM external
```

**Legend:** Mid blue = containers inside our system. Dashed border = a data store. Dark blue = the person using it. Grey = an external service, outside our control.

## What each container does

| Container | Technology | Responsibility | Baseline item | Build task | Status |
|---|---|---|---|---|---|
| **Web Application** | Python — FastAPI, static HTML/CSS/JS front end | Serves the public landing page and the app; handles sign-up, log-in, team workspaces and invite codes; scopes every project request to the signed-in user's workspace | B1, B3 | — | Built (Nov 2026) |
| **Review Interface** | Browser front end; Streamlit and CLI still work (Q-013 decided) | Collects the seven input fields and images, shows the draft with flagged claims, captures edits, records approval, and triggers export only after approval | B1, B3 | BT-1, BT-5 | Built |
| **Extraction & Generation Pipeline** | Python + Gemini | Pulls out only the facts stated in the input, then writes the case study from those facts rather than from the raw notes | B5 | BT-3 | Built |
| **Faithfulness Checker** | Python + Gemini | Compares every claim in the draft against the source and the extracted facts; labels each one; flags information that is missing rather than supplying it | B5 | BT-4 | Built |
| **Project Store** | Postgres (Neon) in production, SQLite locally; five tables — workspaces, users, projects, images, brand kits | Holds the source input, extracted facts, drafts, claim labels, edits and approval status, so that a document can always be traced back to what was provided. Also holds user accounts; passwords are stored as scrypt hashes, never in plain text | B3, B5 | BT-1 | Built |
| **Document Renderer** | Python — ReportLab (Q-012 decided) plus Chromium for the designed report | Renders approved content into the PDF case study, the one-page summary, the portfolio page and the designed 4–5 page branded report | B2, T1, T2 | BT-6 | Built |

> [!NOTE]
> **All five containers are built.** "Built" means the code exists and the automated tests pass; it does not yet mean the Baseline is met — that needs the real-input runs (BT-7) and the two-person claim check (BT-8).

## The two things this diagram is designed to guarantee

**1. Nothing is written from the raw notes.** The Pipeline extracts stated facts first and writes from those. The raw input stays in the Project Store so the Checker can compare against it afterwards.

**2. Nothing can be exported without approval.** The Renderer is reached only through the Interface, and only after the approval status in the Project Store is set. There is no path from the Pipeline to the Renderer. That gap in the diagram is deliberate — it is what makes B3 structural rather than a matter of discipline.

## Design decision and trade-off

**We considered generating and checking in a single LLM call** — ask the model to write the case study and mark its own unsupported claims at the same time. It would be cheaper, faster, and gentler on a rate-limited free tier.

We rejected it. A model checking its own output in the same call is not an independent check: it tends to agree with what it has just written, which is exactly the failure we are trying to catch. Separating the Checker into its own container means the check runs against the stored source input rather than against the model's own reasoning, and it means we can measure the Checker on its own with the planted-claim test ([Test Plan](test-plan.md), Section 3, Step 2).

**The cost is real:** two passes roughly double the number of API calls, against a free tier whose rate limits we have not yet measured (**Q-004**). If the limits turn out to be too tight, the fallback is to batch claims into fewer comparison calls rather than to merge the check back into generation — we would reduce the number of calls, not the independence of the check.

**We also considered a rules-based checker** — string and number matching against the input, with no model involved. It is deterministic, free and fast, and we may still use it as a first pass for numbers and dates specifically, since invented figures are our most dangerous failure. On its own it is not enough, because it cannot tell that a correctly paraphrased sentence is still faithful, and it would flag almost everything.

## Changes from the previous version

| Change | Reason |
|---|---|
| **Added the Faithfulness Checker as its own container** | The previous diagram had no box for it — the Pipeline only "applied missing-info flags". The check is the core of the project and it needs to be visible, independent, and separately testable |
| **Renamed Draft Store → Project Store, and widened what it holds** | The Checker needs the source input and the extracted facts, not just the draft. A store holding only drafts could not support the check at all |
| **Added the missing link from the store to the Document Renderer** | As previously drawn, the Renderer had no way to read the approved text it was supposed to render |
| **Renamed the boundary to CaseForge** | The repository, documents and product now use one name |
| **Added the Web Application container** (Nov 2026) | The product is now a hosted website with accounts and team workspaces. The previous diagram had no server, no authentication and no multi-user concept at all |
| **Project Store is now a real database** (Nov 2026) | JSON folders could not support accounts, workspaces or concurrent users. It is Postgres in production and SQLite locally, and it now also holds personal data — see [Data Sources](data-sources.md) |
| **Document Renderer gained Chromium** (Nov 2026) | The designed 4–5 page report is laid out in HTML/CSS and printed by headless Chromium; ReportLab still produces the fixed-template PDF and the one-pager |
| Recorded that the Checker also calls the LLM API | Level 1 was updated to match |

## Related

- [System Context Diagram (C4 Level 1)](c4-context.md) — the system's users and external dependencies
- [Definition of Done](definition-of-done.md) — the Baseline items each container serves
- [Test Plan](test-plan.md) — how the Checker will be measured
- [Question Log](question-log.md) — the open questions referenced above
