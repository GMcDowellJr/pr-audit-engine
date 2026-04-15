import argparse
import json
import os
import sys
from dataclasses import dataclass


@dataclass
class Finding:
    field: str | None
    severity: str  # ERROR | WARN | INFO
    code: str
    message: str

    def to_dict(self):
        return {
            "field": self.field,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


def get_marker(doc, field_name, findings):
    key = f"{field_name}_marker"
    value = doc.get(key)
    VALID_MARKERS = ["FILLED", "PARTIAL", "ABSENT", "INFERRED"]
    if value not in VALID_MARKERS:
        findings.append(
            Finding(
                field=key,
                severity="WARN",
                code="INVALID_MARKER",
                message=f"{key} has unrecognized value '{value}'",
            )
        )
        return None
    return value


def check_schema_version(doc):
    findings = []
    KNOWN_VERSIONS = [1]
    if "schema_version" not in doc:
        findings.append(
            Finding(
                field="schema_version",
                severity="ERROR",
                code="SCHEMA_VERSION_MISSING",
                message="schema_version is missing",
            )
        )
    elif doc["schema_version"] not in KNOWN_VERSIONS:
        v = doc["schema_version"]
        findings.append(
            Finding(
                field="schema_version",
                severity="ERROR",
                code="SCHEMA_VERSION_UNKNOWN",
                message=f"schema_version '{v}' not recognized",
            )
        )
    return findings


def check_required_fields(doc):
    findings = []
    REQUIRED = ["repo_intent", "invariants", "failure_mode_categories"]
    for field in REQUIRED:
        if field not in doc or doc[field] is None:
            findings.append(
                Finding(
                    field=field,
                    severity="ERROR",
                    code="FIELD_ABSENT",
                    message=f"{field} is missing or null",
                )
            )
    return findings


def check_repo_intent(doc):
    findings = []
    value = doc.get("repo_intent")
    if value is None:
        return findings

    marker = get_marker(doc, "repo_intent", findings)

    if marker == "ABSENT":
        findings.append(
            Finding(
                field="repo_intent",
                severity="ERROR",
                code="INTENT_ABSENT",
                message="repo_intent marker is ABSENT",
            )
        )
    elif marker == "INFERRED":
        findings.append(
            Finding(
                field="repo_intent",
                severity="WARN",
                code="INTENT_INFERRED",
                message=(
                    "repo_intent is INFERRED — engine findings from this field will be downgraded"
                ),
            )
        )
    elif marker == "PARTIAL":
        findings.append(
            Finding(
                field="repo_intent",
                severity="WARN",
                code="INTENT_PARTIAL",
                message="repo_intent is PARTIAL — missing scope boundary or correctness definition",
            )
        )

    text = str(value).strip()
    MIN_INTENT_LENGTH = 50
    if len(text) < MIN_INTENT_LENGTH:
        findings.append(
            Finding(
                field="repo_intent",
                severity="WARN",
                code="INTENT_TOO_SHORT",
                message=(
                    f"repo_intent may be too vague ({len(text)} chars, minimum {MIN_INTENT_LENGTH})"
                ),
            )
        )

    return findings


def check_invariants(doc):
    findings = []
    value = doc.get("invariants")
    if value is None:
        return findings

    marker = get_marker(doc, "invariants", findings)

    if marker == "ABSENT":
        findings.append(
            Finding(
                field="invariants",
                severity="ERROR",
                code="INVARIANTS_ABSENT",
                message="invariants marker is ABSENT",
            )
        )
    elif marker == "INFERRED":
        findings.append(
            Finding(
                field="invariants",
                severity="WARN",
                code="INVARIANTS_INFERRED",
                message="invariants is INFERRED",
            )
        )
    elif marker == "PARTIAL":
        findings.append(
            Finding(
                field="invariants",
                severity="WARN",
                code="INVARIANTS_PARTIAL",
                message="invariants is PARTIAL",
            )
        )

    if not isinstance(value, list) or len(value) == 0:
        findings.append(
            Finding(
                field="invariants",
                severity="ERROR",
                code="INVARIANTS_EMPTY",
                message="invariants must be a non-empty list",
            )
        )
        return findings

    PLACEHOLDER_VALUES = ["~", "", None]
    ASSERTION_VERBS = [
        "must",
        "must not",
        "never",
        "always",
        "shall",
        "shall not",
        "cannot",
        "is required to",
    ]

    for i, inv in enumerate(value):
        if not isinstance(inv, str) or inv.strip() in PLACEHOLDER_VALUES:
            findings.append(
                Finding(
                    field=f"invariants[{i}]",
                    severity="WARN",
                    code="INVARIANT_PLACEHOLDER",
                    message=f"invariants[{i}] is a placeholder",
                )
            )
            continue
        if not any(verb in inv.lower() for verb in ASSERTION_VERBS):
            findings.append(
                Finding(
                    field=f"invariants[{i}]",
                    severity="WARN",
                    code="INVARIANT_NOT_FALSIFIABLE",
                    message=f"invariants[{i}] may not be falsifiable: '{inv}'",
                )
            )

    return findings


def check_failure_modes(doc):
    findings = []
    value = doc.get("failure_mode_categories")
    if value is None:
        return findings

    marker = get_marker(doc, "failure_mode_categories", findings)

    if marker == "ABSENT":
        findings.append(
            Finding(
                field="failure_mode_categories",
                severity="ERROR",
                code="FAILURE_MODES_ABSENT",
                message="failure_mode_categories marker is ABSENT",
            )
        )
    elif marker == "INFERRED":
        findings.append(
            Finding(
                field="failure_mode_categories",
                severity="WARN",
                code="FAILURE_MODES_INFERRED",
                message="failure_mode_categories is INFERRED",
            )
        )
    elif marker == "PARTIAL":
        findings.append(
            Finding(
                field="failure_mode_categories",
                severity="WARN",
                code="FAILURE_MODES_PARTIAL",
                message="failure_mode_categories is PARTIAL",
            )
        )

    if not isinstance(value, list) or len(value) == 0:
        findings.append(
            Finding(
                field="failure_mode_categories",
                severity="ERROR",
                code="FAILURE_MODES_EMPTY",
                message="failure_mode_categories must be a non-empty list",
            )
        )
        return findings

    PLACEHOLDER = "~"
    for i, cat in enumerate(value):
        if not isinstance(cat, dict):
            findings.append(
                Finding(
                    field=f"failure_mode_categories[{i}]",
                    severity="ERROR",
                    code="FAILURE_MODE_NOT_DICT",
                    message=f"failure_mode_categories[{i}] is not a mapping",
                )
            )
            continue
        for subfield in ["name", "description", "example"]:
            v = cat.get(subfield)
            if v is None or str(v).strip() in ("", PLACEHOLDER):
                findings.append(
                    Finding(
                        field=f"failure_mode_categories[{i}].{subfield}",
                        severity="WARN",
                        code="FAILURE_MODE_INCOMPLETE",
                        message=f"failure_mode_categories[{i}].{subfield} is missing or empty",
                    )
                )

    return findings


def check_attention_anchors(doc):
    findings = []
    value = doc.get("attention_anchors")
    if value is None:
        findings.append(
            Finding(
                field="attention_anchors",
                severity="INFO",
                code="ANCHORS_ABSENT",
                message="attention_anchors not present — recommended but not required",
            )
        )
        return findings

    if not isinstance(value, dict):
        findings.append(
            Finding(
                field="attention_anchors",
                severity="ERROR",
                code="ANCHORS_NOT_MAPPING",
                message="attention_anchors must be a mapping",
            )
        )
        return findings

    PLACEHOLDER = "~"
    file_anchors = value.get("file_anchors", [])
    if not isinstance(file_anchors, list):
        findings.append(
            Finding(
                field="file_anchors",
                severity="ERROR",
                code="FILE_ANCHORS_NOT_LIST",
                message="attention_anchors.file_anchors must be a list",
            )
        )
        return findings
    for i, anchor in enumerate(file_anchors):
        if not isinstance(anchor, dict):
            continue
        if not anchor.get("path") or str(anchor["path"]).strip() == PLACEHOLDER:
            findings.append(
                Finding(
                    field=f"file_anchors[{i}]",
                    severity="WARN",
                    code="ANCHOR_MISSING_PATH",
                    message=f"file_anchors[{i}] missing path",
                )
            )
        if not anchor.get("reason") or str(anchor["reason"]).strip() == PLACEHOLDER:
            findings.append(
                Finding(
                    field=f"file_anchors[{i}]",
                    severity="WARN",
                    code="ANCHOR_MISSING_REASON",
                    message=f"file_anchors[{i}] missing reason",
                )
            )

    pattern_anchors = value.get("pattern_anchors", [])
    if len(pattern_anchors) == 0 and len(file_anchors) > 0:
        findings.append(
            Finding(
                field="pattern_anchors",
                severity="INFO",
                code="NO_PATTERN_ANCHORS",
                message="no pattern_anchors defined — consider adding at least one",
            )
        )

    return findings


def check_context_docs(doc):
    findings = []
    value = doc.get("context_docs")
    if value is None:
        findings.append(
            Finding(
                field="context_docs",
                severity="INFO",
                code="CONTEXT_DOCS_ABSENT",
                message="context_docs not present — optional",
            )
        )
        return findings

    if not isinstance(value, list):
        findings.append(
            Finding(
                field="context_docs",
                severity="ERROR",
                code="CONTEXT_DOCS_NOT_LIST",
                message="context_docs must be a list",
            )
        )
        return findings

    VALID_STRATEGIES = ["full", "summary", "reference"]
    PLACEHOLDER = "~"
    for i, entry in enumerate(value):
        if not isinstance(entry, dict):
            findings.append(
                Finding(
                    field=f"context_docs[{i}]",
                    severity="ERROR",
                    code="CONTEXT_DOC_NOT_DICT",
                    message=f"context_docs[{i}] is not a mapping",
                )
            )
            continue
        if not entry.get("path") or str(entry["path"]).strip() == PLACEHOLDER:
            findings.append(
                Finding(
                    field=f"context_docs[{i}]",
                    severity="WARN",
                    code="CONTEXT_DOC_MISSING_PATH",
                    message=f"context_docs[{i}] missing path",
                )
            )
        if "inject_strategy" not in entry:
            findings.append(
                Finding(
                    field=f"context_docs[{i}]",
                    severity="WARN",
                    code="CONTEXT_DOC_MISSING_STRATEGY",
                    message=f"context_docs[{i}] missing inject_strategy",
                )
            )
        elif entry["inject_strategy"] not in VALID_STRATEGIES:
            v = entry["inject_strategy"]
            findings.append(
                Finding(
                    field=f"context_docs[{i}]",
                    severity="ERROR",
                    code="CONTEXT_DOC_INVALID_STRATEGY",
                    message=(
                        f"context_docs[{i}] inject_strategy '{v}' must be one of {VALID_STRATEGIES}"
                    ),
                )
            )

    return findings


def check_staleness_hints(doc):
    findings = []
    AUTO_FIELDS = ["generated_at", "generated_against_sha", "passes_run"]
    missing_auto = [f for f in AUTO_FIELDS if doc.get(f) is None]
    if missing_auto:
        findings.append(
            Finding(
                field=None,
                severity="WARN",
                code="STALENESS_AUTO_MISSING",
                message=f"Auto-populated staleness fields missing: {missing_auto}",
            )
        )

    value = doc.get("staleness_hints")
    if not value or (
        isinstance(value, list) and all(str(v).strip() in ("~", "") for v in value)
    ):
        findings.append(
            Finding(
                field="staleness_hints",
                severity="INFO",
                code="STALENESS_HINTS_ABSENT",
                message="no domain-specific staleness hints — consider adding one",
            )
        )

    return findings


def resolve_exit_code(findings):
    if any(f.severity == "ERROR" for f in findings):
        return 1
    if any(f.severity == "WARN" for f in findings):
        return 2
    return 0


def emit_output(findings, fmt):
    if fmt == "json":
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        for f in findings:
            print(f"[{f.severity}] {f.code}: {f.message}")
        n_errors = sum(1 for f in findings if f.severity == "ERROR")
        n_warnings = sum(1 for f in findings if f.severity == "WARN")
        n_info = sum(1 for f in findings if f.severity == "INFO")
        print(f"\n{n_errors} error(s), {n_warnings} warning(s), {n_info} info")


def parse_args():
    parser = argparse.ArgumentParser(description="Validate a pr-audit-rider.yaml file.")
    parser.add_argument("rider_path", help="Path to the rider YAML file")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    return parser.parse_args()


def get_yaml_module():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The 'PyYAML' package is required to parse rider YAML files. "
            "Install dependencies (for example: `pip install pyyaml`)."
        ) from exc

    return yaml


