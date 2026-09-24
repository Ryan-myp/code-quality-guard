"""Convert a Code Quality Guard result to SARIF 2.1.0."""

from pathlib import Path
from typing import Any, Dict, List, Tuple


SEVERITY_LEVELS = {
    "critical": "error",
    "high": "error",
    "warning": "warning",
    "info": "note",
}
Finding = Tuple[str, Dict[str, Any]]


def _collect_findings(result: Dict[str, Any]) -> List[Finding]:
    return [
        (file_name, issue)
        for file_name, issues in result.get("file_results", {}).items()
        for issue in issues
    ]


def _make_rules(findings: List[Finding]) -> List[Dict[str, Any]]:
    first_issue_by_rule = {}
    for _, issue in findings:
        first_issue_by_rule.setdefault(issue["rule_id"], issue)
    return [
        {
            "id": rule_id,
            "shortDescription": {"text": issue["message"]},
            "help": {"text": issue.get("fix") or issue["message"]},
            "defaultConfiguration": {
                "level": SEVERITY_LEVELS.get(issue["severity"], "warning")
            },
        }
        for rule_id, issue in sorted(first_issue_by_rule.items())
    ]


def _artifact_uri(file_name: str, project_path: Path) -> str:
    path = Path(file_name)
    if project_path.is_file():
        if not path.is_absolute() and path.name == project_path.name:
            path = project_path
        elif not path.is_absolute():
            path = project_path.parent / path
        return path.resolve().as_uri()
    if not path.is_absolute():
        path = project_path / path
    try:
        return path.resolve().relative_to(project_path).as_posix()
    except ValueError:
        return path.resolve().as_uri()


def _make_result(file_name: str, issue: Dict[str, Any], project_path: Path, indices):
    region = {"startLine": max(1, int(issue["line"]))}
    if issue.get("column") is not None:
        region["startColumn"] = max(1, int(issue["column"]) + 1)
    return {
        "ruleId": issue["rule_id"],
        "ruleIndex": indices[issue["rule_id"]],
        "level": SEVERITY_LEVELS.get(issue["severity"], "warning"),
        "message": {"text": issue["message"]},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": _artifact_uri(file_name, project_path)},
                    "region": region,
                }
            }
        ],
        "properties": {
            "confidence": issue.get("confidence"),
            "fix": issue.get("fix"),
        },
    }


def generate_sarif(result: Dict[str, Any], project_path: Path) -> Dict[str, Any]:
    """Return a SARIF document containing findings and scan errors."""
    project_path = Path(project_path).resolve()
    findings = _collect_findings(result)
    rule_ids = sorted({issue["rule_id"] for _, issue in findings})
    rule_indices = {rule_id: index for index, rule_id in enumerate(rule_ids)}
    rules = _make_rules(findings)
    sarif_results = [
        _make_result(file_name, issue, project_path, rule_indices)
        for file_name, issue in findings
    ]
    invocation = {
        "executionSuccessful": not bool(result.get("scan_errors")),
        "properties": {"scanErrors": result.get("scan_errors", [])},
    }
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Code Quality Guard",
                        "informationUri": "https://github.com/Ryan-myp/code-quality-guard",
                        "rules": rules,
                    }
                },
                "invocations": [invocation],
                "results": sarif_results,
            }
        ],
    }
