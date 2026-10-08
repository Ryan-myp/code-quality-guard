import json
import shutil

import pytest

from engines.agent_ruleset import generate_agent_rules
from engines import go_analyzer
from engines.spec_parser import ProjectSpec, SpecParser
from scripts.qguard import discover_files, main, run_analysis


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
