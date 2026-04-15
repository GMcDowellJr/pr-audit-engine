# pr-audit-engine rider validator

Validates a `pr-audit-rider.yaml` file against the rider schema, reporting
structural errors, incomplete markers, and quality warnings before any
downstream tooling consumes it.

## Prerequisites

- Python 3.11+
- [PyYAML](https://pypi.org/project/PyYAML/) (`pip install pyyaml`)

## Step-by-step instructions

1. Place your rider file at `.github/pr-audit-rider.yaml` in your target
   repository (or any accessible path).

2. Run the validator, passing the path to the rider file as the only
   positional argument:

   ```
   python rider_validate.py .github/pr-audit-rider.yaml
   ```

3. To receive machine-readable output, add `--format json`:

   ```
   python rider_validate.py .github/pr-audit-rider.yaml --format json
   ```

4. Inspect the findings printed to stdout and fix any `ERROR` or `WARN` items
   before proceeding to downstream tools.

## Expected outcome

The script prints a structured findings report and exits with one of three
codes:

| Exit code | Meaning |
|-----------|---------|
| `0` | No errors or warnings — rider is valid |
| `1` | One or more `ERROR` findings — rider must be fixed |
| `2` | One or more `WARN` findings but no errors — rider is usable with caveats |

**Text output example (exit 0):**

```
0 error(s), 0 warning(s), 0 info
```

**Text output example (exit 1):**

```
[ERROR] INTENT_ABSENT: repo_intent marker is ABSENT
[INFO] ANCHORS_ABSENT: attention_anchors not present — recommended but not required

1 error(s), 0 warning(s), 1 info
```

## Troubleshooting

**`FILE_NOT_FOUND` error even though the file exists**
The path argument is resolved relative to the current working directory, not
the script location. Either pass an absolute path or `cd` to the repo root
before running the script.

**`YAML_PARSE_FAILURE` on a file that looks valid**
YAML is whitespace-sensitive. Tab characters are not valid YAML indentation —
replace them with spaces. Also check for unquoted special characters such as
`:` or `#` inside string values.

**`INVALID_MARKER` warning for a marker field**
Each `*_marker` key must be exactly one of `FILLED`, `PARTIAL`, `ABSENT`, or
`INFERRED` (case-sensitive). Any other value — including lowercase variants or
a missing key — triggers this warning and causes the associated semantic checks
to be skipped.

**`INTENT_TOO_SHORT` warning despite a long description**
The check measures the length of the string after stripping leading and
trailing whitespace. Ensure `repo_intent` contains at least 50 characters of
actual content, not just whitespace or newlines.

**`INVARIANT_NOT_FALSIFIABLE` warning on a well-written invariant**
The check looks for assertion verbs: `must`, `must not`, `never`, `always`,
`shall`, `shall not`, `cannot`, `is required to`. Rephrase the invariant to
include one of these verbs to suppress the warning.

## Supported Clients

This is a standalone Python script with no framework dependencies. It runs in
any environment where Python 3.11+ and PyYAML are available:

- Local terminal / shell
- CI pipelines (GitHub Actions, GitLab CI, etc.)
- Docker containers
- Pre-commit hooks

## Installation

No installation step is required beyond ensuring the dependencies are present:

```
pip install pyyaml
```

Copy `rider_validate.py` to any location on your `PATH` or invoke it directly
with `python rider_validate.py`.

## Trigger Conditions

Run this validator:

- **Before opening a PR** that modifies `.github/pr-audit-rider.yaml`
- **In CI** as a gate before any pr-audit-engine analysis step
- **After regenerating a rider file** with the engine's generation tooling to
  confirm the output is well-formed
- **During development** of new rider fields or marker values to catch schema
  regressions early
