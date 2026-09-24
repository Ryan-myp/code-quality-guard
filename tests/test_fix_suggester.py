from engines.enhanced_analyzer import Issue, Severity
from engines.fix_suggester import FixSuggester


def test_suggester_uses_rule_guidance_when_no_template_exists():
    finding = Issue(
        "security.insecure_random",
        Severity.WARNING,
        3,
        0,
        "Weak random source",
        fix="Use secrets for security-sensitive values.",
    )

    suggestion = FixSuggester().suggest(finding)

    assert suggestion["template"] == "Use secrets for security-sensitive values."
