# Project Overview

## Case Study & Portfolio Generator (S1)

| | |
|---|---|
| **Category** | Software / AI Workflow |
| **Repository** | CaseForge |
| **Team** | Team 5 |
| **Development Period** | Fall 2026 Semester |
| **Status** | Initial Project Plan |

---

## Table of Contents

1. [Project Name](#1-project-name)
2. [Problem](#2-problem)
3. [Target Users](#3-target-users)
4. [How Users Currently Solve the Problem](#4-how-users-currently-solve-the-problem)
5. [Proposed Solution](#5-proposed-solution)
6. [Why AI](#6-why-ai)
7. [Inputs and Outputs](#7-inputs-and-outputs)
8. [Planned Core Features](#8-planned-core-features)
9. [Development Plan](#9-development-plan)
10. [Baseline](#10-baseline)
11. [Target](#11-target)
12. [Stretch](#12-stretch)
13. [Data Sources](#13-data-sources)
14. [Tools and Models](#14-tools-and-models)
15. [Main Technical Challenges](#15-main-technical-challenges)
16. [Testing and Evaluation](#16-testing-and-evaluation)
17. [Expected Final Result](#17-expected-final-result)
18. [Expected Value](#18-expected-value)
19. [Semester Goal](#19-semester-goal)
20. [Current Status](#20-current-status)
21. [Project Documentation](#21-project-documentation)
22. [Final Project Goal](#22-final-project-goal)

---

## 1. Project Name

**S1 - Case Study & Portfolio Generator**

The project repository is called **CaseForge**.

## 2. Problem

Companies can complete strong projects but often fail to present this work clearly after the project is finished.

For service companies, writing a professional case study can be difficult because project information may be spread across rough notes, messages, screenshots, documents, and other sources. Writing the case study is also usually not a direct part of the project work, so nobody may have clear responsibility for doing it.

As a result, companies may have:

- Old or incomplete portfolio information
- No professional case study for completed projects
- Difficulty collecting project information
- Inconsistent writing and formatting
- A large amount of time spent preparing project materials manually

The initial business context for this project is **HumbleBeeAI**, which works in areas such as AI development, R&D, cybersecurity, data science, and software engineering.

## 3. Target Users

### Primary Users

The primary users are service companies that sell their work based on previous projects and results.

The main user inside the company can be a person responsible for business development or marketing.

They need to turn completed project information into professional materials that can be used to present the company's previous work.

### Secondary Users

A faster validation group will be the project team and classmates.

Students often complete projects but do not have a polished case study or portfolio artifact that can be used for job applications or presentations.

## 4. How Users Currently Solve the Problem

Currently, users may collect information manually from different sources and then write the case study themselves.

A typical process can include:

1. Finding project information.
2. Collecting notes, messages, screenshots, and other materials.
3. Selecting useful information.
4. Writing the case study.
5. Checking the information.
6. Formatting the document.
7. Creating a final PDF or presentation.

## 5. Proposed Solution

The team proposes an AI-based Case Study & Portfolio Generator.

The system will take messy and unstructured project information and transform it into a structured professional case study.

The planned workflow is:

```
Messy project input → Fact extraction → Case study writing → Faithfulness check → Human review → Final output
```

The system will first identify information that is actually stated in the source material. It will then use these verified facts to create a professional case study.

> [!IMPORTANT]
> A key requirement is that the system **must not invent information**. For example, if the source material does not contain a specific performance improvement, the system should not create a statement such as: *"The system reduced processing time by 40%."* Instead, missing information should be identified or flagged for human review. A human must review and approve the generated content before it is finalized or published.

## 6. Why AI

AI can help reduce the manual work required to organize and write project information.

The system can use an LLM to:

- Understand unstructured project information
- Extract important facts
- Organize information into a fixed structure
- Generate professional written content
- Check generated claims against the original information
- Identify information that is missing or unsupported

The project will focus on **controlled AI generation**, rather than simply asking an AI model to write a case study.

## 7. Inputs and Outputs

### Inputs

The system may receive:

- Rough project notes
- Project descriptions
- Client problem information
- Work completed
- Development approach
- Tools and technologies
- Challenges
- Results
- Screenshots or project images
- Other messy project information

The team will deliberately test the system with poor or messy inputs. A system that only works with clean and well-written information will not fully solve the intended problem.

### Outputs

The main initial output will be a **professional case study in PDF format**.

Planned additional formats include:

- Portfolio page
- One-page summary
- Partner presentation

The final output should contain only information that can be supported by the provided project information.

## 8. Planned Core Features

The planned system will include the following features:

### Feature 1 - Structured Input Intake

The system will collect information about:

- Client problem
- Work completed
- Approach
- Tools and technologies
- Challenges
- Results
- Images

### Feature 2 - Fact Extraction

The system will extract only facts that are stated in the input. If important information is missing, the system should flag it instead of creating unsupported information.

### Feature 3 - Case Study Generation

The extracted facts will be organized into a fixed case-study structure and converted into professional written content.

### Feature 4 - Automated Faithfulness Check

The system will compare generated claims with the original project information. The purpose is to identify claims that are unsupported by the source information.

### Feature 5 - Human Review

A human must review and approve the generated case study before it is finalized or published.

### Feature 6 - PDF Generation

The approved case study will be converted into a downloadable PDF.

## 9. Development Plan

The team will first build the minimum working version and then improve it based on testing.

The planned development process is:

1. Define the project structure and user workflow.
2. Collect safe project information and test examples.
3. Build the basic input and extraction process.
4. Build the case-study generation process.
5. Add the faithfulness checking process.
6. Add human review and editing.
7. Generate the final PDF.
8. Test the system with different types of project input.
9. Identify errors and limitations.
10. Improve the system based on test results.
11. Prepare the final demonstration and presentation.

## 10. Baseline

The Baseline is the minimum version that the team needs to complete first.

The Baseline will include:

- Project information input
- Extraction of stated facts
- Structured case-study generation
- Basic automated checking of generated claims
- Human review before finalization
- PDF generation

The Baseline will focus on proving that messy project information can be transformed into a useful and professional case study without inventing unsupported claims.

## 11. Target

After completing the Baseline, the team will improve the system toward the Target version.

The Target may include:

- Better handling of messy input
- Improved claim verification
- Better case-study formatting
- Portfolio page generation
- One-page summary generation
- Improved user review and editing
- More testing examples

The exact Target features may be adjusted based on development progress and testing results.

## 12. Stretch

If the Baseline and Target are completed early, the team may consider additional features.

Possible Stretch features include:

- Partner presentation generation
- More output templates
- Improved image placement
- Additional input formats
- More advanced quality checks
- Additional testing with different project types

Stretch features will not be prioritized over completing and testing the Baseline.

## 13. Data Sources

The project will use safe and appropriate project information.

Possible sources include:

- HumbleBeeAI project information that is cleared for external sharing
- Project information constructed by the team
- The team's own capstone project information
- Classmates' project information, with permission

The team will **not** use:

- Client confidential information
- Internal company information that is not approved for use
- Protected or sensitive information without appropriate permission

The project will intentionally collect some poor or messy project inputs for testing because handling such inputs is an important part of the problem.

## 14. Tools and Models

| Area | Tool | Notes |
|---|---|---|
| **AI Model** | Google Gemini (via Google AI Studio) | The team plans to use the free tier so that the project does not require a project budget for AI API usage. |
| **Programming** | Python | Used to build the main workflow and supporting components. |
| **PDF Generation** | ReportLab / WeasyPrint | The final choice may depend on implementation requirements. |
| **Development Environment** | Local development environment / Google Colab | |

> [!NOTE]
> API keys will not be placed directly in the public repository. If an API key is required, the team will use environment variables and an `.env` file.

## 15. Main Technical Challenges

The main technical challenge is preventing the AI from generating information that is not supported by the original project input.

The system needs to distinguish between:

- Information that is explicitly provided
- Information that can be safely reorganized
- Information that is missing
- Information that is unsupported or potentially fabricated

Another challenge is handling messy and incomplete input. The system should still produce useful results when the original information is not written in a professional format.

The team will also need to determine how the faithfulness check should work and how to evaluate whether a generated claim is supported by the source.

## 16. Testing and Evaluation

The team will test the system using different project inputs.

Testing will include both:

- Clean and structured project information
- Poor, incomplete, and messy project information

The main evaluation areas will be:

| # | Evaluation Area | Description |
|---|---|---|
| 1 | **Information Accuracy** | Generated content should match the information provided by the user. |
| 2 | **Claim Faithfulness** | The system should not create unsupported facts, numbers, results, or achievements. |
| 3 | **Output Quality** | The generated case study should have a clear structure and professional writing. |
| 4 | **Handling Missing Information** | The system should identify important missing information instead of automatically inventing it. |
| 5 | **Human Review** | Users should be able to review and edit the generated content before finalization. |
| 6 | **Final Output** | The system should successfully generate the planned PDF output. |

The team will record known errors and limitations during testing.

## 17. Expected Final Result

By the end of the semester, the team aims to develop and demonstrate a working Case Study & Portfolio Generator.

The final prototype should demonstrate the complete workflow:

```
Raw project information → Fact extraction → Case study generation → Faithfulness check → Human review → Final PDF
```

## 18. Expected Value

For service companies, the system can reduce the manual effort required to turn completed projects into professional case studies.

Potential value includes:

- Faster creation of portfolio materials
- More consistent case-study structure
- Better reuse of completed project information
- Easier preparation of business development materials
- Reduced risk of unsupported claims
- More useful project documentation

For students, the system can also help turn completed capstone projects into professional portfolio materials.

## 19. Semester Goal

The team's main goal for the semester is to build, test, and demonstrate a working prototype rather than only prepare a concept.

The team will complete the **Baseline** first, then work toward the **Target** and, if time allows, the **Stretch** features.

The project will be continuously updated as the team learns more from implementation and testing.

## 20. Current Status

The project is currently in the **initial draft stage**.

The team has defined the main problem, target users, proposed solution, planned features, initial data sources, and development direction.

Some technical and implementation details are still **TBD** and will be decided during development and testing.

## 21. Project Documentation

The project documentation will be maintained in the public GitHub repository.

Planned documentation includes:

- [ ] Team Roles & Responsibilities
- [x] Project Overview
- [ ] Team Ground Rules
- [ ] Question Log
- [ ] System Context Diagram (C4 Level 1)
- [ ] Container Diagram (C4 Level 2)
- [ ] Data Sources
- [ ] Test Plan
- [ ] Definition of Done
- [ ] Demo Script
- [ ] README

These documents will be updated as the project develops.

## 22. Final Project Goal

The final goal is to create a practical AI workflow that helps users turn messy project information into professional, reusable case-study and portfolio materials while keeping the generated content faithful to the original information.

> **The most important principle of the project is that the system should improve how project information is presented without inventing what happened.**
