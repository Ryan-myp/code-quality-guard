"""Load, validate, and save project quality specifications."""

from dataclasses import asdict, dataclass, field
from math import isfinite
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


SEVERITY_LEVELS = ("critical", "high", "warning", "info")


@dataclass
class SecuritySpec:
    """Settings for security findings."""

    # Findings at this level and more severe are reported.
    max_severity: str = "info"
    ignore_patterns: List[str] = field(
        default_factory=lambda: ["test_*.py", "__init__.py", "conftest.py"]
    )


@dataclass
class CodeQualitySpec:
    """Thresholds for structural Python checks."""

    max_function_length: int = 50
    max_nesting_depth: int = 4
    max_parameters: int = 7
    max_line_length: int = 100
    require_docstrings: bool = False


@dataclass
class QualityGateSpec:
    """Issue-count limits used by the quality gate."""

    max_critical: int = 0
    max_high: int = 5
    max_warning: int = 20
    max_info: int = 100
    min_confidence: float = 0.7
    forbidden_rules: List[str] = field(default_factory=list)


@dataclass
class ProjectSpec:
    """Complete project quality policy."""

    name: str = "default"
    language: str = "python"
    security: SecuritySpec = field(default_factory=SecuritySpec)
    code_quality: CodeQualitySpec = field(default_factory=CodeQualitySpec)
    quality_gate: QualityGateSpec = field(default_factory=QualityGateSpec)

    def validate(self) -> List[str]:
        errors = []
        if not isinstance(self.name, str) or not self.name.strip():
            errors.append("name must be a non-empty string")
        if not isinstance(self.language, str) or not self.language.strip():
            errors.append("language must be a non-empty string")
        if self.security.max_severity not in SEVERITY_LEVELS:
            errors.append(
                "security.max_severity must be one of {}".format(", ".join(SEVERITY_LEVELS))
            )
        if not isinstance(self.security.ignore_patterns, list) or not all(
            isinstance(pattern, str) and pattern for pattern in self.security.ignore_patterns
        ):
            errors.append("security.ignore_patterns must be a list of non-empty strings")
        for name in ("max_function_length", "max_nesting_depth", "max_line_length"):
            value = getattr(self.code_quality, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                errors.append("code_quality.{} must be a positive integer".format(name))
        if (
            isinstance(self.code_quality.max_parameters, bool)
            or not isinstance(self.code_quality.max_parameters, int)
            or self.code_quality.max_parameters < 0
        ):
            errors.append("code_quality.max_parameters must be a non-negative integer")
        if not isinstance(self.code_quality.require_docstrings, bool):
            errors.append("code_quality.require_docstrings must be a boolean")
        for name in ("max_critical", "max_high", "max_warning", "max_info"):
            value = getattr(self.quality_gate, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append("quality_gate.{} must be a non-negative integer".format(name))
        if (
            isinstance(self.quality_gate.min_confidence, bool)
            or not isinstance(self.quality_gate.min_confidence, (int, float))
            or not isfinite(self.quality_gate.min_confidence)
            or not 0 <= self.quality_gate.min_confidence <= 1
        ):
            errors.append("quality_gate.min_confidence must be between 0 and 1")
        if not isinstance(self.quality_gate.forbidden_rules, list) or not all(
            isinstance(rule, str) and rule for rule in self.quality_gate.forbidden_rules
        ):
            errors.append("quality_gate.forbidden_rules must be a list of non-empty strings")
        return errors


class SpecParser:
    """Parse YAML project specs and infer a basic spec from a project tree."""

    def __init__(self, spec_path: Optional[Path] = None):
        self.spec_path = Path(spec_path) if spec_path is not None else None
        self.spec: Optional[ProjectSpec] = None

    def load(self, path: Optional[Path] = None) -> ProjectSpec:
        spec_file = Path(path) if path is not None else self.spec_path
        if spec_file is None:
            self.spec = ProjectSpec()
            return self.spec
        if not spec_file.is_file():
            raise FileNotFoundError("Spec file does not exist: {}".format(spec_file))
        with spec_file.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
        self.spec = self._parse_spec(data)
        errors = self.spec.validate()
        if errors:
            raise ValueError("Invalid spec: {}".format("; ".join(errors)))
        return self.spec

    @staticmethod
    def _section(data: Dict[str, Any], name: str) -> Dict[str, Any]:
        section = data.get(name, {})
        if not isinstance(section, dict):
            raise ValueError("{} must be a mapping".format(name))
        return section

    @staticmethod
    def _check_keys(data: Dict[str, Any], allowed: set, section: str) -> None:
        if any(not isinstance(key, str) for key in data):
            raise ValueError("{} keys must be strings".format(section))
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(
                "Unsupported {} setting(s): {}".format(section, ", ".join(unknown))
            )

    def _parse_spec(self, data: Any) -> ProjectSpec:
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError("Spec document must be a mapping")
        self._check_keys(
            data,
            {"name", "language", "security", "code_quality", "quality_gate"},
            "top-level",
        )
        security_data = self._section(data, "security")
        quality_data = self._section(data, "code_quality")
        gate_data = self._section(data, "quality_gate")
        self._validate_section_keys(security_data, quality_data, gate_data)
        return ProjectSpec(
            name=data.get("name", "default"),
            language=data.get("language", "python"),
            security=self._parse_security(security_data),
            code_quality=self._parse_code_quality(quality_data),
            quality_gate=self._parse_quality_gate(gate_data),
        )

    def _validate_section_keys(
        self,
        security: Dict[str, Any],
        code_quality: Dict[str, Any],
        quality_gate: Dict[str, Any],
    ) -> None:
        self._check_keys(security, {"max_severity", "ignore_patterns"}, "security")
        self._check_keys(
            code_quality,
            {
                "max_function_length",
                "max_nesting_depth",
                "max_parameters",
                "max_line_length",
                "require_docstrings",
            },
            "code_quality",
        )
        self._check_keys(
            quality_gate,
            {
                "max_critical",
                "max_high",
                "max_warning",
                "max_info",
                "min_confidence",
                "forbidden_rules",
            },
            "quality_gate",
        )

    @staticmethod
    def _parse_security(data: Dict[str, Any]) -> SecuritySpec:
        return SecuritySpec(
            max_severity=data.get("max_severity", "info"),
            ignore_patterns=data.get("ignore_patterns", SecuritySpec().ignore_patterns),
        )

    @staticmethod
    def _parse_code_quality(data: Dict[str, Any]) -> CodeQualitySpec:
        return CodeQualitySpec(
            max_function_length=data.get("max_function_length", 50),
            max_nesting_depth=data.get("max_nesting_depth", 4),
            max_parameters=data.get("max_parameters", 7),
            max_line_length=data.get("max_line_length", 100),
            require_docstrings=data.get("require_docstrings", False),
        )

    @staticmethod
    def _parse_quality_gate(data: Dict[str, Any]) -> QualityGateSpec:
        return QualityGateSpec(
            max_critical=data.get("max_critical", 0),
            max_high=data.get("max_high", 5),
            max_warning=data.get("max_warning", 20),
            max_info=data.get("max_info", 100),
            min_confidence=data.get("min_confidence", 0.7),
            forbidden_rules=data.get("forbidden_rules", []),
        )

    def save(self, path: Optional[Path] = None) -> Path:
        spec_file = Path(path) if path is not None else self.spec_path
        if spec_file is None:
            raise ValueError("No spec file path provided")
        if self.spec is None:
            raise ValueError("No project spec is loaded")
        errors = self.spec.validate()
        if errors:
            raise ValueError("Invalid spec: {}".format("; ".join(errors)))
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(
            yaml.safe_dump(
                {
                    "name": self.spec.name,
                    "language": self.spec.language,
                    "security": asdict(self.spec.security),
                    "code_quality": asdict(self.spec.code_quality),
                    "quality_gate": asdict(self.spec.quality_gate),
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        return spec_file

    def auto_generate(self, project_path: Path) -> ProjectSpec:
        language = self._detect_language(Path(project_path))
        spec = ProjectSpec(language=language)
        if language == "typescript":
            spec.code_quality.max_function_length = 40
            spec.code_quality.max_parameters = 6
        self.spec = spec
        return spec

    @staticmethod
    def _detect_language(project_path: Path) -> str:
        if (project_path / "pyproject.toml").exists() or any(project_path.glob("*.py")):
            return "python"
        if (project_path / "package.json").exists():
            return "typescript"
        if (project_path / "go.mod").exists():
            return "go"
        if (project_path / "Cargo.toml").exists():
            return "rust"
        return "python"
