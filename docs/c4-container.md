# Container Diagram (C4 Level 2)

```mermaid
C4Container
    title Container Diagram - Case Study & Portfolio Generator

    Person(user, "Content Editor", "Uploads notes, reviews drafts")

    System_Boundary(system, "Case Study Generator") {
        Container(webapp, "Web/CLI Interface", "Python/Streamlit or CLI", "Collects raw notes, shows draft for review, triggers export")
        Container(pipeline, "Generation Pipeline", "Python", "Builds prompts, calls LLM API, applies missing-info flags")
        Container(reviewstore, "Draft Store", "SQLite/JSON files", "Holds drafts pending human review and approval status")
        Container(pdfgen, "PDF Renderer", "Python (ReportLab/WeasyPrint)", "Renders approved draft into final templated PDF")
    }

    System_Ext(llm, "LLM API", "Generates structured text from prompt + notes (Gemini free tier)")

    Rel(user, webapp, "Uploads notes / reviews & edits draft")
    Rel(webapp, pipeline, "Sends raw notes for structuring")
    Rel(pipeline, llm, "Prompt + notes -> structured draft")
    Rel(pipeline, reviewstore, "Saves draft awaiting review")
    Rel(webapp, reviewstore, "Reads draft for review, writes approval")
    Rel(webapp, pdfgen, "Triggers export once approved")
    Rel(pdfgen, user, "Delivers final PDF")
```
