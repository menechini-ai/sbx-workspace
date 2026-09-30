# CLAUDE.md

## Workflow Orchestration

### 1. Plan Mode Default

-   Enter plan mode for ANY non-trivial task (3+ steps or architectural
    decisions).
-   If something goes sideways, STOP and re-plan immediately --- don't
    keep pushing.
-   Use plan mode for verification steps, not just building.
-   Write detailed specs upfront to reduce ambiguity.

### 2. Subagent Strategy

-   Use subagents liberally to keep the main context window clean.
-   Offload research, exploration, and parallel analysis to subagents.
-   For complex problems, throw more compute at it via subagents.
-   One task per subagent for focused execution.

### 3. Self-Improvement Loop

-   After ANY correction from the user: update `tasks/lessons.md` with
    the pattern.
-   Write rules for yourself that prevent the same mistake.
-   Ruthlessly iterate on these lessons until mistake rate drops.
-   Review lessons at session start for the relevant project.

### 4. Verification Before Done

-   Never mark a task complete without proving it works.
-   Diff behavior between main and your changes when relevant.
-   Ask yourself: "Would a Staff engineer approve this?"
-   Run tests, check logs, and demonstrate correctness.

### 5. Demand Elegance (Balanced)

-   For non-trivial changes: pause and ask, "Is there a more elegant
    way?"
-   If a fix feels hacky: "Knowing everything I know now, implement the
    elegant solution."
-   Skip this for simple, obvious fixes --- don't over-engineer.
-   Challenge your own work before presenting it.

### 6. Autonomous Bug Fixing

-   When given a bug report: just fix it. Don't ask for hand-holding.
-   Point at logs, errors, and failing tests --- then resolve them.
-   Zero context switching required from the user.
-   Go fix failing CI tests without being told how.


### 7. AI Memory

- **Always use AI Memory** for project memory, context, decisions, lessons, and relevant persistent knowledge.
- Follow the AI Memory documentation and workflow: https://github.com/akitaonrails/ai-memory/tree/main/docs
- Before starting relevant work, check existing AI Memory context instead of assuming prior decisions or rediscovering information.
- After meaningful corrections, architectural decisions, discoveries, or reusable lessons, update the AI Memory accordingly.
- Keep project memory organized, concise, and focused on information that will be useful in future sessions.

## Task Management

1.  **Plan First:** Write the plan to `tasks/todo.md` with checkable
    items.
2.  **Verify Plan:** Check in before starting implementation.
3.  **Track Progress:** Mark items complete as you go.
4.  **Explain Changes:** Provide a high-level summary at each step.
5.  **Document Results:** Add a review section to `tasks/todo.md`.
6.  **Capture Lessons:** Update `tasks/lessons.md` after corrections.

### 8. Development Flow: SPEC → TDD → TASK → CODING → REFACTOR → LINTER → SAFETY

Always follow this development flow for non-trivial changes:

1. **SPEC:** Define the requirement, acceptance criteria, constraints, assumptions, and expected behavior before implementation.
2. **TDD:** Write or update tests before implementation whenever practical. Tests should express expected behavior and edge cases.
3. **TASK:** Break the work into small, checkable tasks and track them in `tasks/todo.md`.
4. **CODING:** Implement the smallest correct solution that satisfies the specification and tests.
5. **REFACTOR:** After tests pass, review the implementation and improve structure, readability, duplication, maintainability, and design without changing intended behavior.
6. **LINTER:** Run formatters, linters, static analysis, and type checks where applicable. Fix reported issues instead of suppressing them without justification.
7. **SAFETY:** Before declaring completion, review security, privacy, data handling, dependency risks, error handling, permissions, secrets, input validation, and potentially destructive operations.

- Do not skip a stage without a clear reason.
- If a stage reveals a problem, stop, update the plan/specification as necessary, and continue from the appropriate stage.
- **Definition of Done:** specification satisfied, tests passing, refactor reviewed, lint/type checks passing, and safety considerations verified.

## Core Principles

-   **Simplicity First:** Make every change as simple as possible.
    Impact minimal code.
-   **No Laziness:** Find root causes. No temporary fixes. Senior
    developer standards.
-   **Minimal Impact:** Changes should only touch what's necessary.
    Avoid introducing bugs.

