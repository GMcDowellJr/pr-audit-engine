# Contributing Guidelines

This repository enforces a **branch + CI–gated workflow**.
Changes are expected to be small, reviewable, and verifiable.

These rules exist to prevent silent failure, semantic drift, and
“works on my machine” regressions.

---

## Development workflow (required)

1. **Create a branch**
   - One branch per change or logical unit of work.
   - Do not commit directly to `main`.

2. **Make changes**
   - Keep commits focused.
   - Avoid mixing unrelated concerns.

3. **Run checks locally**
   Before committing, run:

       ruff check .
       pytest

4. **Commit**
   - Use clear, factual commit messages.
   - Prefer one concern per commit.

5. **Push and open a Pull Request**
   - CI will run automatically.
   - The PR must be green before merging.

---

## Commit message guidance

Use a simple, consistent format:

    <type>: <short description>

Recommended types:
- `ci` — CI configuration or automation
- `chore` — tooling, config, dependencies
- `docs` — documentation only
- `test` — tests only
- `fix` — bug fixes
- `feat` — new functionality

Avoid:
- “wip”
- “stuff”
- “misc”
- “initial commit” (except the literal first commit)

---

## Error handling expectations

- No bare `except`.
- Exceptions must either:
  - be logged with context and re-raised, or
  - follow an explicit, documented policy (fail / skip / degrade).
- Silent failure is considered a bug.

---

## Tests

- New behavior or policy changes should include tests.
- Tests should cover failure modes when feasible, not just happy paths.
- CI is the source of truth; local success does not override CI failure.

---

## Merging

- Pull requests must pass CI before merging.
- If CI fails, fix the issue or explain why the rule should change.
- Bypassing CI defeats the purpose of this repository.

---

## Scope of these rules

These guidelines define **how changes are merged**, not what the
correct design or implementation should be.

Design quality is handled through review; correctness gates are handled
through automation.