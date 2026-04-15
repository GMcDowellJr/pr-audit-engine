#!/usr/bin/env python3
"""pass1_extract_llm.py — LLM extraction component of pr-audit-engine."""

import argparse
import json
import os
import sys
from pathlib import Path

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000
MIN_COMPRESSION_BYTES = 0  # placeholder — calibrate against RDI
                            # directional intent: compress mid-size
                            # and up (~2000 bytes / ~400 words)

MARKER_KEYS = [
    "repo_intent_marker",
    "invariants_marker",
    "failure_mode_categories_marker",
    "attention_anchors_marker",
    "context_docs_marker",
    "staleness_hints_marker",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="LLM extraction component of pr-audit-engine."
    )
    parser.add_argument(
        "fetch_dir",
        help="Path to pass1_extract_pre output directory (must contain consolidated.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write prompts to disk instead of calling the LLM",
    )
    return parser.parse_args()


def call_llm(system_prompt, user_prompt, api_key):
    try:
        import anthropic
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The 'anthropic' package is required for live LLM calls. "
            "Install dependencies (for example: `pip install anthropic`)."
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def get_yaml_module():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The 'PyYAML' package is required for YAML parsing/writing. "
            "Install dependencies (for example: `pip install pyyaml`)."
        ) from exc

    return yaml


def compress_doc(file, api_key):
    system_prompt = """You are compressing a repository document for use as context
in a code review tool. Extract and preserve:
  - All normative statements (must, never, always, required,
    prohibited, not allowed)
  - All structural descriptions (what modules exist, what
    each does, how they relate)
  - All explicit scope boundaries (what the repo does NOT do)
  - All process requirements (PR format, review gates,
    contribution rules)

Discard:
  - Motivational or marketing language
  - Repeated explanations of the same concept
  - Examples that do not add new information
  - Meta-commentary about the document itself

Output plain prose. No headers. No lists. No markdown.
Be aggressive — target 30% of original length.
Preserve meaning over brevity when they conflict.
"""
    user_prompt = f"Document: {file['path']}\n\n{file['content']}\n\nCompress now."

    try:
        return call_llm(system_prompt, user_prompt, api_key)
    except Exception as e:
        print(
            f"WARN: Compression failed for {file['path']}: {e}"
            " — using uncompressed content",
            file=sys.stderr,
        )
        return file["content"]


def build_system_prompt():
    return """You are analyzing a software repository to produce a structured
evaluation rider — a YAML document that captures the repo's intent,
hard invariants, and failure mode categories for use in automated
PR review.

You will be given the contents of key repository documents.
Your job is to extract signal, not summarize prose.

Documents are provided as a JSON array in the user message. Each
entry has path, inject_strategy, size_bytes, and content fields.

Weighting rules by inject_strategy:
  full      — normative documents. Treat statements here as
              authoritative constraints. Ground all invariants
              and failure modes in these files first.
  summary   — structural context. Use to understand the system
              and populate attention_anchors and context_docs.
              Do not elevate to invariant without full support
              from a full-strategy document.
  reference — existence noted only. content will be null.
              Do not use as evidence.

Output ONLY valid YAML matching the schema below.
No preamble. No explanation. No markdown fences.
If you cannot fill a field from the available evidence,
set its _marker to ABSENT and its value to null.
Never invent invariants or failure modes not supported
by evidence in the provided documents.

SCHEMA:

schema_version: 1
generated_at: <ISO timestamp>
generated_against_sha: null
passes_run: [pass1]

repo_intent_marker: <FILLED|PARTIAL|ABSENT|INFERRED>
repo_intent: |
  <What does this repo do? What is it explicitly NOT doing?
   What does correctness mean for its core output?>

invariants_marker: <FILLED|PARTIAL|ABSENT|INFERRED>
invariants:
  - <Each invariant must be falsifiable — contains must/never/
     always/shall/cannot. Specific to this repo. Consequential
     — violation causes incorrect output, silent data loss,
     or broken API contract.>

failure_mode_categories_marker: <FILLED|PARTIAL|ABSENT|INFERRED>
failure_mode_categories:
  - name: <short label>
    description: <what this failure mode looks like in code>
    example: <concrete instance from this repo or plausible
              given domain>

attention_anchors_marker: <FILLED|PARTIAL|ABSENT|INFERRED>
attention_anchors:
  file_anchors:
    - path: <repo-relative path>
      reason: <why this file deserves scrutiny>
  pattern_anchors:
    - pattern: <code pattern to flag>
      reason: <why this pattern is risky in this repo>

context_docs_marker: <FILLED|PARTIAL|ABSENT|INFERRED>
context_docs:
  - path: <repo-relative path>
    purpose: <why this doc is useful for PR evaluation>
    inject_strategy: <full|summary|reference>

staleness_hints_marker: PARTIAL
staleness_hints:
  - "rider generated by pass1 only — re-run pass2 against
     PR history to strengthen invariants and failure modes"

MARKER GUIDANCE:
  FILLED   — strong direct evidence in provided documents
  PARTIAL  — some evidence, gaps remain
  INFERRED — reasonable inference, no explicit statement
  ABSENT   — no evidence — set field value to null
"""


