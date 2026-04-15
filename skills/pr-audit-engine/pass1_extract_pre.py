#!/usr/bin/env python3
"""pass1_extract_pre.py — normalize and consolidate fetched docs for LLM extraction."""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Files that get full inject — normative language is load-bearing
FULL_INJECT_NAMES = [
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "SOUL.md",
]

# GitHub automation files — reference only, content not injected
GITHUB_AUTOMATION_EXTENSIONS = [".yml", ".yaml"]

# Size threshold — emit warning but do not truncate
LARGE_FILE_WARNING_BYTES = 50_000


def parse_args():
    parser = argparse.ArgumentParser(
        description="Normalize and consolidate fetched docs for LLM extraction."
    )
    parser.add_argument(
        "fetch_dir",
        help="Path to pass1_fetch output directory (must contain manifest.json)",
    )
    return parser.parse_args()


def classify_inject_strategy(path):
    filename = os.path.basename(path)

    # Normative docs — full inject
    if filename in FULL_INJECT_NAMES:
        return "full"

    # GitHub automation — reference only
    if path.startswith(".github/"):
        ext = os.path.splitext(filename)[1].lower()
        if ext in GITHUB_AUTOMATION_EXTENSIONS:
            return "reference"

    # Structural docs — summary
    if filename == "README.md":
        return "summary"

    if path.startswith("docs/"):
        return "summary"

    # Default
    return "summary"


def normalize_doc(text):
    # 0. Extract fenced blocks up front so markdown cleanup does not alter
    #    code/diagram content before fence handling.
    fenced_blocks = []

    def _stash_fenced_block(match):
        info_string = (match.group("info") or "").strip()
        content = match.group("content") or ""
        language_tag = info_string.split()[0].lower() if info_string else ""

        if language_tag in {"mermaid", "graphviz", "dot", "plantuml"}:
            replacement = f"[diagram: {language_tag}]\n{content}"
        else:
            replacement = content

        token_index = len(fenced_blocks)
        token = f"<<CODE_FENCE_BLOCK_{token_index}>>"
        fenced_blocks.append(replacement)
        return token

    text = re.sub(
        r"```(?P<info>[^\n`]*)\n(?P<content>[\s\S]*?)```",
        _stash_fenced_block,
        text,
    )

    # 1. Remove HTML comments
    text = re.sub(r"<!--[\s\S]*?-->", "", text)

    # 2. Remove badge/image links (shields.io etc)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # 3. Strip markdown headings — keep label text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # 4. Strip bold/italic markers — keep inner text
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)

    # 5. Strip inline code markers — keep inner text
    text = re.sub(r"`([^`\n]+)`", r"\1", text)

    # 6. (fenced blocks already extracted in step 0)

    # 7. Strip link syntax — keep display text, drop URL
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # 8. Strip blockquote markers
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)

    # 9. Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # 10. Strip trailing whitespace per line
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

    # 11. Collapse 3+ consecutive blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 12. Strip leading/trailing whitespace from result
    text = text.strip()

    # 13. Reinsert preserved fenced block content.
    def _reinsert_fenced_block(match):
        token_index = int(match.group("index"))
        if 0 <= token_index < len(fenced_blocks):
            return fenced_blocks[token_index]
        return match.group(0)

    text = re.sub(
        r"<<CODE_FENCE_BLOCK_(?P<index>\d+)>>",
        _reinsert_fenced_block,
        text,
    )

    return text


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    fetch_dir = Path(args.fetch_dir)

    # Step 1: Load manifest
    manifest_path = fetch_dir / "manifest.json"
    if not manifest_path.exists():
        print("ERROR: No manifest.json found — run pass1_fetch first", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    ok_files = [f for f in manifest["files"] if f["status"] == "ok"]

    if len(ok_files) == 0:
        print("ERROR: No successfully fetched files in manifest", file=sys.stderr)
        sys.exit(1)

    # Step 2: Process each file
    processed = []
    warnings = []

    for file_entry in ok_files:
        raw_path = fetch_dir / file_entry["path"]

        if not raw_path.exists():
            warnings.append({
                "code": "MISSING_ON_DISK",
                "path": file_entry["path"],
                "message": (
                    f"{file_entry['path']} is listed as ok in manifest "
                    "but missing on disk"
                ),
            })
            continue

        raw_content = raw_path.read_text(encoding="utf-8")
        inject_strategy = classify_inject_strategy(file_entry["path"])

        if inject_strategy == "reference":
            content = None
            size_bytes = 0
        else:
            content = normalize_doc(raw_content)
            size_bytes = len(content.encode("utf-8"))
            raw_size = len(raw_content.encode("utf-8"))
            if size_bytes == 0 and raw_size > 0:
                warnings.append({
                    "code": "ZERO_AFTER_NORMALIZE",
                    "path": file_entry["path"],
                    "message": (
                        f"{file_entry['path']} normalized to empty string "
                        f"(raw size was {raw_size} bytes) — "
                        "likely a diagram-only or code-fence-only file"
                    ),
                })

        if size_bytes > LARGE_FILE_WARNING_BYTES:
            warnings.append({
                "code": "LARGE_FILE",
                "path": file_entry["path"],
                "message": (
                    f"{file_entry['path']} is {size_bytes} bytes after normalization "
                    "— may consume significant token budget"
                ),
            })

        processed.append({
            "path": file_entry["path"],
            "inject_strategy": inject_strategy,
            "size_bytes": size_bytes,
            "content": content,
        })

    # Step 3: Write consolidated.json
    consolidated = {
        "repo": manifest["repo"],
        "ref": manifest["ref"],
        "generated_against_sha": manifest["resolved_sha"],
        "fetched_at": manifest["fetched_at"],
        "extracted_at": datetime.utcnow().isoformat() + "Z",
        "warnings": warnings,
        "files": processed,
    }

    output_path = fetch_dir / "consolidated.json"
    write_json(output_path, consolidated)

    # Step 4: Print summary
    n_full = sum(1 for p in processed if p["inject_strategy"] == "full")
    n_summary = sum(1 for p in processed if p["inject_strategy"] == "summary")
    n_reference = sum(1 for p in processed if p["inject_strategy"] == "reference")

    print(f"Consolidated {len(processed)} files")
    print(f"  full:      {n_full}")
    print(f"  summary:   {n_summary}")
    print(f"  reference: {n_reference}")
    if warnings:
        print(f"  {len(warnings)} warning(s) — review before LLM pass")
    print(f"→ {output_path}")

    has_errors = any(w["code"] == "MISSING_ON_DISK" for w in warnings)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
