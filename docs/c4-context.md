# System Context Diagram (C4 Level 1)

Shows the system as a single box, its users, and the external systems it connects to.

```mermaid
flowchart TB
    User(["Content Editor<br/>Agency staff or student<br/>who owns raw project notes"])

    System["<b>Case Study Generator</b><br/>Turns messy project notes into<br/>a reviewed, formatted case study PDF"]

    LLM[["LLM API<br/>Gemini free tier<br/>Generates structured draft text"]]
    Storage[["File Storage<br/>Stores uploaded notes<br/>and generated PDFs"]]

    User -- "Uploads notes,<br/>reviews & approves draft,<br/>downloads final PDF" --> System
    System -- "Sends notes + prompt,<br/>receives structured text" --> LLM
    System -- "Reads/writes<br/>input files and PDFs" --> Storage

    classDef person fill:#1168bd,color:#fff,stroke:#0b4884,stroke-width:2px
    classDef system fill:#08427b,color:#fff,stroke:#052e56,stroke-width:2px
    classDef external fill:#999999,color:#fff,stroke:#6b6b6b,stroke-width:2px

    class User person
    class System system
    class LLM,Storage external
```

**Legend:** Blue = the system we're building. Gray = external systems outside our control. 
