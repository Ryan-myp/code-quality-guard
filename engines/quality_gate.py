"""Quality gate for analyzer findings."""

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any, Dict, List, Optional

from .enhanced_analyzer import Issue, Severity


class GateResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


@dataclass
class GateConfig:
    """Limits used to decide whether a scan passes."""

    max_critical: int = 0
    max_high: int = 5
    max_warning: int = 20
    max_info: int = 100
    min_confidence: float = 0.7
    forbidden_rules: List[str] = field(default_factory=list)

    def __post_init__(self):
        for name in ("max_critical", "max_high", "max_warning", "max_info"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("{} must be a non-negative integer".format(name))
        if (
            isinstance(self.min_confidence, bool)
            or not isinstance(self.min_confidence, (int, float))
            or not isfinite(self.min_confidence)
            or not 0.0 <= self.min_confidence <= 1.0
        ):
            raise ValueError("min_confidence must be between 0 and 1")
        if not isinstance(self.forbidden_rules, list) or not all(
            isinstance(rule, str) and rule for rule in self.forbidden_rules
        ):
            raise ValueError("forbidden_rules must be a list of non-empty strings")


class QualityGate:
    """Evaluate findings against configured issue limits."""

    def __init__(self, config: Optional[GateConfig] = None):
        self.config = config or GateConfig()
        self.result: Optional[GateResult] = None
        self.details: Dict[str, Any] = {}

    def _counts(self, issues: List[Issue]) -> Dict[Severity, int]:
        counts = {severity: 0 for severity in Severity}
        for issue in issues:
            if issue.confidence >= self.config.min_confidence:
                counts[issue.severity] += 1
        return counts

    @staticmethod
    def _serialized_counts(counts: Dict[Severity, int]) -> Dict[str, int]:
        return {severity.name: count for severity, count in counts.items()}

    def check(self, issues: List[Issue]) -> GateResult:
        """Check the findings and store a machine-readable explanation."""
        counts = self._counts(issues)
        count_data = self._serialized_counts(counts)
        violations = [
            issue.rule_id
            for issue in issues
            if issue.rule_id in self.config.forbidden_rules
            and issue.confidence >= self.config.min_confidence
        ]
        if violations:
            return self._set_result(
                GateResult.FAIL,
                "violated_forbidden_rules",
                count_data,
                violations=violations,
            )

        limits = (
            (Severity.CRITICAL, self.config.max_critical, GateResult.FAIL, "too_many_critical"),
            (Severity.HIGH, self.config.max_high, GateResult.FAIL, "too_many_high"),
            (Severity.WARNING, self.config.max_warning, GateResult.WARN, "too_many_warnings"),
            (Severity.INFO, self.config.max_info, GateResult.WARN, "too_many_info"),
        )
        for severity, limit, result, reason in limits:
            if counts[severity] > limit:
                return self._set_result(result, reason, count_data)

        return self._set_result(GateResult.PASS, "all_clear", count_data)

    def _set_result(
        self,
        result: GateResult,
        reason: str,
        counts: Dict[str, int],
        **extra: Any
    ) -> GateResult:
        self.result = result
        self.details = {"reason": reason, "counts": counts}
        self.details.update(extra)
        return result

    def fail(self, reason: str, **extra: Any) -> GateResult:
        """Mark the current scan as failed for an operational or external policy reason."""
        return self._set_result(
            GateResult.FAIL,
            reason,
            self.details.get("counts", {}),
            **extra
        )

    def get_score(self, issues: List[Issue]) -> float:
        """Compute the legacy 0-100 severity-weighted score."""
        penalties = {
            Severity.CRITICAL: 20,
            Severity.HIGH: 10,
            Severity.WARNING: 5,
            Severity.INFO: 1,
        }
        total_penalty = sum(
            penalties[issue.severity] * issue.confidence
            for issue in issues
            if issue.confidence >= self.config.min_confidence
        )
        return round(max(0.0, 100.0 - total_penalty), 2)

    @staticmethod
    def get_badge(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def get_report(self, issues: List[Issue]) -> Dict[str, Any]:
        """Generate a report, evaluating the gate if it has not run yet."""
        self.check(issues)
        score = self.get_score(issues)
        return {
            "result": self.result.value,
            "score": score,
            "badge": self.get_badge(score),
            "details": self.details,
            "issue_counts": {
                "critical": sum(1 for issue in issues if issue.severity == Severity.CRITICAL),
                "high": sum(1 for issue in issues if issue.severity == Severity.HIGH),
                "warning": sum(1 for issue in issues if issue.severity == Severity.WARNING),
                "info": sum(1 for issue in issues if issue.severity == Severity.INFO),
            },
        }
