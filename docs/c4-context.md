# System Context Diagram (C4 Level 1)

```mermaid
C4Context
    title System Context Diagram - Case Study & Portfolio Generator

    Person(user, "Content Editor", "Agency staff or student who owns the raw project notes")

    System(generator, "Case Study Generator", "Turns messy notes into a reviewed, formatted case study PDF")

    System_Ext(llm, "LLM API", "Generates structured draft text from raw notes (Gemini free tier)")
    System_Ext(storage, "File Storage", "Stores uploaded notes and generated PDFs (local disk or cloud bucket)")

    Rel(user, generator, "Uploads notes, reviews/edits draft, downloads final PDF")
    Rel(generator, llm, "Sends notes + prompt, receives structured draft text")
    Rel(generator, storage, "Reads/writes input files and output PDFs")
```
