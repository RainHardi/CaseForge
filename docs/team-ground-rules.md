# Team Ground Rules

| | |
|---|---|
| **Project** | S1 - Case Study & Portfolio Generator |
| **Repository** | CaseForge |
| **Team** | Team 5 |
| **Development Period** | Fall 2026 Semester |
| **Last Updated** | 23 October 2026 |

These are the working agreements the team follows for the whole semester. They sit on top of the course rules on data, attribution and repositories, which we follow in every case. We update this document when something stops working.

---

## Meetings

- The team will have regular meetings. Regular meeting time: **TBD**.
- Team members should inform the team in advance if they cannot attend.
- Important decisions will be recorded after meetings and shared with everyone, including anyone who missed the meeting.

## Tasks

- Each task will have an owner.
- Each task will have a target date.
- Each task should have a clear definition of what "done" means, agreed before the work starts.
- Team members should communicate problems as early as possible. Nobody is blamed for asking for help; a surprise on the deadline is what hurts the team.
- Tasks can be reassigned if the workload becomes uneven.

## Scope

- The team completes the **Baseline** before starting Target work, and Target before Stretch.
- New ideas are welcome, but they do not delay the Baseline.
- Anything the team has not yet decided is marked **TBD** in the documents and tracked in the [Question Log](./question-log.md).
- The team checks with an instructor or mentor before changing the problem or the Baseline scope.

## Code and Development

- The team uses one public GitHub repository for all code and documents.
- Every member commits their own work, so that each person has a visible record of contribution.
- Commit messages should say what actually changed.
- Important code changes should be reviewed by another team member before merging.
- Team members should explain important changes to other members.
- Documentation and tests should be updated when features change.

## API Keys and Secrets

- No passwords, API keys or other secrets are ever committed to the repository, and none are pasted into notebooks, slides or chat messages.
- Keys are stored in a `.env` file excluded from Git. The repository holds a `.env.example` with blank placeholder values so that others know what to set up.
- If a key is committed by mistake, deleting it from the file is not enough — the key is revoked or rotated immediately.
- The team aims to reach the Baseline on free tiers (Google Gemini through Google AI Studio). If a paid service turns out to be necessary, the team asks the instructors before paying for anything.

## Data

- The team will use only permitted project data.
- Confidential client information will not be used.
- Private company information will not be used.
- Unnecessary personal information will not be collected or shared.
- Permission will be obtained before using classmates' project information, and their material is not published without their agreement.
- Recordings of people, video of people and exported community chat messages are never uploaded to the public repository, even with class-project consent.
- For every data source the team records where it came from, its usage conditions, the collection date or version, whether it contains personal information, and how it was prepared. These records are kept in [Data Sources](./data-sources.md) and summarized in the [README](../README.md).

## AI Tools

- AI-generated code will be reviewed before it is used.
- AI-generated documents will be checked by team members.
- The team records which AI tools were used and for what, in the [README](../README.md).
- The team does not assume AI-generated information is correct; facts and figures are checked against their original sources.
- The sources and licences of any borrowed code, data or writing are recorded.
- The team will not claim that a test has been completed unless it has actually been performed.
- AI-generated content for users must be editable and reviewed by a human before final use.

**For CaseForge itself**, the same principle applies to the product we are building:

- Every generated case study is checked against the original project information. A claim that is not in the input does not go into the output.
- Generated content always stays editable.
- Nothing is finalized or published without a person reviewing and approving it.

## Communication

- Team members communicate clearly and respectfully.
- Questions and problems are raised rather than left unresolved.
- When asking for technical help, explain the problem, the error, and what you have already tried.
- No passwords, API keys or private information in team chats.

## Documentation and Honesty

- Each member documents their own work.
- Project documents should reflect the team's current decisions, not older ones.
- The team does not state that a feature works or a test passed unless it has actually been run.
- Known errors and limitations are recorded honestly — they are part of the result.

---

## In short

Communicate early, keep the Baseline first, handle data and API keys safely, use AI tools responsibly and say so, and never claim something has been done until it actually has.

See [Team Roles & Responsibilities](./team-roles.md) for individual role assignments.
