"""
增强分析器 - AST + 文本模式匹配
"""
import ast
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
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
        'security.eval_exec': {
            'pattern': r'\beval\s*\(',
            'severity': Severity.CRITICAL,
            'message': '检测到 eval() 使用，存在代码注入风险',
            'fix': '使用 json.loads() 或 ast.literal_eval() 替代',
            'confidence': 0.95,
        },
        'security.exec': {
            'pattern': r'\bexec\s*\(',
            'severity': Severity.CRITICAL,
            'message': '检测到 exec() 使用，存在代码注入风险',
            'fix': '重构代码避免使用 exec()',
            'confidence': 0.95,
        },
        'security.hardcoded_secret': {
            'pattern': r'''(?:password|secret|api_key|token|private_key)\s*=\s*["\'][^"\']+["\']''',
            'severity': Severity.CRITICAL,
            'message': '检测到硬编码密钥/密码',
            'fix': '使用环境变量或密钥管理服务',
            'confidence': 0.90,
        },
        'security.sql_injection': {
            'pattern': r'''(?:execute|cursor\.execute|query)\s*\(\s*f?["\'](?:SELECT|INSERT|UPDATE|DELETE)[^"\']*\{''',
            'severity': Severity.CRITICAL,
            'message': '检测到 SQL 注入风险',
            'fix': '使用参数化查询',
            'confidence': 0.85,
        },
        'security.ssl_disabled': {
            'pattern': r'verify\s*=\s*False',
            'severity': Severity.CRITICAL,
            'message': 'SSL 验证被禁用，存在中间人攻击风险',
            'fix': '启用 SSL 验证: verify=True',
            'confidence': 0.95,
        },
        'security.command_injection': {
            'pattern': r'os\.system\s*\(|subprocess\.call\s*\([^)]*shell\s*=\s*True',
            'severity': Severity.CRITICAL,
            'message': '检测到命令注入风险',
            'fix': '使用 subprocess.run() 参数列表',
            'confidence': 0.90,
        },
        'security.unsafe_deserialization': {
            'pattern': r'yaml\.load\s*\([^)]*Loader\s*=|pickle\.loads?\s*\(|marshal\.loads?\s*\(',
            'severity': Severity.CRITICAL,
            'message': '检测到不安全的反序列化，存在代码执行风险',
            'fix': '使用安全的反序列化方法，如 yaml.safe_load()',
            'confidence': 0.90,
        },
        'security.path_traversal': {
            'pattern': r'open\s*\([^)]*(?:\.\.|\.\\|\$\{|%s|%\()',
            'severity': Severity.HIGH,
            'message': '检测到潜在的路径遍历风险',
            'fix': '对用户输入进行路径规范化处理',
            'confidence': 0.80,
        },
        'security.insecure_random': {
            'pattern': r'random\.random\s*\(|random\.randint\s*\(|random\.choice\s*\(',
            'severity': Severity.WARNING,
            'message': '检测到使用不安全的随机数生成器',
            'fix': '使用 secrets 模块生成安全随机数',
            'confidence': 0.85,
        },
    }
    
    # 错误处理规则
    ERROR_HANDLING_RULES = {
        'ai_slop.bare_except': {
            'pattern': r'except\s*:',
            'severity': Severity.HIGH,
            'message': '检测到裸 except，应捕获具体异常类型',
            'fix': '捕获具体异常类型，如 except ValueError:',
            'confidence': 0.95,
        },
        'ai_slop.swallow_exception': {
            'pattern': r'except.*?:\s*\n\s+pass',
            'severity': Severity.HIGH,
            'message': '异常被吞没，可能导致难以调试的问题',
            'fix': '记录日志并重新抛出异常',
            'confidence': 0.90,
        },
        'ai_slop.generic_exception': {
            'pattern': r'except\s+Exception\s*:',
            'severity': Severity.HIGH,
            'message': '捕获通用 Exception，应捕获更具体的异常',
            'fix': '捕获具体异常类型',
            'confidence': 0.85,
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
        
        return self.issues
    
    def _analyze_ast(self, code: str):
        """AST 分析"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return
        
        lines = code.split('\n')
        
        # 检查函数长度、参数数量、嵌套深度
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_function(node, lines)
            
            # 检查异常处理
            if isinstance(node, ast.ExceptHandler):
                self._check_exception_handler(node, lines)
    
    def _check_function(self, node, lines):
        """检查函数"""
        func_length = len(node.body)
        param_count = len(node.args.args)
        nesting_depth = self._calculate_nesting_depth(node)
        
        # 函数过长
        if func_length > self.spec.code_quality.max_function_length:
            line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
            self.issues.append(Issue(
                rule_id='code_quality.function_too_long',
                severity=Severity.WARNING,
                line=node.lineno,
                column=node.col_offset,
                message=f'函数过长 ({func_length} 行，限制 {self.spec.code_quality.max_function_length} 行)',
                fix='拆分为多个职责单一的子函数',
                confidence=0.80,
                context=line_text.strip()[:80],
            ))
        
        # 参数过多
        if param_count > self.spec.code_quality.max_parameters:
            line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
            self.issues.append(Issue(
                rule_id='code_quality.too_many_parameters',
                severity=Severity.WARNING,
                line=node.lineno,
                column=node.col_offset,
                message=f'参数过多 ({param_count} 个，限制 {self.spec.code_quality.max_parameters} 个)',
                fix='使用对象封装参数',
                confidence=0.85,
                context=line_text.strip()[:80],
            ))
        
        # 嵌套过深
        if nesting_depth > self.spec.code_quality.max_nesting_depth:
            line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
            self.issues.append(Issue(
                rule_id='code_quality.deep_nesting',
                severity=Severity.WARNING,
                line=node.lineno,
                column=node.col_offset,
                message=f'嵌套过深 (深度 {nesting_depth}，限制 {self.spec.code_quality.max_nesting_depth})',
                fix='提取为独立函数或使用 early return',
                confidence=0.80,
                context=line_text.strip()[:80],
            ))
    
    def _check_exception_handler(self, node, lines):
        """检查异常处理"""
        line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
        
        # 裸 except
        if node.type is None:
            self.issues.append(Issue(
                rule_id='ai_slop.bare_except',
                severity=Severity.HIGH,
                line=node.lineno,
                column=node.col_offset,
                message='检测到裸 except，应捕获具体异常类型',
                fix='捕获具体异常类型，如 except ValueError:',
                confidence=0.95,
                context=line_text.strip()[:80],
            ))
        
        # 异常吞没
        if node.body and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.issues.append(Issue(
                rule_id='ai_slop.swallow_exception',
                severity=Severity.HIGH,
                line=node.lineno,
                column=node.col_offset,
                message='异常被吞没，可能导致难以调试的问题',
                fix='记录日志并重新抛出',
                confidence=0.90,
                context=line_text.strip()[:80],
            ))
    
    def _analyze_patterns(self, code: str):
        """文本模式匹配"""
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # 安全检查
            for rule_id, rule in self.SECURITY_RULES.items():
                if re.search(rule['pattern'], line, re.IGNORECASE):
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
            
            # 错误处理检查
            for rule_id, rule in self.ERROR_HANDLING_RULES.items():
                if re.search(rule['pattern'], line, re.IGNORECASE):
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
            
            # TODO 检查
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
