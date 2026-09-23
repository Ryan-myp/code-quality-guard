"""
规范解析器 - 定义项目的质量标准
"""
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class SecuritySpec:
    """安全规范"""
    max_severity: str = "critical"  # critical, high, warning, info
    ignore_patterns: List[str] = field(default_factory=lambda: [
        "test_*.py",
        "__init__.py",
        "conftest.py",
    ])
    allowed_eval_contexts: List[str] = field(default_factory=lambda: [
        "ast.literal_eval",
        "json.loads",
    ])


@dataclass
class CodeQualitySpec:
    """代码质量规范"""
    max_function_length: int = 50
    max_nesting_depth: int = 4
    max_parameters: int = 7
    max_line_length: int = 100
    require_docstrings: bool = True
    max_todo_age_days: int = 30


@dataclass
class ProjectSpec:
    """项目规范"""
    name: str = "default"
    language: str = "python"
    security: SecuritySpec = field(default_factory=SecuritySpec)
    code_quality: CodeQualitySpec = field(default_factory=CodeQualitySpec)
    feedback: Dict[str, Any] = field(default_factory=lambda: {
        "enable_learning": True,
        "min_confidence": 0.7,
    })
    
    def validate(self) -> List[str]:
        """验证规范配置"""
        errors = []
        
        if self.security.max_severity not in ["critical", "high", "warning", "info"]:
            errors.append(f"Invalid severity level: {self.security.max_severity}")
        
        if self.code_quality.max_function_length < 10:
            errors.append("max_function_length must be >= 10")
        
        if self.code_quality.max_nesting_depth < 1:
            errors.append("max_nesting_depth must be >= 1")
        
        return errors


class SpecParser:
    """规范解析器"""
    
    def __init__(self, spec_path: Optional[Path] = None):
        self.spec_path = spec_path
        self.spec: Optional[ProjectSpec] = None
    
    def load(self, path: Optional[Path] = None) -> ProjectSpec:
        """加载规范"""
        spec_file = path or self.spec_path
        
        if spec_file and spec_file.exists():
            with open(spec_file, 'r') as f:
                data = yaml.safe_load(f)
            self.spec = self._parse_spec(data)
        else:
            # 使用默认规范
            self.spec = ProjectSpec()
        
        return self.spec
    
    def _parse_spec(self, data: Dict[str, Any]) -> ProjectSpec:
        """解析规范数据"""
        spec = ProjectSpec(
            name=data.get('name', 'default'),
            language=data.get('language', 'python'),
        )
        
        # 解析安全规范
        if 'security' in data:
            sec_data = data['security']
            spec.security = SecuritySpec(
                max_severity=sec_data.get('max_severity', 'critical'),
                ignore_patterns=sec_data.get('ignore_patterns', []),
                allowed_eval_contexts=sec_data.get('allowed_eval_contexts', []),
            )
        
        # 解析代码质量规范
        if 'code_quality' in data:
            cq_data = data['code_quality']
            spec.code_quality = CodeQualitySpec(
                max_function_length=cq_data.get('max_function_length', 50),
                max_nesting_depth=cq_data.get('max_nesting_depth', 4),
                max_parameters=cq_data.get('max_parameters', 7),
                max_line_length=cq_data.get('max_line_length', 100),
                require_docstrings=cq_data.get('require_docstrings', True),
                max_todo_age_days=cq_data.get('max_todo_age_days', 30),
            )
        
        # 解析反馈配置
        if 'feedback' in data:
            spec.feedback = data['feedback']
        
        return spec
    
    def save(self, path: Optional[Path] = None) -> Path:
        """保存规范"""
        spec_file = path or self.spec_path
        
        if not spec_file:
            raise ValueError("No spec file path provided")
        
        data = {
            'name': self.spec.name,
            'language': self.spec.language,
            'security': {
                'max_severity': self.spec.security.max_severity,
                'ignore_patterns': self.spec.security.ignore_patterns,
                'allowed_eval_contexts': self.spec.security.allowed_eval_contexts,
            },
            'code_quality': {
                'max_function_length': self.spec.code_quality.max_function_length,
                'max_nesting_depth': self.spec.code_quality.max_nesting_depth,
                'max_parameters': self.spec.code_quality.max_parameters,
                'max_line_length': self.spec.code_quality.max_line_length,
                'require_docstrings': self.spec.code_quality.require_docstrings,
                'max_todo_age_days': self.spec.code_quality.max_todo_age_days,
            },
            'feedback': self.spec.feedback,
        }
        
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        with open(spec_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        
        return spec_file
    
    def auto_generate(self, project_path: Path) -> ProjectSpec:
        """根据项目自动推断规范"""
        # 检测语言
        language = self._detect_language(project_path)
        
        # 根据语言调整默认规范
        spec = ProjectSpec(language=language)
        
        if language == 'python':
            spec.code_quality.max_function_length = 50
            spec.code_quality.max_parameters = 7
        elif language == 'typescript':
            spec.code_quality.max_function_length = 40
            spec.code_quality.max_parameters = 6
        
        return spec
    
    def _detect_language(self, project_path: Path) -> str:
        """检测项目语言"""
        if (project_path / 'pyproject.toml').exists():
            return 'python'
        elif (project_path / 'package.json').exists():
            return 'typescript'
        elif (project_path / 'go.mod').exists():
            return 'go'
        elif (project_path / 'Cargo.toml').exists():
            return 'rust'
        else:
            return 'unknown'
