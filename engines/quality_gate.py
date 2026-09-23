"""
质量门禁 - 判断是否通过质量检查
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from .enhanced_analyzer import Issue, Severity


class GateResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


@dataclass
class GateConfig:
    """质量门禁配置"""
    # 允许的最大问题数量
    max_critical: int = 0
    max_high: int = 5
    max_warning: int = 20
    max_info: int = 100
    
    # 最低置信度要求
    min_confidence: float = 0.7
    
    # 禁止的规则（即使其他配置允许）
    forbidden_rules: List[str] = None
    
    def __post_init__(self):
        if self.forbidden_rules is None:
            self.forbidden_rules = []


class QualityGate:
    """质量门禁"""
    
    def __init__(self, config: Optional[GateConfig] = None):
        self.config = config or GateConfig()
        self.result: Optional[GateResult] = None
        self.details: Dict[str, Any] = {}
    
    def check(self, issues: List[Issue]) -> GateResult:
        """检查问题列表是否通过门禁"""
        # 统计问题数量
        counts = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 0,
            Severity.WARNING: 0,
            Severity.INFO: 0,
        }
        
        for issue in issues:
            if issue.confidence < self.config.min_confidence:
                continue
            counts[issue.severity] += 1
        
        # 检查是否有禁止的规则
        violated_forbidden = [
            issue for issue in issues
            if issue.rule_id in self.config.forbidden_rules
            and issue.confidence >= self.config.min_confidence
        ]
        
        if violated_forbidden:
            self.result = GateResult.FAIL
            self.details = {
                'reason': 'violated_forbidden_rules',
                'violations': [i.rule_id for i in violated_forbidden],
                'counts': {s.name: c for s, c in counts.items()},
            }
            return self.result
        
        # 检查数量限制
        if counts[Severity.CRITICAL] > self.config.max_critical:
            self.result = GateResult.FAIL
            self.details = {
                'reason': 'too_many_critical',
                'counts': {s.name: c for s, c in counts.items()},
            }
            return self.result
        
        if counts[Severity.HIGH] > self.config.max_high:
            self.result = GateResult.FAIL
            self.details = {
                'reason': 'too_many_high',
                'counts': {s.name: c for s, c in counts.items()},
            }
            return self.result
        
        # 警告状态
        if counts[Severity.WARNING] > self.config.max_warning:
            self.result = GateResult.WARN
            self.details = {
                'reason': 'too_many_warnings',
                'counts': {s.name: c for s, c in counts.items()},
            }
            return self.result
        
        # 通过
        self.result = GateResult.PASS
        self.details = {
            'reason': 'all_clear',
            'counts': {s.name: c for s, c in counts.items()},
        }
        return self.result
    
    def get_score(self, issues: List[Issue]) -> float:
        """计算质量分数 (0-100)"""
        if not issues:
            return 100.0
        
        # 加权扣分
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
        
        score = max(0, 100 - total_penalty)
        return round(score, 2)
    
    def get_badge(self, score: float) -> str:
        """根据分数返回徽章等级"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def get_report(self, issues: List[Issue]) -> Dict[str, Any]:
        """生成完整报告"""
        score = self.get_score(issues)
        badge = self.get_badge(score)
        
        return {
            'result': self.result.value,
            'score': score,
            'badge': badge,
            'details': self.details,
            'issue_counts': {
                'critical': sum(1 for i in issues if i.severity == Severity.CRITICAL),
                'high': sum(1 for i in issues if i.severity == Severity.HIGH),
                'warning': sum(1 for i in issues if i.severity == Severity.WARNING),
                'info': sum(1 for i in issues if i.severity == Severity.INFO),
            },
        }
