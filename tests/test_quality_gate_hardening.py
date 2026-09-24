import pytest
from math import nan

from engines.enhanced_analyzer import Issue, Severity
from engines.quality_gate import GateConfig, GateResult, QualityGate


def issue(severity=Severity.INFO, confidence=1.0, rule_id="example.rule"):
    return Issue(rule_id, severity, 1, 0, "message", confidence=confidence)


def test_max_info_limit_is_enforced():
    gate = QualityGate(GateConfig(max_info=1))

    assert gate.check([issue(), issue()]) == GateResult.WARN
    assert gate.details["reason"] == "too_many_info"


def test_get_report_checks_issues_before_reading_result():
    gate = QualityGate()

    report = gate.get_report([issue(Severity.CRITICAL)])

    assert report["result"] == "fail"


@pytest.mark.parametrize(
    "config",
    [
        {"max_critical": -1},
        {"max_high": -1},
        {"max_warning": -1},
        {"max_info": -1},
        {"min_confidence": -0.1},
        {"min_confidence": 1.1},
        {"min_confidence": True},
        {"min_confidence": nan},
    ],
)
def test_invalid_gate_configuration_is_rejected(config):
    with pytest.raises(ValueError):
        QualityGate(GateConfig(**config))


def test_confidence_threshold_is_consistent_for_counts_and_report():
    gate = QualityGate(GateConfig(min_confidence=0.8))
    issues = [issue(Severity.CRITICAL, 0.79), issue(Severity.HIGH, 0.8)]

    report = gate.get_report(issues)

    assert report["details"]["counts"] == {
        "CRITICAL": 0,
        "HIGH": 1,
        "WARNING": 0,
        "INFO": 0,
    }
    assert report["issue_counts"]["critical"] == 1
