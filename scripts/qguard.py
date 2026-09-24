"""Command-line interface for Code Quality Guard."""

import argparse
import json
import math
import sys
from dataclasses import asdict
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.agent_ruleset import generate_agent_rules
from engines.enhanced_analyzer import EnhancedAnalyzer, Issue
from engines.fix_suggester import FixSuggester
from engines.quality_gate import GateConfig, QualityGate
from engines.sarif_generator import generate_sarif
from engines.spec_parser import ProjectSpec, SpecParser


EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".idea",
    ".tox",
}


def discover_files(project_path: Path, extensions: Optional[List[str]] = None) -> List[Path]:
    """Discover supported source files. The analyzer currently supports Python only."""
    project_path = Path(project_path)
    if extensions is not None and any(extension != ".py" for extension in extensions):
        raise ValueError("Only Python (.py) files are supported")
    if not project_path.exists():
        raise FileNotFoundError("Path does not exist: {}".format(project_path))
    if project_path.is_file():
        if project_path.suffix.lower() != ".py":
            raise ValueError("Only Python (.py) files are supported: {}".format(project_path))
        return [project_path]
    if not project_path.is_dir():
        raise ValueError("Path is not a regular file or directory: {}".format(project_path))

    files = []
    for path in project_path.rglob("*.py"):
        if not path.is_file():
            continue
        try:
            relative_parts = path.relative_to(project_path).parts
        except ValueError:
            continue
        if any(
            part in EXCLUDED_DIRECTORIES or part.startswith(".")
            for part in relative_parts[:-1]
        ):
            continue
        files.append(path)
    return sorted(files)


def _is_ignored(path: Path, root: Path, patterns: List[str]) -> bool:
    try:
        relative = path.relative_to(root).as_posix() if root.is_dir() else path.name
    except ValueError:
        relative = path.as_posix()
    return any(
        fnmatchcase(relative, pattern) or fnmatchcase(path.name, pattern)
        for pattern in patterns
    )


