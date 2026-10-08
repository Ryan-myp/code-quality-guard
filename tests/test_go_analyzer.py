import json
import shutil
import subprocess

import pytest

from engines.agent_ruleset import generate_agent_rules
from engines import go_analyzer
from engines.spec_parser import ProjectSpec, SpecParser
from scripts.qguard import _run_project_tests, discover_files, main, run_analysis


GO_AVAILABLE = shutil.which("go") is not None and shutil.which("gofmt") is not None


def write_module(root, source):
    (root / "go.mod").write_text(
        "module example.com/qguard\n\ngo 1.20\n",
        encoding="utf-8",
    )
    (root / "main.go").write_text(source, encoding="utf-8")


def test_discover_files_accepts_go_and_excludes_hidden_directories(tmp_path):
    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")
    hidden = tmp_path / ".generated"
    hidden.mkdir()
    (hidden / "ignored.go").write_text("package ignored\n", encoding="utf-8")

    assert discover_files(tmp_path, extensions=[".go"]) == [tmp_path / "main.go"]


def test_spec_parser_detects_go_module(tmp_path):
    (tmp_path / "go.mod").write_text(
        "module example.com/qguard\n\ngo 1.20\n",
        encoding="utf-8",
    )

    assert SpecParser().auto_generate(tmp_path).language == "go"


def test_mixed_project_is_detected_and_scanned_by_each_analyzer(tmp_path):
    write_module(tmp_path, "package main\nfunc main() {}\n")
    (tmp_path / "helper.py").write_text("eval(source)\n", encoding="utf-8")

    spec = SpecParser().auto_generate(tmp_path)
    result = run_analysis(tmp_path, spec)

    assert spec.language == "mixed"
    assert result["language"] == "mixed"
    assert result["files_scanned"] == 2
    assert "helper.py" in result["file_results"]
    assert "main.go" in result["file_results"]
    assert any(
        issue["rule_id"] == "security.eval_exec"
        for issue in result["file_results"]["helper.py"]
    )
    assert result["scan_errors"] == []


@pytest.mark.skipif(not GO_AVAILABLE, reason="Go toolchain is not installed")
def test_go_analysis_reports_format_and_vet_findings(tmp_path):
    write_module(
        tmp_path,
        'package main\nimport "fmt"\nfunc main(){fmt.Printf("%d", "wrong")}\n',
    )

    result = run_analysis(tmp_path, ProjectSpec(language="go"))

    assert result["language"] == "go"
    assert result["files_found"] == 1
    assert result["files_scanned"] == 1
    assert result["scan_errors"] == []
    assert result["gate_result"] == "fail"
    rules = {
        issue["rule_id"]
        for issue in result["file_results"]["main.go"]
    }
    assert "go.gofmt" in rules
    assert "go.vet" in rules


@pytest.mark.skipif(not GO_AVAILABLE, reason="Go toolchain is not installed")
def test_gofmt_findings_fail_the_gate_without_other_issues(tmp_path):
    write_module(tmp_path, 'package main\nfunc main(){println("ok")}\n')

    result = run_analysis(tmp_path, ProjectSpec(language="go"))

    assert result["gate_result"] == "fail"
    assert result["summary"]["by_rule"] == {"go.gofmt": 1}


@pytest.mark.skipif(not GO_AVAILABLE, reason="Go toolchain is not installed")
def test_go_analysis_passes_for_clean_module(tmp_path):
    write_module(
        tmp_path,
        "package main\n\nfunc add(left, right int) int {\n\treturn left + right\n}\n",
    )

    result = run_analysis(tmp_path, ProjectSpec(language="go"))

    assert result["files_scanned"] == 1
    assert result["total_issues"] == 0
    assert result["scan_errors"] == []
    assert result["gate_result"] == "pass"


@pytest.mark.skipif(not GO_AVAILABLE, reason="Go toolchain is not installed")
def test_opt_in_go_tests_are_reported_and_block_on_failure(tmp_path):
    write_module(tmp_path, "package main\nfunc main() {}\n")
    (tmp_path / "main_test.go").write_text(
        'package main\nimport "testing"\nfunc TestFailure(t *testing.T) { t.Fatal("expected failure") }\n',
        encoding="utf-8",
    )

    result = run_analysis(
        tmp_path,
        ProjectSpec(language="go"),
        run_tests=True,
    )

    assert result["verification"]["tests"][0]["language"] == "go"
    assert result["verification"]["tests"][0]["status"] == "failed"
    assert result["gate_result"] == "fail"


@pytest.mark.skipif(not GO_AVAILABLE, reason="Go toolchain is not installed")
def test_opt_in_go_tests_can_pass(tmp_path):
    write_module(tmp_path, "package main\n\nfunc main() {}\n")
    (tmp_path / "main_test.go").write_text(
        'package main\n\nimport "testing"\n\nfunc TestSuccess(t *testing.T) {}\n',
        encoding="utf-8",
    )

    result = run_analysis(
        tmp_path,
        ProjectSpec(language="go"),
        run_tests=True,
    )

    assert result["verification"]["tests"][0]["status"] == "passed"
    assert result["gate_result"] == "pass"


def test_go_analysis_fails_closed_without_module_root(tmp_path):
    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")

    result = run_analysis(tmp_path, ProjectSpec(language="go"))

    assert result["gate_result"] == "fail"
    assert result["scan_errors"]
    assert "go.mod" in result["scan_errors"][0]["error"]


