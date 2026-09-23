"""
增强分析器 - AST + 文本模式匹配
"""
import ast
import re
import tokenize
import io
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .spec_parser import ProjectSpec


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    """代码问题"""
    rule_id: str
    severity: Severity
    line: int
    column: int
    message: str
    fix: Optional[str] = None
    confidence: float = 1.0
    context: str = ""


class EnhancedAnalyzer:
    """增强分析器 - AST + 文本模式"""
    
    # 安全规则
    SECURITY_RULES = {
        'eval_exec': {
            'pattern': r'\beval\s*\(',
            'severity': Severity.CRITICAL,
            'message': '检测到 eval() 使用，存在代码注入风险',
            'fix': '使用 json.loads() 或 ast.literal_eval() 替代',
            'confidence': 0.95,
        },
        'exec': {
            'pattern': r'\bexec\s*\(',
            'severity': Severity.CRITICAL,
            'message': '检测到 exec() 使用，存在代码注入风险',
            'fix': '重构为更安全的方式，如使用 dispatch 表',
            'confidence': 0.95,
        },
        'hardcoded_secret': {
            'pattern': r'''(?:password|secret|api_key|token|private_key)\s*=\s*["\'][^"\']+["\']''',
            'severity': Severity.CRITICAL,
            'message': '检测到硬编码密钥/密码',
            'fix': '使用环境变量或密钥管理服务',
            'confidence': 0.90,
        },
        'sql_injection': {
            'pattern': r'''(?:execute|cursor\.execute|query)\s*\(\s*f?["\'](?:SELECT|INSERT|UPDATE|DELETE)[^"\']*\{''',
            'severity': Severity.CRITICAL,
            'message': '检测到 SQL 注入风险',
            'fix': '使用参数化查询',
            'confidence': 0.85,
        },
        'ssl_disabled': {
            'pattern': r'verify\s*=\s*False',
            'severity': Severity.CRITICAL,
            'message': 'SSL 验证被禁用，存在中间人攻击风险',
            'fix': '启用 SSL 验证: verify=True',
            'confidence': 0.95,
        },
        'command_injection': {
            'pattern': r'os\.system\s*\(|subprocess\.call\s*\([^)]*shell\s*=\s*True',
            'severity': Severity.CRITICAL,
            'message': '检测到命令注入风险',
            'fix': '使用 subprocess.run() 参数列表，避免 shell=True',
            'confidence': 0.90,
        },
    }
    
    # 错误处理规则
    ERROR_HANDLING_RULES = {
        'bare_except': {
            'pattern': r'except\s*:',
            'severity': Severity.HIGH,
            'message': '检测到裸 except，应捕获具体异常类型',
            'fix': '捕获具体异常类型，如 except ValueError:',
            'confidence': 0.95,
        },
        'swallow_exception': {
            'pattern': r'except.*?:\s*\n\s+pass',
            'severity': Severity.HIGH,
            'message': '异常被吞没，可能导致难以调试的问题',
            'fix': '记录日志并重新抛出异常',
            'confidence': 0.90,
        },
        'generic_exception': {
            'pattern': r'except\s+Exception\s*:',
            'severity': Severity.HIGH,
            'message': '捕获通用 Exception，应捕获更具体的异常',
            'fix': '捕获具体异常类型',
            'confidence': 0.85,
        },
    }
    
    # 代码质量规则
    CODE_QUALITY_RULES = {
        'function_too_long': {
            'severity': Severity.WARNING,
            'message': '函数过长，建议拆分为多个小函数',
            'fix': '将函数拆分为多个职责单一的子函数',
            'confidence': 0.80,
        },
        'too_many_parameters': {
            'severity': Severity.WARNING,
            'message': '参数过多，建议使用对象封装',
            'fix': '将参数封装为数据类或配置对象',
            'confidence': 0.85,
        },
        'deep_nesting': {
            'severity': Severity.WARNING,
            'message': '嵌套过深，可读性差',
            'fix': '提取为独立函数或使用 early return',
            'confidence': 0.80,
        },
        'redundant_todo': {
            'severity': Severity.INFO,
            'message': '存在 TODO/FIXME 标记',
            'fix': '创建任务或直接修复',
            'confidence': 0.70,
        },
    }
    
    def __init__(self, spec: Optional[ProjectSpec] = None):
        self.spec = spec or ProjectSpec()
        self.issues: List[Issue] = []
    
    def analyze(self, code: str, file_path: Optional[Path] = None) -> List[Issue]:
        """分析代码，返回发现的问题"""
        self.issues = []
        
        # AST 分析
        self._analyze_ast(code)
        
        # 文本模式匹配
        self._analyze_patterns(code)
        
        # 过滤不符合严重级别的发现
        self.issues = [
            issue for issue in self.issues
            if self._should_report(issue)
        ]
        
        return self.issues
    
    def _analyze_ast(self, code: str):
        """AST 分析"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # 语法错误，跳过 AST 分析
            return
        
        # 检查函数长度和参数数量
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_function(node)
            
            # 检查异常处理
            if isinstance(node, ast.ExceptHandler):
                self._check_exception_handler(node)
    
    def _check_function(self, node):
        """检查函数"""
        func_length = len(node.body)
        param_count = len(node.args.args)
        nesting_depth = self._calculate_nesting_depth(node)
        
        # 函数过长
        if func_length > self.spec.code_quality.max_function_length:
            self.issues.append(Issue(
                rule_id='code_quality.function_too_long',
                severity=Severity.WARNING,
                line=node.lineno,
                column=node.col_offset,
                message=f'函数过长 ({func_length} 行，限制 {self.spec.code_quality.max_function_length} 行)',
                fix=self.CODE_QUALITY_RULES['function_too_long']['fix'],
                confidence=self.CODE_QUALITY_RULES['function_too_long']['confidence'],
                context=code.split('\n')[node.lineno - 1][:50],
            ))
        
        # 参数过多
        if param_count > self.spec.code_quality.max_parameters:
            self.issues.append(Issue(
                rule_id='code_quality.too_many_parameters',
                severity=Severity.WARNING,
                line=node.lineno,
                column=node.col_offset,
                message=f'参数过多 ({param_count} 个，限制 {self.spec.code_quality.max_parameters} 个)',
                fix=self.CODE_QUALITY_RULES['too_many_parameters']['fix'],
                confidence=self.CODE_QUALITY_RULES['too_many_parameters']['confidence'],
                context=code.split('\n')[node.lineno - 1][:50],
            ))
        
        # 嵌套过深
        if nesting_depth > self.spec.code_quality.max_nesting_depth:
            self.issues.append(Issue(
                rule_id='code_quality.deep_nesting',
                severity=Severity.WARNING,
                line=node.lineno,
                column=node.col_offset,
                message=f'嵌套过深 (深度 {nesting_depth}，限制 {self.spec.code_quality.max_nesting_depth})',
                fix=self.CODE_QUALITY_RULES['deep_nesting']['fix'],
                confidence=self.CODE_QUALITY_RULES['deep_nesting']['confidence'],
                context=code.split('\n')[node.lineno - 1][:50],
            ))
    
    def _check_exception_handler(self, node):
        """检查异常处理"""
        # 裸 except
        if node.type is None:
            self.issues.append(Issue(
                rule_id='ai_slop.bare_except',
                severity=Severity.HIGH,
                line=node.lineno,
                column=node.col_offset,
                message='检测到裸 except，应捕获具体异常类型',
                fix=self.ERROR_HANDLING_RULES['bare_except']['fix'],
                confidence=self.ERROR_HANDLING_RULES['bare_except']['confidence'],
                context='except:',
            ))
        
        # 异常吞没
        if node.body and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.issues.append(Issue(
                rule_id='ai_slop.swallow_exception',
                severity=Severity.HIGH,
                line=node.lineno,
                column=node.col_offset,
                message='异常被吞没，可能导致难以调试的问题',
                fix=self.ERROR_HANDLING_RULES['swallow_exception']['fix'],
                confidence=self.ERROR_HANDLING_RULES['swallow_exception']['confidence'],
                context='except ...: pass',
            ))
    
    def _analyze_patterns(self, code: str):
        """文本模式匹配"""
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # 安全检查
            for rule_id, rule in self.SECURITY_RULES.items():
                if re.search(rule['pattern'], line, re.IGNORECASE):
                    # 检查是否在忽略列表中
                    if self._is_ignored(rule_id, line):
                        continue
                    
                    self.issues.append(Issue(
                        rule_id=rule_id,
                        severity=rule['severity'],
                        line=line_num,
                        column=0,
                        message=rule['message'],
                        fix=rule['fix'],
                        confidence=rule['confidence'],
                        context=line.strip()[:80],
                    ))
            
            # 代码质量检查
            if 'TODO' in line or 'FIXME' in line:
                self.issues.append(Issue(
                    rule_id='ai_slop.redundant_todo',
                    severity=Severity.INFO,
                    line=line_num,
                    column=0,
                    message='存在 TODO/FIXME 标记',
                    fix='创建任务或直接修复',
                    confidence=0.70,
                    context=line.strip()[:80],
                ))
    
    def _calculate_nesting_depth(self, node, current_depth: int = 0) -> int:
        """计算嵌套深度"""
        max_depth = current_depth
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                child_depth = self._calculate_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)
            else:
                child_depth = self._calculate_nesting_depth(child, current_depth)
                max_depth = max(max_depth, child_depth)
        
        return max_depth
    
    def _is_ignored(self, rule_id: str, line: str) -> bool:
        """检查是否在忽略列表中"""
        # 这里可以根据规则 ID 和行内容判断是否忽略
        # 实际实现可以扩展为更复杂的逻辑
        return False
    
    def _should_report(self, issue: Issue) -> bool:
        """判断是否应该报告"""
        # 根据规范中的最大严重级别过滤
        severity_order = {
            Severity.CRITICAL: 4,
            Severity.HIGH: 3,
            Severity.WARNING: 2,
            Severity.INFO: 1,
        }
        
        max_severity = Severity(self.spec.security.max_severity)
        
        return severity_order[issue.severity] >= severity_order[max_severity]
    
    def get_summary(self) -> Dict[str, Any]:
        """获取分析摘要"""
        summary = {
            'total_issues': len(self.issues),
            'by_severity': {
                'critical': sum(1 for i in self.issues if i.severity == Severity.CRITICAL),
                'high': sum(1 for i in self.issues if i.severity == Severity.HIGH),
                'warning': sum(1 for i in self.issues if i.severity == Severity.WARNING),
                'info': sum(1 for i in self.issues if i.severity == Severity.INFO),
            },
            'by_rule': {},
        }
        
        for issue in self.issues:
            if issue.rule_id not in summary['by_rule']:
                summary['by_rule'][issue.rule_id] = 0
            summary['by_rule'][issue.rule_id] += 1
        
        return summary