def _file_key(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix() if root.is_dir() else path.name
    except ValueError:
        return str(path)


def _issue_to_dict(issue: Issue) -> Dict[str, Any]:
    return {
        "rule_id": issue.rule_id,
        "severity": issue.severity.value,
        "line": issue.line,
        "column": issue.column,
        "message": issue.message,
        "fix": issue.fix,
        "confidence": issue.confidence,
        "context": issue.context,
    }


def _scan_files(project_path: Path, spec: ProjectSpec):
    files = discover_files(project_path)
    eligible_files = [
        path for path in files
        if not _is_ignored(path, project_path, spec.security.ignore_patterns)
    ]
    file_results: Dict[str, List[Dict[str, Any]]] = {}
    all_issues: List[Issue] = []
    scan_errors: List[Dict[str, str]] = []
    if not eligible_files:
        message = (
            "No Python source files found; the analyzer currently supports .py files only."
            if not files
            else "No Python files remain after applying security.ignore_patterns."
        )
        scan_errors.append({"path": str(project_path), "error": message})

    analyzer = EnhancedAnalyzer(spec)
    for file_path in eligible_files:
        key = _file_key(file_path, project_path)
        try:
            code = file_path.read_text(encoding="utf-8")
            issues = analyzer.analyze(code, file_path)
        except (OSError, UnicodeError, SyntaxError) as error:
            scan_errors.append(
                {
                    "path": key,
                    "error": "{}: {}".format(type(error).__name__, error),
                }
            )
            continue
        file_results[key] = [_issue_to_dict(issue) for issue in issues]
        all_issues.extend(issues)
    return files, file_results, all_issues, scan_errors, analyzer


def _evaluate_gate(
    spec: ProjectSpec,
    issues: List[Issue],
    scan_errors: List[Dict[str, str]],
    min_score: Optional[float],
):
    gate = QualityGate(GateConfig(**asdict(spec.quality_gate)))
    result = gate.check(issues)
    score = gate.get_score(issues)
    if min_score is not None and score < min_score:
        gate.fail(
            "below_min_score",
            min_score=min_score,
            quality_score=score,
            prior_gate_reason=gate.details.get("reason"),
        )
    if scan_errors:
        gate.fail(
            "scan_errors",
            errors=scan_errors,
        )
    return gate, gate.result or result, score


def run_analysis(
    project_path: Path,
    spec: ProjectSpec,
    verbose: bool = False,
    min_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Scan Python files and fail closed if any file could not be analyzed."""
    project_path = Path(project_path)
    validation_errors = spec.validate()
    if validation_errors:
        raise ValueError("Invalid project spec: {}".format("; ".join(validation_errors)))
    if spec.language.lower() not in ("python", "py"):
        raise ValueError(
            "Unsupported language '{}': the analyzer currently supports Python only.".format(
                spec.language
            )
        )
    if min_score is not None and (
        isinstance(min_score, bool)
        or not isinstance(min_score, (int, float))
        or not math.isfinite(min_score)
        or not 0 <= min_score <= 100
    ):
        raise ValueError("min_score must be a finite number from 0 to 100")
    files, file_results, all_issues, scan_errors, analyzer = _scan_files(
        project_path, spec
    )
    gate, gate_result, quality_score = _evaluate_gate(
        spec, all_issues, scan_errors, min_score
    )
    suggester = FixSuggester()
    summary = analyzer.get_summary(all_issues)
    suggestions = suggester.prioritize(suggester.suggest_batch(all_issues))
    return {
        "project": str(project_path),
        "language": "python",
        "files_found": len(files),
        "files_scanned": len(file_results),
        "files_with_issues": sum(bool(issues) for issues in file_results.values()),
        "total_issues": len(all_issues),
        "gate_result": gate_result.value,
        "gate_details": gate.details,
        "quality_score": quality_score,
        "quality_badge": gate.get_badge(quality_score),
        "issues_by_severity": summary["by_severity"],
        "file_results": file_results,
        "scan_errors": scan_errors,
        "suggestions": suggestions,
        "summary": summary,
    }


def _write_output(output_path: Path, data: Any, output_format: str = "json") -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "yaml":
        content = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    else:
        content = json.dumps(data, indent=2, ensure_ascii=False)
    output_path.write_text(content + "\n", encoding="utf-8")


def _exit_status(result: Dict[str, Any]) -> int:
    return {"pass": 0, "warn": 1, "fail": 2}.get(result["gate_result"], 2)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Code Quality Guard: Python code quality checks for coding agents"
    )
    parser.add_argument("path", help="Python project directory or .py file")
    parser.add_argument("--verbose", "-v", action="store_true", help="List scanned files")
    parser.add_argument("--spec-only", action="store_true", help="Generate a project spec")
    exports = parser.add_mutually_exclusive_group()
    exports.add_argument("--agent-rules", action="store_true", help="Generate agent guidance YAML")
    exports.add_argument("--sarif", action="store_true", help="Generate a SARIF 2.1.0 report")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--config", "-c", help="Project spec YAML file")
    parser.add_argument("--min-score", type=float, help="Fail if quality score is below this value")
    return parser


def _load_spec(project_path: Path, config_path: Optional[str]) -> ProjectSpec:
    spec_parser = SpecParser()
    if config_path:
        return spec_parser.load(Path(config_path).expanduser())
    if project_path.is_dir():
        return spec_parser.auto_generate(project_path)
    return ProjectSpec()


def _save_spec(args: argparse.Namespace, project_path: Path, spec: ProjectSpec) -> int:
    if not project_path.is_dir():
        print("错误: --spec-only 需要项目目录", file=sys.stderr)
        return 2
    spec_parser = SpecParser()
    spec_parser.spec = spec
    output_path = (
        Path(args.output).expanduser() if args.output else project_path / "spec.yaml"
    )
    saved_path = spec_parser.save(output_path)
    print("规范已保存到: {}".format(saved_path))
    return 0


def _finish_scan(args: argparse.Namespace, project_path: Path, result: Dict[str, Any]) -> int:
    if args.verbose:
        for file_name in result["file_results"]:
            print("已扫描: {}".format(file_name))
    for error in result["scan_errors"]:
        print(
            "扫描失败: {}: {}".format(error["path"], error["error"]),
            file=sys.stderr,
        )

    output_path = Path(args.output).expanduser() if args.output else None
    try:
        if args.sarif:
            output_path = output_path or project_path / "report.sarif.json"
            _write_output(output_path, generate_sarif(result, project_path))
            print("SARIF 报告已保存到: {}".format(output_path))
        elif args.agent_rules:
            output_path = output_path or project_path / "agent_rules.yaml"
            _write_output(output_path, generate_agent_rules(result), "yaml")
            print("Agent 规则已保存到: {}".format(output_path))
        elif output_path is not None:
            _write_output(output_path, result)
            print("分析结果已保存到: {}".format(output_path))
    except (OSError, ValueError) as error:
        print("错误: 无法写入输出文件: {}".format(error), file=sys.stderr)
        return 2

    print("扫描文件: {}".format(result["files_scanned"]))
    print("发现问题: {}".format(result["total_issues"]))
    print("质量评分: {} ({})".format(result["quality_score"], result["quality_badge"]))
    print("门禁状态: {}".format(result["gate_result"].upper()))
    return _exit_status(result)


def main(argv: Optional[List[str]] = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args[:1] == ["gate"]:
        raw_args = raw_args[1:]
    parser = _argument_parser()
    args = parser.parse_args(raw_args)
    if args.min_score is not None and not 0 <= args.min_score <= 100:
        print("错误: --min-score 必须在 0 到 100 之间", file=sys.stderr)
        return 2

    project_path = Path(args.path).expanduser().resolve()
    if not project_path.exists():
        print("错误: 路径不存在: {}".format(project_path), file=sys.stderr)
        return 2
    if args.spec_only and (args.agent_rules or args.sarif):
        print("错误: --spec-only 不能与导出选项同时使用", file=sys.stderr)
        return 2

    try:
        spec = _load_spec(project_path, args.config)
        if args.spec_only:
            return _save_spec(args, project_path, spec)
        result = run_analysis(
            project_path,
            spec,
            verbose=args.verbose,
            min_score=args.min_score,
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        print("错误: {}".format(error), file=sys.stderr)
        return 2
    return _finish_scan(args, project_path, result)


if __name__ == "__main__":
    sys.exit(main())
