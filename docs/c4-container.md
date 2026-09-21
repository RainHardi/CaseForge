# Container Diagram (C4 Level 2)

Shows the main applications and data stores inside the system, their responsibilities, and how they communicate. External APIs are shown outside the system boundary.

```mermaid
flowchart TB
    User(["Content Editor"])

    subgraph Boundary["Case Study Generator — System Boundary"]
        direction TB
        WebApp["<b>Web/CLI Interface</b><br/>Python / Streamlit or CLI<br/>Collects notes, shows draft<br/>for review, triggers export"]
        Pipeline["<b>Generation Pipeline</b><br/>Python<br/>Builds prompts, calls LLM API,<br/>applies missing-info flags"]
        ReviewStore[("<b>Draft Store</b><br/>SQLite / JSON files<br/>Holds drafts pending<br/>review and approval status")]
        PdfGen["<b>PDF Renderer</b><br/>Python — ReportLab / WeasyPrint<br/>Renders approved draft<br/>into final templated PDF"]
    end

    LLM[["LLM API — Gemini free tier<br/>(outside system boundary)"]]

    User -- "Uploads notes /<br/>reviews & edits draft" --> WebApp
    WebApp -- "Sends raw notes<br/>for structuring" --> Pipeline
    Pipeline -- "Prompt + notes →<br/>structured draft" --> LLM
    Pipeline -- "Saves draft<br/>awaiting review" --> ReviewStore
    WebApp -- "Reads draft for review,<br/>writes approval" --> ReviewStore
    WebApp -- "Triggers export<br/>once approved" --> PdfGen
    PdfGen -- "Delivers final PDF" --> User

    classDef person fill:#1168bd,color:#fff,stroke:#0b4884,stroke-width:2px
    classDef container fill:#438dd5,color:#fff,stroke:#2d6ca8,stroke-width:2px
    classDef store fill:#438dd5,color:#fff,stroke:#2d6ca8,stroke-width:2px,stroke-dasharray: 4 2
    classDef external fill:#999999,color:#fff,stroke:#6b6b6b,stroke-width:2px

    class User person
    class WebApp,Pipeline,PdfGen container
    class ReviewStore store
    class LLM external
```

**Legend:** Light blue = containers inside our system. Dashed border = a data store. Gray = external API, outside our system boundary.
