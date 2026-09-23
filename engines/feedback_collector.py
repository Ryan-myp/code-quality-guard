"""
反馈收集器 - 持续学习优化
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class Feedback:
    """用户反馈"""
    issue_id: str
    rule_id: str
    false_positive: bool
    reason: str
    timestamp: str
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeedbackCollector:
    """反馈收集器"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path('.qguard/feedback.json')
        self.feedbacks: List[Feedback] = []
        self._load()
    
    def collect(self, feedback: Feedback) -> None:
        """收集反馈"""
        self.feedbacks.append(feedback)
        self._save()
    
    def collect_many(self, feedbacks: List[Feedback]) -> None:
        """批量收集反馈"""
        self.feedbacks.extend(feedbacks)
        self._save()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取反馈统计"""
        if not self.feedbacks:
            return {
                'total': 0,
                'false_positives': 0,
                'fp_rate': 0.0,
                'by_rule': {},
            }
        
        fp_count = sum(1 for f in self.feedbacks if f.false_positive)
        
        by_rule = {}
        for f in self.feedbacks:
            if f.rule_id not in by_rule:
                by_rule[f.rule_id] = {'total': 0, 'fp': 0}
            by_rule[f.rule_id]['total'] += 1
            if f.false_positive:
                by_rule[f.rule_id]['fp'] += 1
        
        return {
            'total': len(self.feedbacks),
            'false_positives': fp_count,
            'fp_rate': round(fp_count / len(self.feedbacks), 3) if self.feedbacks else 0.0,
            'by_rule': by_rule,
        }
    
    def get_false_positive_rules(self) -> List[str]:
        """获取误报率高的规则"""
        stats = self.get_statistics()
        high_fp_rules = []
        
        for rule_id, rule_stats in stats.get('by_rule', {}).items():
            if rule_stats['total'] >= 3:  # 至少 3 次反馈
                fp_rate = rule_stats['fp'] / rule_stats['total']
                if fp_rate > 0.5:  # 误报率超过 50%
                    high_fp_rules.append(rule_id)
        
        return high_fp_rules
    
    def _load(self) -> None:
        """加载反馈"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.feedbacks = [Feedback(**item) for item in data.get('feedbacks', [])]
            except (json.JSONDecodeError, TypeError):
                self.feedbacks = []
    
    def _save(self) -> None:
        """保存反馈"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'version': '1.0',
            'updated': datetime.now().isoformat(),
            'feedbacks': [f.to_dict() for f in self.feedbacks],
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def export_report(self, output_path: Optional[Path] = None) -> Path:
        """导出反馈报告"""
        report_path = output_path or (self.storage_path.parent / 'feedback_report.json')
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'statistics': self.get_statistics(),
            'high_fp_rules': self.get_false_positive_rules(),
            'feedbacks': [f.to_dict() for f in self.feedbacks],
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report_path
