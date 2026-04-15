# pr-audit-engine

A general-purpose engine for automated PR review against documented repo intent.

Repos accumulate rules — contribution guidelines, architectural invariants, coding standards, safety constraints. Enforcing them consistently across PRs requires either human vigilance or bespoke automation built from scratch per repo. This engine provides the reusable layer: structured evaluation of a PR against the repo’s own documentation, with an AI judgment layer on top of deterministic checks.

The reference implementation is the [Open Brain (OB1)](https://github.com/openmemory/open-brain) repo, which runs a two-layer review pipeline: a deterministic gate checking ~15 structural rules, followed by Claude evaluating mission fit, design patterns, clarity, and scope. This engine extracts that pattern into something any repo can adopt without rebuilding the plumbing.

-----

## How it works

**Layer 1 — Deterministic gate**

Checks that can be expressed as rules without judgment: required files present, metadata valid, no credentials, no dangerous SQL, correct folder structure, PR title format, internal links resolve. These run fast and fail loudly. A PR that can’t pass the gate doesn’t reach the AI layer.

**Layer 2 — AI evaluation**

Reads the PR diff and description against the repo’s documented intent. Evaluates things the gate can’t: whether the contribution actually fits the stated mission, whether the README instructions are clear enough for the target audience, whether design patterns match what the repo declares as correct, whether the scope is right or drifting.

The AI layer is explicitly prompted to reason about:

- **Alignment with documented intent** — does this match what CONTRIBUTING.md, CLAUDE.md, or equivalent docs say the repo is for?
- **Silent failure modes** — does the code fail quietly in ways reviewers are likely to miss?
- **API contracts** — does anything in the diff or unaddressed review comments point to a contract violation?
- **Output correctness** — does the change produce correct results across the edge cases reviewers raised?

**Separation of concerns**

The gate handles what’s checkable. The AI layer handles what requires judgment. Neither substitutes for the other.

-----

## Repo-specific riders

The engine is repo-agnostic. What makes it useful for a specific repo is the **rider** — a config or module that supplies:

- **Invariants** — rules the repo enforces that aren’t universally applicable (e.g., “no local MCP servers,” “pagination must always be complete,” “no modifications to the core `thoughts` table”)
- **Context documents** — CONTRIBUTING.md, CLAUDE.md, architecture docs, or any other docs the AI layer should reason against
- **Prompt anchors** — evaluation focus areas specific to this codebase or contribution category

A default rider ships with the engine and applies general software engineering heuristics. Repos supply their own to get targeted, policy-aware analysis.

-----

## Delivery

The engine is delivery-agnostic. It can run as:

- A **GitHub Action** — triggered on PR open/sync, or on manual dispatch for retrospective review
- A **local script or CLI** — for one-off audits or pre-push checks
- A **Claude skill** — for interactive use inside Claude Code or similar clients

The OB1 reference implementation runs as a GitHub Action (deterministic gate on PR events, Claude review on workflow completion for trusted contributors). Other delivery forms are appropriate for other use cases.

-----

## Directions

Active areas of development beyond the core pattern:

- **CONTRIBUTING.md compliance review** — evaluate merged PRs against declared rules; surface merges that bypassed stated policy after the fact
- **Unresolved comment audit** — fetch merged PRs and identify review comments that were resolved without a corresponding code change; evaluate whether the concern was substantively addressed
- **Pseudocode-to-implementation delta** — compare stated intent in PR description or design comments against what was actually merged
- **Cache regression detection** — identify review comments that flagged caching or memoization behavior; verify the concern was handled
- **Skill formalization** — package the AI evaluation logic as a portable Claude skill

-----

## Status

Early design phase. Pseudocode precedes code. Gaps surface before revisions are written.

The OB1 implementation is the working reference. Generalization into a standalone engine is in progress.

-----

## Contributing

Design proposals and pseudocode welcome. Open an issue before writing implementation.