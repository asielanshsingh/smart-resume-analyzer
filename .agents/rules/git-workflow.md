---
trigger: always_on
---

GIT WORKFLOW RULES

Setup
- If no git repo exists, run git init and use branch name main.
- Create .gitignore first: venv/, __pycache__/, *.pyc, .env, instance/, *.db, uploads/, .pytest_cache/, .ruff_cache/, .coverage, htmlcov/, .DS_Store. Never commit secrets, uploaded files or databases.
- Do not modify git config. Use the identity already configured.

Committing
- Commit after each small, working, tested unit of work (one feature, one bug fix, one test group). Never one giant commit.
- Do not commit while tests are failing, unless the commit is explicitly a failing-test-first step.
- Message format: type: short description. Types: feat, fix, test, docs, refactor, chore, style.
- Subject in imperative mood, under 72 characters, no trailing period. Example: fix: reject encrypted PDFs with a clear error
- Add a 1-3 line body only when the why is not obvious.
- Messages must read like a normal developer's. No emojis, no marketing language, no co-author trailers, and no mention of AI, agents, assistants, models, prompts or IDE names.

Bugs
- When you find a bug, fix it in its own fix: commit with a message saying what was wrong and what changed.
- Keep docs/BUGLOG.md: one entry per bug (symptom, cause, fix, commit message). Update it in the same commit as the fix.

Pushing
- Push to origin main after every few commits and at the end of each task, only if a remote named origin exists.
- If a push fails (auth, network, rejected), stop and tell me. Do not retry with other credentials or workarounds.
- Never use force push, reset --hard, rebase on pushed commits, history rewrites, or branch deletion.