"""Command-line interface for Code Quality Guard."""

import argparse
import json
import math
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.agent_ruleset import generate_agent_rules
from engines.enhanced_analyzer import EnhancedAnalyzer, Issue, Severity
from engines.fix_suggester import FixSuggester
from engines.go_analyzer import GoAnalyzer
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

TEST_TIMEOUT_SECONDS = 300


@dataclass
class ScanAnalysis:
    """Language-neutral scan results used to combine analyzer outputs."""

    files: List[Path]
    file_results: Dict[str, List[Dict[str, Any]]]
    issues: List[Issue]
    scan_errors: List[Dict[str, str]]
    fail_on_any_rules: List[str]


def discover_files(project_path: Path, extensions: Optional[List[str]] = None) -> List[Path]:
    """Discover supported Python or Go source files."""
    project_path = Path(project_path)
    selected_extensions = [extension.lower() for extension in (extensions or [".py"])]
    unsupported = set(selected_extensions) - {".py", ".go"}
    if unsupported:
        raise ValueError(
            "Unsupported source extension(s): {}. Supported extensions are .py and .go.".format(
                ", ".join(sorted(unsupported))
            )
        )
    if not project_path.exists():
        raise FileNotFoundError("Path does not exist: {}".format(project_path))
    if project_path.is_file():
        if project_path.suffix.lower() not in selected_extensions:
            raise ValueError(
                "Unsupported source file '{}'; expected one of {}.".format(
                    project_path, ", ".join(selected_extensions)
                )
            )
        return [project_path]
    if not project_path.is_dir():
        raise ValueError("Path is not a regular file or directory: {}".format(project_path))

    files = []
    for path in project_path.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in selected_extensions:
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


def _summarize_issues(issues: List[Issue]) -> Dict[str, Any]:
    by_severity = {
        severity.value: sum(1 for issue in issues if issue.severity == severity)
        for severity in Severity
    }
    by_rule: Dict[str, int] = {}
    for issue in issues:
        by_rule[issue.rule_id] = by_rule.get(issue.rule_id, 0) + 1
    return {
        "total_issues": len(issues),
        "by_severity": by_severity,
        "by_rule": by_rule,
    }


def _evaluate_gate(
    spec: ProjectSpec,
    issues: List[Issue],
    scan_errors: List[Dict[str, str]],
    min_score: Optional[float],
    fail_on_any_rules: Optional[List[str]] = None,
):
    gate = QualityGate(GateConfig(**asdict(spec.quality_gate)))
    result = gate.check(issues)
    score = gate.get_score(issues)
    blocking_rules = sorted(
        {
            issue.rule_id
            for issue in issues
            if fail_on_any_rules and issue.rule_id in fail_on_any_rules
        }
    )
    if blocking_rules:
        gate.fail("blocking_findings", rule_ids=blocking_rules)
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


def _run_python_analysis(project_path: Path, spec: ProjectSpec):
    files, file_results, issues, scan_errors, analyzer = _scan_files(
        project_path, spec
    )
    del analyzer
    return ScanAnalysis(
        files,
        file_results,
        issues,
        scan_errors,
        [],
    )


def _run_go_analysis(project_path: Path, spec: ProjectSpec):
    del spec
    files = discover_files(project_path, extensions=[".go"])
    go_result = GoAnalyzer().analyze(project_path, files)
    file_results = {
        file_name: [_issue_to_dict(issue) for issue in issues]
        for file_name, issues in go_result.file_results.items()
    }
    issues = [
        issue
        for file_issues in go_result.file_results.values()
        for issue in file_issues
    ]
    return ScanAnalysis(
        files,
        file_results,
        issues,
        go_result.scan_errors,
        ["go.gofmt", "go.vet"],
    )


LANGUAGE_ANALYZERS = {
    "python": _run_python_analysis,
    "go": _run_go_analysis,
}


def _combine_analyses(analyses: List[ScanAnalysis]) -> ScanAnalysis:
    combined = ScanAnalysis([], {}, [], [], [])
    for analysis in analyses:
        combined.files.extend(analysis.files)
        combined.file_results.update(analysis.file_results)
        combined.issues.extend(analysis.issues)
        combined.scan_errors.extend(analysis.scan_errors)
        for rule_id in analysis.fail_on_any_rules:
            if rule_id not in combined.fail_on_any_rules:
                combined.fail_on_any_rules.append(rule_id)
    return combined


def _test_command(language: str):
    if language == "python":
        return (
            [sys.executable, "-m", "pytest"],
            [Path(sys.executable).name, "-m", "pytest"],
            None,
        )

    executable = shutil.which("go")
    return (
        [executable or "go", "test", "./..."],
        ["go", "test", "./..."],
        "Go command is not available on PATH." if executable is None else None,
    )