def parse_rider_document(raw):
    """Parse rider content with PyYAML when available, or JSON as fallback."""
    try:
        yaml = get_yaml_module()
    except RuntimeError as yaml_error:
        try:
            return json.loads(raw), [
                Finding(
                    field=None,
                    severity="INFO",
                    code="JSON_FALLBACK_USED",
                    message=(
                        "PyYAML is not installed; parsed rider as JSON fallback "
                        "(YAML syntax beyond JSON is not supported in this mode)."
                    ),
                )
            ]
        except json.JSONDecodeError:
            raise RuntimeError(
                f"{yaml_error} If you cannot install PyYAML, provide the rider in strict JSON format."
            ) from yaml_error

    try:
        return yaml.safe_load(raw), []
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parse error: {e}") from e


def main():
    args = parse_args()
    findings = []

    if not os.path.exists(args.rider_path):
        findings.append(
            Finding(
                field=None,
                severity="ERROR",
                code="FILE_NOT_FOUND",
                message=f"Rider file not found at {args.rider_path}",
            )
        )
        emit_output(findings, args.format)
        sys.exit(1)

    with open(args.rider_path) as fh:
        raw = fh.read()

    try:
        doc, parse_findings = parse_rider_document(raw)
        findings += parse_findings
    except RuntimeError as e:
        findings.append(
            Finding(
                field=None,
                severity="ERROR",
                code="YAML_DEPENDENCY_MISSING",
                message=str(e),
            )
        )
        emit_output(findings, args.format)
        sys.exit(1)
    except ValueError as e:
        findings.append(
            Finding(
                field=None,
                severity="ERROR",
                code="YAML_PARSE_FAILURE",
                message=f"YAML parse error: {e}",
            )
        )
        emit_output(findings, args.format)
        sys.exit(1)

    if doc is None or not isinstance(doc, dict):
        findings.append(
            Finding(
                field=None,
                severity="ERROR",
                code="EMPTY_OR_INVALID",
                message="Rider file is empty or not a mapping",
            )
        )
        emit_output(findings, args.format)
        sys.exit(1)

    findings += check_schema_version(doc)
    findings += check_required_fields(doc)
    findings += check_repo_intent(doc)
    findings += check_invariants(doc)
    findings += check_failure_modes(doc)
    findings += check_attention_anchors(doc)
    findings += check_context_docs(doc)
    findings += check_staleness_hints(doc)

    emit_output(findings, args.format)
    sys.exit(resolve_exit_code(findings))


if __name__ == "__main__":
    main()
