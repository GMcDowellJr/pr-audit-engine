# Python Project Template — CI + Guardrails

This repository is a **starter template** for Python projects that want:
- automated quality checks from day one
- fast local iteration
- early detection of error-handling and semantic drift issues

It is intentionally **minimal and opinionated**.

---

## What this template guarantees

From the first commit:

- ✅ **Continuous Integration (CI)** runs on every push and pull request
- ✅ **Linting** catches common correctness and robustness issues
- ✅ **Tests** must pass before code can be merged
- ✅ Rules are **explicit, versioned, and automated**
- ✅ “Works on my machine” failures are reduced by clean CI environments

This template focuses on **how code is merged**, not what the code does.

---

## What this template does *not* guarantee

- ❌ Correct algorithms or domain logic
- ❌ Complete test coverage
- ❌ Optimal performance
- ❌ Freedom from design mistakes

Those emerge during design and integration.  
The goal here is to make problems **visible early and cheaply**, not to eliminate them magically.

---

## Included tooling

- **pytest** — automated tests
- **ruff** — fast static analysis (linting)
- **GitHub Actions** — CI execution
- **pyproject.toml** — single source of tool configuration

All tooling is optional to extend, but none is optional to bypass once enabled.

---

## Repository structure (baseline)

- `.github/workflows/ci.yml`  
  CI pipeline (lint + tests on PRs and pushes)

- `pyproject.toml`  
  Tool configuration (ruff, pytest)

- `requirements-dev.txt`  
  Development dependencies (testing, linting)

- `tests/`  
  Test suite (starts minimal; grows over time)

- `CONTRIBUTING.md`  
  Contribution and workflow rules

---

## Local setup

Create and activate a virtual environment:

    python -m venv .venv
    source .venv/Scripts/activate   # Windows (Git Bash)
    python -m pip install --upgrade pip
    pip install -r requirements-dev.txt
    if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

Run checks locally:

    ruff check .
    pytest

CI will run the same checks automatically.

---

## Development workflow (expected)

1. Create a feature branch
2. Make changes
3. Run:
   - ruff check .
   - pytest
4. Commit and push
5. Open a pull request
6. Merge only when CI is green

If CI fails, the code is not ready to merge.

---

## Design philosophy

This template assumes:

- Bugs are cheaper to fix when found early
- Silent failures are worse than loud ones
- Inconsistency spreads unless actively constrained
- Automation beats memory and good intentions

It is designed to **support adversarial review**, not replace it.

---

## When to extend this template

Add rules or tooling only when:
- the same issue has appeared in multiple projects
- the rule is clearly non-project-specific
- the cost of enforcement is lower than the cost of drift

Keep the template boring. Let projects be interesting.

---

## Using this repository as a template

This repository is intended to be marked as a **GitHub template repository**.
New projects should be created from it rather than copied manually.

Each new repository gets:
- a fresh Git history
- the same guardrails
- freedom to evolve independently

---

## Questions this template intentionally answers

- “How do we know code is safe to merge?”
- “What runs automatically, and when?”
- “What rules are non-negotiable?”

Questions it intentionally does not answer:

- “Is this the best design?”
- “Is this fast enough?”
- “Is this the right abstraction?”

Those belong to design and review—not scaffolding.

---

If this README ever needs to explain *why* the rules exist, the template has already failed.
