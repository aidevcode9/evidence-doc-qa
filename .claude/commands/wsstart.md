---
description: Start working on a new task
---

Start working on a new task.

Steps:
1. Read STATUS.md to see what's in "Next"
2. Read CLAUDE.md to understand project context
3. Ask me which task I want to work on (or I'll tell you)
4. Create a new branch: `git checkout -b feat/[short-description]` or `fix/[short-description]`
5. Move the task from "Next" to "Now" in STATUS.md
6. Enter Plan mode and create a plan for implementing this task:
   - What files need to change?
   - What's the implementation approach?
   - What tests are needed? follow a naming convention.
   - Any risks or concerns?
   - All prompts in their own files to versioned?
   - what telemtry is needed?
   - what key areas should be logged?
   - any variables to add to the .env?
7. Show me the plan and wait for approval before implementing

Don't start coding until I approve the plan.
