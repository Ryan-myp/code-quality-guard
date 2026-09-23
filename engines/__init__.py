"""
Code Quality Guard v22 - 引擎模块
"""
from .spec_parser import SpecParser
from .enhanced_analyzer import EnhancedAnalyzer
from .quality_gate import QualityGate
from .fix_suggester import FixSuggester
from .feedback_collector import FeedbackCollector

__all__ = [
    'SpecParser',
    'EnhancedAnalyzer',
    'QualityGate',
    'FixSuggester',
    'FeedbackCollector',
]
__version__ = '22.0.0-alpha'
