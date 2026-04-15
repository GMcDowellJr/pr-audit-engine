#!/usr/bin/env python3
"""pass1_fetch.py — fetch candidate documentation files from a GitHub repo."""

import argparse
import base64
import fnmatch
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

CANDIDATE_PATHS = [
    # Normative
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "SOUL.md",
    ".github/CONTRIBUTING.md",
    # Structural
    "README.md",
    "ARCHITECTURE.md",
    "docs/architecture.md",
    "docs/ARCHITECTURE.md",
    # Automation
    ".github/pr-audit-rider.yaml",
]

CANDIDATE_GLOB_PATTERNS = [
    ".github/*.yml",
    ".github/*.yaml",
    "docs/*.md",
]

MAX_FILE_SIZE_BYTES = 500_000
OUTPUT_DIR_DEFAULT = ".pr-audit-fetch"


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def request(self, method, path, params=None):
        url = self.BASE_URL + path
        if params:
            url = f"{url}?{urlencode(params)}"

        request = Request(url, headers=self.headers, method=method)
        try:
            with urlopen(request) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 401:
                sys.exit("GITHUB_TOKEN is invalid or expired")
            if error.code == 403:
                sys.exit("GITHUB_TOKEN lacks required permissions")
            if error.code == 404:
                raise FileNotFoundError from error
            if error.code == 429:
                sys.exit("GitHub API rate limit exceeded")
            if error.code >= 500:
                raise RuntimeError(f"GitHub API error: {error.code}") from error
            raise RuntimeError(f"GitHub API error: {error.code}") from error
        except URLError as error:
            raise RuntimeError(f"Network error while calling GitHub API: {error}") from error


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch candidate documentation files from a GitHub repo."
    )
    parser.add_argument("repo", help="Repository in owner/repo format")
    parser.add_argument(
        "--output",
        default=OUTPUT_DIR_DEFAULT,
        help=f"Output directory (default: {OUTPUT_DIR_DEFAULT})",
    )
    parser.add_argument(
        "--ref",
        default=None,
        help="Git ref (branch/tag/SHA) to fetch from (default: repo default branch)",
    )
    return parser.parse_args()


def parse_repo(repo_str):
    parts = repo_str.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        print("ERROR: repo must be in owner/repo format", file=sys.stderr)
        sys.exit(1)
    return parts[0], parts[1]


def fetch_default_branch(client, owner, repo_name):
    response = client.request("GET", f"/repos/{owner}/{repo_name}")
    return response["default_branch"]


def fetch_tree(client, owner, repo_name, ref):
    encoded_ref = quote(ref, safe="")
    response = client.request(
        "GET",
        f"/repos/{owner}/{repo_name}/git/trees/{encoded_ref}",
        params={"recursive": "1"},
    )
    truncated = response.get("truncated", False)
    if truncated:
        print(
            "WARN: repo tree was truncated by GitHub API — "
            "large repos may have incomplete candidate list",
            file=sys.stderr,
        )
    return response["tree"], truncated


def resolve_ref_to_sha(client, owner, repo_name, ref):
    encoded_ref = quote(ref, safe="")
    response = client.request("GET", f"/repos/{owner}/{repo_name}/commits/{encoded_ref}")
    return response["sha"]


def identify_candidates(tree):
    tree_nodes = {
        node["path"]: node
        for node in tree
        if node["type"] == "blob"
    }

    seen = set()
    candidates = []

    # Exact path matches
    for path in CANDIDATE_PATHS:
        if path in tree_nodes and path not in seen:
            node = tree_nodes[path]
            skip = node.get("size", 0) > MAX_FILE_SIZE_BYTES
            candidates.append({
                "path": path,
                "match_type": "exact",
                "size": node.get("size", 0),
                "skip": skip,
                "skip_reason": (
                    f"exceeds MAX_FILE_SIZE_BYTES ({node['size']} bytes)"
                    if skip else None
                ),
            })
            seen.add(path)

    # Glob pattern matches (shallow: path depth must equal pattern depth)
    for pattern in CANDIDATE_GLOB_PATTERNS:
        for path, node in tree_nodes.items():
            if (
                path.count("/") == pattern.count("/")
                and fnmatch.fnmatch(path, pattern)
                and path not in seen
            ):
                skip = node.get("size", 0) > MAX_FILE_SIZE_BYTES
                candidates.append({
                    "path": path,
                    "match_type": "glob",
                    "size": node.get("size", 0),
                    "skip": skip,
                    "skip_reason": (
                        f"exceeds MAX_FILE_SIZE_BYTES ({node['size']} bytes)"
                        if skip else None
                    ),
                })
                seen.add(path)

    return candidates


def fetch_and_write(client, owner, repo_name, ref, candidate, output_dir):
    if candidate["skip"]:
        return {
            "path": candidate["path"],
            "status": "skipped",
            "skip_reason": candidate["skip_reason"],
        }

    try:
        response = client.request(
            "GET",
            f"/repos/{owner}/{repo_name}/contents/{candidate['path']}",
            params={"ref": ref},
        )
        raw_bytes = base64.b64decode(response["content"])
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError("binary or non-UTF-8 file") from e

        local_path = output_dir / candidate["path"]
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(content, encoding="utf-8")

        return {
            "path": candidate["path"],
            "match_type": candidate["match_type"],
            "size_bytes": len(raw_bytes),
            "status": "ok",
        }

    except FileNotFoundError:
        return {
            "path": candidate["path"],
            "status": "error",
            "error": "404 Not Found",
        }
    except Exception as e:
        return {
            "path": candidate["path"],
            "status": "error",
            "error": str(e),
        }


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    args = parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)

    owner, repo_name = parse_repo(args.repo)

    client = GitHubClient(token)

    # Step 1: Resolve default branch
    if args.ref is None:
        default_branch = fetch_default_branch(client, owner, repo_name)
    else:
        default_branch = args.ref

    # Step 2: Resolve ref to commit SHA
    resolved_sha = resolve_ref_to_sha(client, owner, repo_name, default_branch)

    # Step 3: Fetch repo tree at resolved commit SHA (immutable)
    tree, truncated = fetch_tree(client, owner, repo_name, resolved_sha)

    # Step 4: Identify candidate docs
    candidates = identify_candidates(tree)

    # Step 5: Create output directory
    output_dir = Path(args.output)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Step 6: Fetch and write each candidate
    results = []
    for candidate in candidates:
        result = fetch_and_write(
            client, owner, repo_name, resolved_sha,
            candidate, output_dir,
        )
        results.append(result)

    # Step 7: Write manifest.json
    manifest = {
        "repo": args.repo,
        "ref": default_branch,
        "resolved_sha": resolved_sha,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "tree_truncated": truncated,
        "files": results,
    }
    write_json(output_dir / "manifest.json", manifest)

    # Step 8: Print summary
    n_ok = sum(1 for r in results if r["status"] == "ok")
    n_skipped = sum(1 for r in results if r["status"] == "skipped")
    n_errors = sum(1 for r in results if r["status"] == "error")

    print(f"Fetched {n_ok} files, skipped {n_skipped}, {n_errors} errors → {args.output}/")

    sys.exit(0 if n_errors == 0 else 1)


if __name__ == "__main__":
    main()
