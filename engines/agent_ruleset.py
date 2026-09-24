"""Build concise, machine-readable coding guidance from a scan result."""

from typing import Any, Dict, List


def generate_agent_rules(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return a reusable agent policy plus findings from the current scan."""
    findings: List[Dict[str, Any]] = []
    for file_name, issues in result.get("file_results", {}).items():
        for issue in issues:
            findings.append(
                {
                    "rule_id": issue["rule_id"],
                    "severity": issue["severity"],
                    "file": file_name,
                    "line": issue["line"],
                    "instruction": issue["fix"] or issue["message"],
                }
            )
    return {
        "version": 1,
        "language": "python",
        "workflow": [
            "Inspect the relevant code and project conventions before editing.",
            "Write or update focused tests before changing implementation.",
            "Cover boundary conditions and expected failure paths.",
            "Run the relevant tests and quality checks; report commands and outcomes.",
            "Do not claim a check passed when it was skipped or could not run.",
        ],
        "security_baseline": [
            "Do not hardcode credentials, tokens, or private keys.",
            "Use parameterized SQL queries.",
            "Do not use eval() or exec() on untrusted input.",
            "Do not swallow exceptions or disable TLS verification without a documented reason.",
        ],
        "scan": {
            "gate_result": result.get("gate_result"),
            "findings": findings,
            "errors": result.get("scan_errors", []),
        },
    }