def _run_single_test(
    project_root: Path, language: str
) -> Dict[str, Any]:
    command, display_command, executable_error = _test_command(language)
    result = {
        "language": language,
        "command": display_command,
        "status": "error",
        "exit_code": None,
    }
    if executable_error:
        result["reason"] = executable_error
        return result

    try:
        completed = subprocess.run(
            command,
            cwd=str(project_root),
            timeout=TEST_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["reason"] = "Timed out after {} seconds.".format(
            TEST_TIMEOUT_SECONDS
        )
    except OSError as error:
        result["reason"] = "{} while starting test command.".format(
            type(error).__name__
        )
    else:
        result["exit_code"] = completed.returncode
        result["status"] = "passed" if completed.returncode == 0 else "failed"
    return result


def _run_project_tests(
    project_path: Path, languages: List[str]
) -> List[Dict[str, Any]]:
    project_root = project_path if project_path.is_dir() else project_path.parent
    return [
        _run_single_test(project_root, language)
        for language in languages
    ]


def _build_analysis_report(
    project_path: Path,
    language: str,
    spec: ProjectSpec,
    analysis: ScanAnalysis,
    min_score: Optional[float],
    tests_requested: bool,
    test_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    gate, gate_result, quality_score = _evaluate_gate(
        spec,
        analysis.issues,
        analysis.scan_errors,
        min_score,
        fail_on_any_rules=analysis.fail_on_any_rules,
    )
    gate_result = _apply_test_results(gate, gate_result, test_results)
    summary = _summarize_issues(analysis.issues)
    suggestions = FixSuggester().prioritize(
        FixSuggester().suggest_batch(analysis.issues)
    )
    return {
        "project": str(project_path),
        "language": language,
        "files_found": len(analysis.files),
        "files_scanned": len(analysis.file_results),
        "files_with_issues": sum(
            bool(items) for items in analysis.file_results.values()
        ),
        "total_issues": len(analysis.issues),
        "gate_result": gate_result.value,
        "gate_details": gate.details,
        "quality_score": quality_score,
        "quality_badge": gate.get_badge(quality_score),
        "issues_by_severity": summary["by_severity"],
        "file_results": analysis.file_results,
        "scan_errors": analysis.scan_errors,
        "suggestions": suggestions,
        "summary": summary,
        "verification": {
            "tests_requested": tests_requested,
            "tests": test_results,
        },
    }


def _apply_test_results(gate, gate_result, test_results):
    failed_tests = [
        result for result in test_results if result["status"] != "passed"
    ]
    if not failed_tests:
        return gate_result
    gate.fail(
        "project_tests_failed",
        tests=failed_tests,
        prior_gate_result=gate_result.value,
        prior_gate_details=dict(gate.details),
    )
    return gate.result


def _languages_for_spec(spec: ProjectSpec) -> List[str]:
    language_groups = {
        "python": ["python"],
        "py": ["python"],
        "go": ["go"],
        "golang": ["go"],
        "mixed": ["python", "go"],
    }
    languages = language_groups.get(spec.language.lower())
    if languages is None:
        raise ValueError(
            "Unsupported language '{}': the analyzer supports Python and Go, "
            "including mixed projects.".format(spec.language)
        )
    return languages


def _validate_analysis_options(
    spec: ProjectSpec, min_score: Optional[float], run_tests: bool
) -> List[str]:
    validation_errors = spec.validate()
    if validation_errors:
        raise ValueError("Invalid project spec: {}".format("; ".join(validation_errors)))
    if not isinstance(run_tests, bool):
        raise ValueError("run_tests must be a boolean")
    if min_score is not None and (
        isinstance(min_score, bool)
        or not isinstance(min_score, (int, float))
        or not math.isfinite(min_score)
        or not 0 <= min_score <= 100
    ):
        raise ValueError("min_score must be a finite number from 0 to 100")
    return _languages_for_spec(spec)


def run_analysis(
    project_path: Path,
    spec: ProjectSpec,
    verbose: bool = False,
    min_score: Optional[float] = None,
    run_tests: bool = False,
) -> Dict[str, Any]:
    """Scan supported project languages and optionally execute their test suites."""
    project_path = Path(project_path)
    languages = _validate_analysis_options(spec, min_score, run_tests)
    analysis = _combine_analyses(
        [
            LANGUAGE_ANALYZERS[language](project_path, spec)
            for language in languages
        ]
    )
    test_results = (
        _run_project_tests(project_path, languages) if run_tests else []
    )
    return _build_analysis_report(
        project_path,
        spec.language.lower()
        if spec.language.lower() == "mixed"
        else languages[0],
        spec,
        analysis,
        min_score,
        run_tests,
        test_results,
    )


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
        description="Code Quality Guard: Python and Go checks for coding agents"
    )
    parser.add_argument(
        "path",
        help="Python/Go project directory or Python source file",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="List scanned files")
    parser.add_argument("--spec-only", action="store_true", help="Generate a project spec")
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Run the detected project's pytest and/or go test suite",
    )
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
    if project_path.suffix.lower() == ".go":
        return ProjectSpec(language="go")
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
    for check in result.get("verification", {}).get("tests", []):
        command = " ".join(check["command"])
        print(
            "测试验证 ({}): {} [{}]".format(
                check["language"], check["status"].upper(), command
            )
        )
        if check.get("reason"):
            print("测试说明: {}".format(check["reason"]))
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
    if args.spec_only and args.run_tests:
        print("错误: --spec-only 不能与 --run-tests 同时使用", file=sys.stderr)
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
            run_tests=args.run_tests,
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        print("错误: {}".format(error), file=sys.stderr)
        return 2
    return _finish_scan(args, project_path, result)


if __name__ == "__main__":
    sys.exit(main())
