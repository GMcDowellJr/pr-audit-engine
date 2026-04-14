# pr-audit-engine — Pseudocode

## Overview

Two modules and a set of entry points. `rider_prepass` drafts or refreshes the
repo-specific rider. `audit_pr` runs the post-merge evaluation. Both modules
are delivery-agnostic — they describe logic, not implementation.

-----

## Module: `rider_prepass(repo_path, existing_rider=None)`

Reads repo docs and recent PR history to draft a rider file. Presents the draft
for approval before saving. Does not write without confirmation.

### Step 1 — Gather raw material

Read the following from the repo:

- `CONTRIBUTING.md`
- `README.md`
- Any `*.md` files in `/docs`
- Any schema files
- Any config files that express invariants

Fetch from GitHub:

- Recent merged PRs — limit 10
- Review comments for each of those PRs

### Step 2 — Build prepass prompt

Assemble a prompt containing:

- The repo docs collected above
- The recent PR review comments
- An instruction to draft a rider with three sections:
1. **Intent** — what this repo does and what good looks like (2–4 sentences)
1. **Invariants** — things that must always be true (bullet list)
1. **Attention anchors** — specific problem patterns to watch for, inferred
   from the docs and from patterns in past review comments

If `existing_rider` is provided, include it and add:

> “Here is the current rider. Flag anything that appears stale.”

### Step 3 — Call LLM

```
draft_rider ← llm_call(prompt, model=CAPABLE)
```

### Step 4 — Present and confirm

Present the draft to the user. Do not save without explicit confirmation.

On confirmation:

```
save(draft_rider → rider.md)
```

-----

## Module: `audit_pr(pr_number, rider_path)`

Fetches a merged PR, evaluates the diff against the rider, and produces a
markdown report. Unresolved PR comments are included as a secondary input
alongside independent diff evaluation.

### Step 1 — Fetch PR data

|Variable  |Source                  |Notes                                                                                                                                 |
|----------|------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
|`diff`    |`gh pr diff <n>`        |Full diff as formatted string                                                                                                         |
|`pr_meta` |`gh pr view <n>`        |Title, description, merge date                                                                                                        |
|`comments`|GitHub REST comments API|All review comments; `is_resolved` defaults to `false` in v1 (REST limitation — upgrade to GraphQL for authoritative resolution state)|

**Comment shape (internal, v1):**

```
Comment {
  body:        string
  path:        string
  line:        number
  author:      string
  is_resolved: boolean   // always false in v1 (REST); authoritative in v2 (GraphQL)
  is_outdated: boolean   // always false in v1 (REST); authoritative in v2 (GraphQL)
  source:      "rest" | "graphql"
}
```

### Step 2 — Load rider

```
rider ← read_file(rider_path)
```

### Step 3 — Check rider staleness

Heuristic check: does the diff touch files or patterns that the rider’s
invariants reference? If yes, set a staleness hint — flag in report but do not
block evaluation.

> This is a heuristic in v1. A more robust version would run a mini LLM call
> to compare diff against rider and flag divergence.

### Step 4 — Build evaluation prompt

Assemble the following in order:

1. Rider contents (intent + invariants + attention anchors)
1. PR metadata (title, description)
1. Full diff
1. Unresolved comments (may be empty — that is fine)
1. Evaluation instructions:

> Evaluate this merged PR against the repo intent and invariants above.
> 
> Reason explicitly about: API contracts, silent failure modes, output
> correctness, data loss risk, pagination completeness.
> 
> Do not assess code style unless it indicates a correctness risk.
> 
> For each finding:
> 
> - State what the concern is
> - Cite the specific diff location
> - State why it matters relative to repo intent
> - Suggest a concrete follow-up action
> - Tag source: `UNRESOLVED_COMMENT` or `INDEPENDENT_EVAL`
> - Tag severity: `HIGH`, `MEDIUM`, or `LOW`
> 
> If there are no concerns, say so explicitly. Do not manufacture findings.

If staleness hint was triggered, append:

> Note: the rider may not reflect recent changes to `<X>`. Flag if relevant.

If using REST comment fetch (v1), append:

> These comments may or may not have been formally resolved. Evaluate whether
> each appears addressed by the diff. If the diff clearly fixes the concern,
> note it as likely resolved.

### Step 5 — Call LLM

```
raw_report ← llm_call(prompt, model=CAPABLE)
```

### Step 6 — Render report

Render a markdown report with the following structure:

```
# PR Audit — #{pr_number}: {pr_meta.title}
Merged: {merge_date}
Rider: {rider_path} {[STALENESS WARNING] if triggered}

## Findings
{raw_report}

## Suggested Follow-Up Scope
{derived from HIGH severity findings}
```

Output to console. Optionally save to `/audit-reports/pr-{number}.md`.

-----

## Entry Points

|Invocation                           |Resolves to                                             |
|-------------------------------------|--------------------------------------------------------|
|`audit PR <number>`                  |`audit_pr(number, default_rider_path)`                  |
|`draft rider for <repo>`             |`rider_prepass(repo_path)`                              |
|`refresh rider`                      |`rider_prepass(repo_path, existing_rider=current_rider)`|
|`audit PR <number> with rider <path>`|`audit_pr(number, specified_rider_path)`                |


> The `with rider <path>` form supports multi-repo use. One engine, multiple
> riders.

-----

## Open Items

|Item                        |Status        |Notes                                                                                         |
|----------------------------|--------------|----------------------------------------------------------------------------------------------|
|Diff size handling          |Unresolved    |Large PRs may overflow context window. No truncation strategy yet.                            |
|`model=CAPABLE`             |Placeholder   |Probably Sonnet via OpenRouter. Make configurable in rider or as a flag.                      |
|Severity definition         |Not formalized|HIGH/MEDIUM/LOW left to LLM judgment in v1.                                                   |
|Rider staleness detection   |Heuristic only|Real signal deferred — would require a mini LLM call.                                         |
|GraphQL migration           |Deferred      |Swap `fetch_unresolved_comments` and update `comment_resolution_mode` flag. One-hour refactor.|
|Comment resolution mode flag|Not yet added |Add to rider or config: `comment_resolution_mode: inferred | authoritative`                   |
