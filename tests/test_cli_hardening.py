import json
from pathlib import Path

import pytest

from engines.spec_parser import ProjectSpec, SecuritySpec
from engines.sarif_generator import generate_sarif
from scripts.qguard import discover_files, main, run_analysis


def test_discover_files_accepts_a_single_python_file(tmp_path):
    target = tmp_path / "one.py"
    target.write_text("value = 1\n", encoding="utf-8")

    assert discover_files(target) == [target]


def test_discover_files_rejects_unsupported_single_file(tmp_path):
    target = tmp_path / "one.ts"
    target.write_text("const value = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Python"):
        discover_files(target)


def test_discover_files_excludes_generated_and_hidden_directories(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("value = 1\n", encoding="utf-8")
    for directory in (".git", ".venv", "node_modules", "__pycache__"):
        excluded = tmp_path / directory
        excluded.mkdir()
        (excluded / "skip.py").write_text("value = 1\n", encoding="utf-8")

    assert [path.name for path in discover_files(tmp_path)] == ["ok.py"]


def test_discover_files_ignores_directories_named_with_python_extension(tmp_path):
    python_named_directory = tmp_path / "generated.py"
    python_named_directory.mkdir()
    (python_named_directory / "child.py").write_text("value = 1\n", encoding="utf-8")

    assert discover_files(tmp_path) == [python_named_directory / "child.py"]


def test_run_analysis_aggregates_findings_from_every_file(tmp_path):
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("eval(source)\n", encoding="utf-8")
    second.write_text("exec(source)\n", encoding="utf-8")

    result = run_analysis(tmp_path, ProjectSpec())

    assert result["files_scanned"] == 2
    assert result["total_issues"] == 2
    assert result["summary"]["total_issues"] == 2
    assert result["summary"]["by_rule"] == {
        "security.eval_exec": 1,
        "security.exec": 1,
    }


def test_run_analysis_fails_closed_on_read_and_syntax_errors(tmp_path):
    invalid = tmp_path / "invalid.py"
    invalid.write_text("def broken(:\n", encoding="utf-8")

    result = run_analysis(tmp_path, ProjectSpec())

    assert result["gate_result"] == "fail"
    assert len(result["scan_errors"]) == 1
    assert "SyntaxError" in result["scan_errors"][0]["error"]


def test_run_analysis_honors_security_ignore_patterns(tmp_path):
    (tmp_path / "test_secret.py").write_text("password = 'secret'\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("password = 'secret'\n", encoding="utf-8")
    spec = ProjectSpec(security=SecuritySpec(ignore_patterns=["test_*.py"]))

    result = run_analysis(tmp_path, spec)

    assert result["files_scanned"] == 1
    assert result["total_issues"] == 1


def test_run_analysis_rejects_non_python_project_spec(tmp_path):
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="supports Python only"):
        run_analysis(tmp_path, ProjectSpec(language="typescript"))


def test_gate_command_enforces_minimum_score(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "\n".join("import random\nvalue_{} = random.random()".format(i) for i in range(8)),
        encoding="utf-8",
    )

    status = main(["gate", str(source), "--min-score", "70"])

    assert status == 2


def test_cli_writes_valid_sarif_and_returns_failure_status(tmp_path):
    (tmp_path / "app.py").write_text("eval(source)\n", encoding="utf-8")
    output = tmp_path / "report.sarif"

    status = main([str(tmp_path), "--sarif", "--output", str(output)])

    assert status == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["version"] == "2.1.0"
    assert report["runs"][0]["results"][0]["ruleId"] == "security.eval_exec"


def test_sarif_single_file_scan_uses_the_file_as_artifact_uri(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("eval(source)\n", encoding="utf-8")
    result = run_analysis(source, ProjectSpec())

    sarif = generate_sarif(result, source)
    artifact_uri = sarif["runs"][0]["results"][0]["locations"][0][
        "physicalLocation"
    ]["artifactLocation"]["uri"]

    assert artifact_uri == source.resolve().as_uri()


def test_cli_writes_agent_rules(tmp_path):
    (tmp_path / "app.py").write_text("eval(source)\n", encoding="utf-8")
    output = tmp_path / "agent-rules.yaml"

    status = main([str(tmp_path), "--agent-rules", "--output", str(output)])

    assert status == 2
    assert "security.eval_exec" in output.read_text(encoding="utf-8")


def test_cli_creates_output_parent_directories(tmp_path, capsys):
    source = tmp_path / "app.py"
    source.write_text("value = 1\n", encoding="utf-8")
    output = tmp_path / "missing" / "result.json"

    status = main([str(source), "--output", str(output)])

    assert status == 0
    assert output.is_file()
    assert "错误" not in capsys.readouterr().err
