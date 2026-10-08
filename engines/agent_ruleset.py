"""Build concise, machine-readable coding guidance from a scan result."""

from typing import Any, Dict, List


SECURITY_BASELINES = {
    "python": [
        "Do not hardcode credentials, tokens, or private keys.",
        "Use parameterized SQL queries.",
        "Do not use eval() or exec() on untrusted input.",
        "Do not swallow exceptions or disable TLS verification without a documented reason.",
    ],
    "go": [
        "Do not hardcode credentials, tokens, or private keys.",
        "Use parameterized SQL queries rather than concatenating untrusted input.",
        "Do not pass untrusted input to shell commands.",
        "Check errors and preserve cancellation and resource lifetimes.",
    ],
}


def _collect_findings(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings = []
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
    return findings


def _security_baseline(language: str) -> List[str]:
    languages = ("python", "go") if language == "mixed" else (language,)
    instructions = []
    for selected_language in languages:
        baseline = SECURITY_BASELINES.get(
            selected_language, SECURITY_BASELINES["python"]
        )
        for instruction in baseline:
            if instruction not in instructions:
                instructions.append(instruction)
    return instructions


def generate_agent_rules(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return a reusable agent policy plus findings from the current scan."""
    language = result.get("language", "python")
    return {
        "version": 1,
        "language": language,
        "workflow": [
            "Inspect the relevant code and project conventions before editing.",
            "Write or update focused tests before changing implementation.",
            "Cover boundary conditions and expected failure paths.",
            "Run the relevant tests and quality checks; report commands and outcomes.",
            "Do not claim a check passed when it was skipped or could not run.",
        ],
        "security_baseline": _security_baseline(language),
        "scan": {
            "gate_result": result.get("gate_result"),
            "findings": _collect_findings(result),
            "errors": result.get("scan_errors", []),
        },
    }