def test_cli_reports_module_root_requirement_for_a_go_file(tmp_path, capsys):
    source = tmp_path / "main.go"
    source.write_text("package main\n", encoding="utf-8")

    status = main([str(source)])

    assert status == 2
    assert "Go scans require a module directory containing go.mod." in capsys.readouterr().err


def test_go_analysis_fails_closed_when_go_toolchain_is_missing(tmp_path, monkeypatch):
    write_module(tmp_path, "package main\n")
    original_which = shutil.which

    def find_tool(name):
        if name == "go":
            return None
        return original_which(name)

    monkeypatch.setattr(go_analyzer.shutil, "which", find_tool)

    result = run_analysis(tmp_path, ProjectSpec(language="go"))

    assert result["gate_result"] == "fail"
    assert any("not found" in item["error"].lower() for item in result["scan_errors"])


@pytest.mark.skipif(not GO_AVAILABLE, reason="Go toolchain is not installed")
def test_go_cli_exports_vet_findings_to_sarif(tmp_path):
    write_module(
        tmp_path,
        'package main\nimport "fmt"\nfunc main(){fmt.Printf("%d", "wrong")}\n',
    )
    output = tmp_path / "report.sarif"

    status = main([str(tmp_path), "--sarif", "--output", str(output)])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert status == 2
    rule_ids = {item["ruleId"] for item in report["runs"][0]["results"]}
    assert rule_ids == {"go.gofmt", "go.vet"}


@pytest.mark.skipif(not GO_AVAILABLE, reason="Go toolchain is not installed")
def test_go_vet_reports_diagnostics_from_subpackages(tmp_path):
    write_module(tmp_path, "package main\n\nfunc main() {}\n")
    subpackage = tmp_path / "internal" / "sample"
    subpackage.mkdir(parents=True)
    (subpackage / "sample.go").write_text(
        'package sample\nimport "fmt"\nfunc Log() { fmt.Printf("%d", "wrong") }\n',
        encoding="utf-8",
    )

    result = run_analysis(tmp_path, ProjectSpec(language="go"))

    assert "internal/sample/sample.go" in result["file_results"]
    assert any(
        issue["rule_id"] == "go.vet"
        for issue in result["file_results"]["internal/sample/sample.go"]
    )


def test_agent_rules_preserve_scanned_language():
    result = {
        "language": "go",
        "gate_result": "pass",
        "file_results": {},
        "scan_errors": [],
    }

    assert generate_agent_rules(result)["language"] == "go"


def test_agent_rules_merge_language_specific_baselines_for_mixed_projects():
    result = {
        "language": "mixed",
        "gate_result": "pass",
        "file_results": {},
        "scan_errors": [],
    }

    rules = generate_agent_rules(result)

    assert rules["language"] == "mixed"
    assert any("eval()" in item for item in rules["security_baseline"])
    assert any("shell commands" in item for item in rules["security_baseline"])
    assert len(rules["security_baseline"]) == len(set(rules["security_baseline"]))


def test_cli_run_tests_reports_failure_and_fails_gate(tmp_path, monkeypatch, capsys):
    (tmp_path / "app.py").write_text("eval(source)\n", encoding="utf-8")

    def fail_tests(command, **kwargs):
        assert command[-2:] == ["-m", "pytest"]
        return type("Completed", (), {"returncode": 1})()

    monkeypatch.setattr("scripts.qguard.subprocess.run", fail_tests)
    output = tmp_path / "report.json"

    status = main([str(tmp_path), "--run-tests", "--output", str(output)])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert status == 2
    assert report["verification"]["tests_requested"] is True
    assert report["verification"]["tests"][0]["status"] == "failed"
    assert report["gate_result"] == "fail"
    assert report["gate_details"]["prior_gate_result"] == "fail"
    assert report["gate_details"]["prior_gate_details"]["reason"] == "too_many_critical"
    assert "测试验证" in capsys.readouterr().out


def test_spec_only_rejects_run_tests_flag(tmp_path, capsys):
    status = main([str(tmp_path), "--spec-only", "--run-tests"])

    assert status == 2
    assert "--spec-only" in capsys.readouterr().err


def test_project_test_runner_reports_timeout(tmp_path, monkeypatch):
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("scripts.qguard.subprocess.run", timeout)

    result = _run_project_tests(tmp_path, ["python"])

    assert result[0]["status"] == "timeout"
    assert "Timed out" in result[0]["reason"]


def test_project_test_runner_reports_startup_errors(tmp_path, monkeypatch):
    def fail_to_start(command, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("scripts.qguard.subprocess.run", fail_to_start)

    result = _run_project_tests(tmp_path, ["python"])

    assert result[0]["status"] == "error"
    assert "OSError" in result[0]["reason"]


def test_project_test_runner_marks_missing_go_tool_as_error(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.qguard.shutil.which", lambda _: None)

    result = _run_project_tests(tmp_path, ["go"])

    assert result[0]["status"] == "error"
    assert "not available" in result[0]["reason"]


def test_project_test_runner_runs_each_language_for_mixed_projects(
    tmp_path, monkeypatch
):
    commands = []

    def pass_tests(command, **kwargs):
        commands.append(command)
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr("scripts.qguard.subprocess.run", pass_tests)
    monkeypatch.setattr("scripts.qguard.shutil.which", lambda _: "/usr/bin/go")

    results = _run_project_tests(tmp_path, ["python", "go"])

    assert [result["status"] for result in results] == ["passed", "passed"]
    assert commands[0][-2:] == ["-m", "pytest"]
    assert commands[1][-2:] == ["test", "./..."]