def build_user_prompt(consolidated):
    import json as _json

    prompt_files = []
    for file in consolidated["files"]:
        prompt_file = dict(file)
        if (
            prompt_file.get("inject_strategy") == "summary"
            and prompt_file.get("compressed_content") is not None
        ):
            prompt_file["content"] = prompt_file["compressed_content"]
        prompt_file.pop("compressed_content", None)
        prompt_files.append(prompt_file)

    return (
        f"Repository: {consolidated['repo']}\n"
        f"Ref: {consolidated['ref']}\n\n"
        + _json.dumps(prompt_files, indent=2, ensure_ascii=False)
        + "\n\n---\nProduce the rider YAML now."
    )


def validate_draft_shape(doc):
    EXPECTED_KEYS = [
        "schema_version",
        "repo_intent_marker",
        "repo_intent",
        "invariants_marker",
        "invariants",
        "failure_mode_categories_marker",
        "failure_mode_categories",
        "attention_anchors_marker",
        "context_docs_marker",
        "staleness_hints_marker",
    ]
    for key in EXPECTED_KEYS:
        if key not in doc:
            print(f"WARN: LLM response missing expected key: {key}", file=sys.stderr)


def main():
    args = parse_args()
    fetch_dir = Path(args.fetch_dir)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not args.dry_run and not api_key:
        print(
            "ERROR: ANTHROPIC_API_KEY environment variable not set",
            file=sys.stderr,
        )
        sys.exit(1)

    consolidated_path = fetch_dir / "consolidated.json"
    if not consolidated_path.exists():
        print(
            "ERROR: No consolidated.json — run pass1_extract_pre first",
            file=sys.stderr,
        )
        sys.exit(1)

    consolidated = json.loads(consolidated_path.read_text(encoding="utf-8"))

    yaml = None
    if not args.dry_run:
        try:
            yaml = get_yaml_module()
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    # Step 1: Pre-compress summary-strategy files
    for file in consolidated["files"]:
        if (
            file["inject_strategy"] == "summary"
            and file["content"] is not None
            and len(file["content"].encode("utf-8")) > MIN_COMPRESSION_BYTES
        ):
            if file.get("compressed_content") is not None:
                continue
            if args.dry_run:
                file["compressed_content"] = file["content"]
            else:
                compressed = compress_doc(file, api_key)
                file["compressed_content"] = compressed

    # Step 2: Assemble prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(consolidated)

    # Step 3: Dry-run path
    if args.dry_run:
        (fetch_dir / "system-prompt.txt").write_text(system_prompt, encoding="utf-8")
        (fetch_dir / "user-prompt.txt").write_text(user_prompt, encoding="utf-8")
        print("Dry run — prompts written to:")
        print(f"  {fetch_dir}/system-prompt.txt")
        print(f"  {fetch_dir}/user-prompt.txt")
        print("Paste into Claude manually.")
        print(f"Save response as: {fetch_dir}/rider-draft.yaml")
        sys.exit(0)

    # Step 4: Extraction LLM call
    try:
        response_text = call_llm(system_prompt, user_prompt, api_key)
    except Exception as e:
        print(f"ERROR: LLM call failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 5: Parse response
    try:
        doc = yaml.safe_load(response_text)
    except yaml.YAMLError:
        (fetch_dir / "llm-response-raw.txt").write_text(response_text, encoding="utf-8")
        print(
            "ERROR: LLM response was not valid YAML —"
            " raw response saved to llm-response-raw.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    if doc is None or not isinstance(doc, dict):
        (fetch_dir / "llm-response-raw.txt").write_text(response_text, encoding="utf-8")
        print(
            "ERROR: LLM response parsed as empty or non-mapping —"
            " raw response saved to llm-response-raw.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    # Step 6: Validate response shape
    validate_draft_shape(doc)

    # Step 7: Write rider-draft.yaml
    rider_draft_path = fetch_dir / "rider-draft.yaml"
    rider_draft_path.write_text(
        yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    # Step 8: Print field status summary
    print(f"Draft rider written to {fetch_dir}/rider-draft.yaml")
    print("Field status:")
    for key in MARKER_KEYS:
        field = key.replace("_marker", "")
        value = doc.get(key, "MISSING")
        print(f"  {field:<30} {value}")
    print("")
    print("Run rider-validate to check before proceeding:")
    print(f"  python rider_validate.py {fetch_dir}/rider-draft.yaml")


if __name__ == "__main__":
    main()
