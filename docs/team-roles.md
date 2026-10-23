# Team Roles & Responsibilities

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator |
| **Repository** | CaseForge |
| **Category** | Software / AI Workflow |
| **Team** | Team 5 |
| **Members** | 5 |
| **Status** | Midterm draft — design complete, implementation not yet started |
| **Development Period** | Fall 2026 Semester |
| **Last Updated** | 23 October 2026 |

---

## Table of Contents

1. [Team Members and Roles](#1-team-members-and-roles)
2. [Mukhammadkodir - Project Manager](#2-mukhammadkodir---project-manager)
3. [Abdulaziz - AI / Engineering](#3-abdulaziz---ai--engineering)
4. [Dilshodjon - Problem & Business](#4-dilshodjon---problem--business)
5. [Odina - Data & Research](#5-odina---data--research)
6. [Anvarbek - Demo & Presentation](#6-anvarbek---demo--presentation)
7. [Team Responsibilities](#7-team-responsibilities)
8. [Team Ground Rules](#8-team-ground-rules)
9. [Task Ownership](#9-task-ownership)
10. [Development Responsibilities During the Semester](#10-development-responsibilities-during-the-semester)
11. [Team Role Summary](#11-team-role-summary)
12. [Final Team Goal](#12-final-team-goal)

---

## 1. Team Members and Roles

| Team Member | Assigned Role | Main Responsibility |
|---|---|---|
| Mukhammadkodir | Project Manager | Project planning, schedule, milestones, tasks, submissions, and team coordination |
| Abdulaziz | AI / Engineering | AI workflow, application development, technical implementation, claim verification, and C4 diagrams |
| Dilshodjon | Problem & Business | Problem definition, target users, business value, and user feedback |
| Odina | Data & Research | Data sources, testing, verification, research, error analysis, and limitations |
| Anvarbek | Demo & Presentation | README, documentation, demo video, presentation, and final demonstration |

## 2. Mukhammadkodir - Project Manager

### Main Responsibilities

- Manage the overall project schedule.
- Set milestones and target dates.
- Assign tasks to team members.
- Track the progress of each task.
- Coordinate project submissions.
- Organize team meetings and decisions.
- Make sure the team completes the Baseline before focusing on additional features.
- Coordinate communication between team members.
- Maintain the Question Log with the team.
- Help maintain GitHub repository rules and documentation.
- Make sure project materials follow the course requirements.
- Report important blockers or delays to the team.

### Current Tasks (October 2026)

- Agree target dates for the remaining Baseline tasks BT-1 to BT-8, which are currently TBD.
- Coordinate the midterm Business Plan draft and its submission.
- Keep the Question Log up to date as decisions are made.
- Track progress against the Baseline and report blockers early.
- Make sure every member has a visible record of contribution in the repository.

## 3. Abdulaziz - AI / Engineering

### Main Responsibilities

- Build and maintain the technical part of the project.
- Set up and maintain the development environment.
- Managing GitHub repository rules
- Develop the AI workflow.
- Implement the project information input process.
- Develop the extraction step that identifies stated facts.
- Develop the AI writing/generation step.
- Implement the automated faithfulness check.
- Develop the logic for identifying unsupported information.
- Help implement the PDF generation system.
- Develop and maintain the main application.
- Create the C4 Level 1 System Context diagram.
- Create the C4 Level 2 Container diagram.
- Test the technical implementation.
- Work with Data & Research on testing methods and evaluation.

### Completed

- Created and organized the GitHub repository and added links to the project documents.
- Prepared the C4 Level 1 System Context and Level 2 Container diagrams (first versions).
- Defined the initial technical workflow.

### Current Tasks (October 2026)

- Revise the C4 diagrams: add the faithfulness-check container, align the storage boundary between Level 1 and Level 2, and add the Draft Store to PDF Renderer link.
- **BT-1** — set up the code structure and `requirements.txt`, and get a working Gemini API call.
- **BT-3** — build the fact extraction step.
- **BT-4** — build the automated faithfulness check.
- **BT-5** — build the human review and approval step.
- **BT-6** — build PDF and one-page summary generation.
- Confirm the Google Gemini free-tier rate limits and the starter template choice.
- Decide between ReportLab and WeasyPrint for PDF generation.

### Important Technical Focus

> [!IMPORTANT]
> The main technical challenge is preventing the AI from creating unsupported claims. For example, the system should not create a statement such as: *"Reduced processing time by 40%"* if this information was not included in the original project input.

## 4. Dilshodjon - Problem & Business

### Main Responsibilities

- Define the main business problem.
- Define the target users.
- Identify the main buyer.
- Research how users currently create case studies.
- Define the business value of the system.
- Explain why the problem is important.
- Identify potential user benefits.
- Collect and organize user feedback.
- Help define the value proposition.
- Connect the technical solution with the business problem.
- Help prepare the business part of the final presentation.

### Primary Business Context

The initial business context is services companies such as **HumbleBeeAI**, including companies working in areas such as:

- AI development
- R&D
- Cybersecurity
- Data science
- Software engineering

The expected buyer is the person responsible for business development or marketing.

### Secondary Users

The secondary users are:

- Our team
- Classmates
- Other permitted student users

These users can provide fast and realistic feedback because they also complete projects that can be turned into portfolio materials.

### Completed

- Problem definition, primary and secondary users, buyer, current manual process and business value, recorded in the [Project Overview](project-overview.md) and the weekly business worksheets.

### Current Tasks (October 2026)

- Write Sections 1 to 3 of the midterm Business Plan (Company Overview, Problem & Solution, Target Market) from the weekly worksheets.
- Prepare questions for user feedback.
- Confirm the pricing and business model assumptions used in the TAM analysis.

## 5. Odina - Data & Research

### Main Responsibilities

- Identify suitable data sources.
- Check data usage conditions.
- Confirm that data can be used for the project.
- Prepare safe project information for testing.
- Document data sources and permissions.
- Prepare test cases.
- Create both clean and messy project inputs.
- Define criteria for testing and verification.
- Check whether generated claims are supported by the original input.
- Analyze system errors.
- Document system limitations.
- Support user testing.
- Work with AI / Engineering on technical evaluation.

### Planned Data Sources

The team plans to use:

- HumbleBeeAI project information that is cleared for external sharing.
- Project information constructed by the team.
- Our own capstone project information.
- Classmates' capstone project information with permission.

### Data Restrictions

The team will **not** use:

- Client confidential material.
- Internal company data.
- Protected information.

### Important Research Focus

The team will deliberately collect poor and messy project inputs early in development.

This is important because the main problem is not only creating a case study from clean information. The system should also be able to handle the type of messy information that users actually provide.

### Completed

- [Data Sources](data-sources.md) and [Test Plan](test-plan.md) written and committed.

### Current Tasks (October 2026)

- **BT-2** — prepare three real project inputs with hand-written fact lists and commit them.
- **BT-8** — run the manual claim check on every test case once generation works.
- Request permission from HumbleBeeAI for project information cleared for external sharing (**Q-D01**).
- Confirm whether Google's free-tier terms allow sending real project information (**Q-D02**).
- Add collection dates and versions to the Data Sources document.
- Decide the target catch rate for the automated faithfulness check (**Q-T01**).
- Write Sections 7 and 9 of the midterm Business Plan.

## 6. Anvarbek - Demo & Presentation

### Main Responsibilities

- Create and maintain the README.
- Maintain project documentation.
- Organize project documents and links.
- Prepare the demo flow.
- Prepare the demo script.
- Record and edit the demo video.
- Show the complete process from messy input to final output.
- Prepare presentation slides.
- Connect the technical system with the business problem.
- Explain the system clearly to non-technical users.
- Prepare the final project demonstration.

### Completed

- README and project documentation structure.

### Current Tasks (October 2026)

- Write the Definition of Done, Demo Script and Question Log documents.
- Write Sections 4, 5, 8 and 10 of the midterm Business Plan.
- Run the comparison test: the same messy project notes through a general AI tool and through our planned workflow, recording every claim that was not in the input.
- Prepare the demo flow and the presentation structure.

## 7. Team Responsibilities

Although each member has a main role, the project is a team project.

All members are responsible for:

- Understanding the main problem.
- Understanding the target users.
- Understanding the main system features.
- Communicating with other team members.
- Completing assigned tasks on time.
- Reporting problems early.
- Reviewing important work when needed.
- Updating documentation related to their work.
- Testing their own work.
- Contributing to the final presentation.
- Contributing to the final project demonstration.

Each feature owner will work with the Data & Research member to agree on how the feature will be tested.

## 8. Team Ground Rules

Our working agreements — meetings, task handling, GitHub and code review, API keys and secrets, data permissions, AI tool use, communication, and honesty about what has actually been tested — are kept in a single document so that they cannot drift apart from this one:

**[Team Ground Rules](team-ground-rules.md)**

Every member is expected to have read them.

## 9. Task Ownership

| Task | Owner | Reviewer / Support | Status |
|---|---|---|---|
| GitHub repository | Abdulaziz | Team | Created |
| Team R&R (this document) | Mukhammadkodir | Team | Complete, updated 23 Oct |
| Project Overview | Dilshodjon | Mukhammadkodir / Team | Complete, updated 23 Oct |
| README | Anvarbek | Mukhammadkodir / Team | Complete, updated 23 Oct |
| Team Ground Rules | Team | Mukhammadkodir | Draft — needs updating |
| Data Sources | Odina | Abdulaziz | Complete — collection dates still to add |
| Test Plan | Odina | Abdulaziz | Complete |
| C4 Level 1 | Abdulaziz | Team | Complete — revision needed |
| C4 Level 2 | Abdulaziz | Team | Complete — revision needed |
| Definition of Done | Anvarbek | Team | **Not started** |
| Demo Script | Anvarbek | Team | **Not started** |
| Question Log | Mukhammadkodir / Team | Team | **Not started** |
| Midterm Business Plan | Team | Mukhammadkodir | In progress — due 24 Oct |
| Baseline implementation (BT-1 to BT-8) | See below | Team | **Not started** |

### Baseline implementation ownership

No code has been written yet. The remaining Baseline tasks, with completion criteria, are listed in the [Project Overview](project-overview.md#21-current-status-and-next-steps). Ownership:

| Member | Baseline tasks |
|---|---|
| Abdulaziz | BT-1 setup and Gemini call, BT-3 fact extraction, BT-4 faithfulness check, BT-5 review and approval, BT-6 PDF and one-page summary |
| Odina | BT-2 three test inputs with fact lists, BT-8 manual claim check on every test case |
| Team | BT-7 end-to-end run on three real inputs |
| Mukhammadkodir | Agreeing target dates, tracking progress, reporting blockers |
| Dilshodjon | User feedback and business validation once a draft output exists |
| Anvarbek | Demo scenario, documentation, recording what breaks during testing |

Target dates are **TBD** until the team agrees a schedule.

### Contribution records

Individual contributions are visible in the repository's commit history:
[github.com/RainHardi/CaseForge/graphs/contributors](https://github.com/RainHardi/CaseForge/graphs/contributors)

## 10. Development Responsibilities During the Semester

The team will continue working on the project throughout the Fall 2026 semester.

### Initial Stage

The team will:

- Finalize the project requirements.
- Confirm the system architecture.
- Confirm data sources.
- Prepare test data.
- Define the testing method.

### Development Stage

The team will:

- Build the input system.
- Build the extraction process.
- Build the AI writing process.
- Build the faithfulness-checking process.
- Build the human review process.
- Build PDF generation.
- Develop the portfolio page and other planned outputs.

### Testing Stage

The team will:

- Test the system with project examples.
- Test messy and incomplete inputs.
- Check generated claims.
- Conduct user testing.
- Measure the time required to create case studies.
- Record errors and limitations.
- Improve the system based on test results.

### Final Stage

The team will:

- Complete the working system.
- Finalize documentation.
- Prepare the final demo.
- Prepare the presentation.
- Demonstrate the complete workflow.

## 11. Team Role Summary

| Member | Role | Main Focus |
|---|---|---|
| Mukhammadkodir | Project Manager | Planning, schedule, tasks, submissions, coordination |
| Abdulaziz | AI / Engineering | AI workflow, application, claim verification, technical development |
| Dilshodjon | Problem & Business | Problem, users, buyer, business value, feedback |
| Odina | Data & Research | Data, testing, verification, research, errors |
| Anvarbek | Demo & Presentation | README, documentation, demo, presentation |

## 12. Final Team Goal

By the end of the semester, the team will aim to have a working, tested, and demonstrable Case Study & Portfolio Generator.

The team will work together from the initial planning stage through development, testing, improvement, and final presentation.
