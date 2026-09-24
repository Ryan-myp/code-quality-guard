import pytest

from engines.spec_parser import SpecParser


def test_load_uses_configured_quality_and_security_values(tmp_path):
    path = tmp_path / "spec.yaml"
    path.write_text(
        """
name: sample
language: python
security:
  max_severity: high
  ignore_patterns:
    - "test_*.py"
code_quality:
  max_function_length: 30
  max_nesting_depth: 3
  max_parameters: 4
  max_line_length: 88
  require_docstrings: false
quality_gate:
  min_confidence: 0.9
""",
        encoding="utf-8",
    )

    spec = SpecParser().load(path)

    assert spec.code_quality.max_function_length == 30
    assert spec.code_quality.max_nesting_depth == 3
    assert spec.code_quality.max_parameters == 4
    assert spec.code_quality.max_line_length == 88
    assert spec.code_quality.require_docstrings is False
    assert spec.security.max_severity == "high"
    assert spec.security.ignore_patterns == ["test_*.py"]
    assert spec.quality_gate.min_confidence == 0.9


def test_missing_explicit_config_does_not_fall_back_to_defaults(tmp_path):
    with pytest.raises(FileNotFoundError):
        SpecParser().load(tmp_path / "missing.yaml")


@pytest.mark.parametrize(
    "source",
    [
        "- not-a-mapping",
        "code_quality: {max_function_length: 0}",
        "security: {max_severity: impossible}",
        "code_quality: {max_nesting_depth: 0}",
        "feedback: {enable_learning: true}",
        "security: {allowed_eval_contexts: ['ast.literal_eval']}",
    ],
)
def test_invalid_spec_is_rejected(tmp_path, source):
    path = tmp_path / "invalid.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError):
        SpecParser().load(path)


def test_non_string_mapping_key_is_reported_as_invalid_spec(tmp_path):
    path = tmp_path / "invalid.yaml"
    path.write_text("1: unsupported\n", encoding="utf-8")

    with pytest.raises(ValueError, match="keys must be strings"):
        SpecParser().load(path)
