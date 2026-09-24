import pytest

from engines.enhanced_analyzer import EnhancedAnalyzer, Severity
from engines.spec_parser import CodeQualitySpec, ProjectSpec


def make_analyzer(**quality_options):
    spec = ProjectSpec(code_quality=CodeQualitySpec(**quality_options))
    return EnhancedAnalyzer(spec)


def test_function_length_counts_physical_source_lines():
    code = "\n".join(
        ["def one_statement():", "    values = ["]
        + [f"        {number}," for number in range(12)]
        + ["    ]", "    return values"]
    )

    issues = make_analyzer(max_function_length=10).analyze(code)

    issue = next(i for i in issues if i.rule_id == "code_quality.function_too_long")
    assert "16 行" in issue.message


def test_parameter_count_includes_positional_only_and_keyword_only_parameters():
    code = "def f(a, /, b, *args, c, **kwargs):\n    return a\n"

    issues = make_analyzer(max_parameters=3).analyze(code)

    assert any(i.rule_id == "code_quality.too_many_parameters" for i in issues)


def test_comments_and_string_literals_do_not_trigger_code_rules():
    code = """
# eval(user_input) TODO: this is documentation
message = "exec(untrusted) password = 'secret' verify=False"
"""

    issues = EnhancedAnalyzer().analyze(code)

    assert [issue.rule_id for issue in issues] == ["ai_slop.redundant_todo"]


def test_python_ast_rules_are_reported_once_with_source_location():
    code = "try:\n    work()\nexcept:\n    pass\n"

    issues = EnhancedAnalyzer().analyze(code)
    rule_ids = [issue.rule_id for issue in issues]

    assert rule_ids.count("ai_slop.bare_except") == 1
    assert rule_ids.count("ai_slop.swallow_exception") == 1
    assert next(i for i in issues if i.rule_id == "ai_slop.bare_except").line == 3


def test_todo_in_comment_is_reported_but_todo_in_string_is_not():
    code = '# TODO: remove this\nmessage = "TODO: not a task"\n'

    issues = EnhancedAnalyzer().analyze(code)

    todos = [i for i in issues if i.rule_id == "ai_slop.redundant_todo"]
    assert len(todos) == 1
    assert todos[0].line == 1


def test_hardcoded_secret_context_is_redacted():
    issues = EnhancedAnalyzer().analyze('config["password"] = "do-not-leak-this"\n')

    issue = next(i for i in issues if i.rule_id == "security.hardcoded_secret")
    assert "do-not-leak-this" not in issue.context
    assert "<redacted>" in issue.context


def test_ast_column_is_reported_as_unicode_character_column():
    issues = EnhancedAnalyzer().analyze('前缀 = 1; result = eval(source)\n')

    issue = next(i for i in issues if i.rule_id == "security.eval_exec")
    assert issue.column == 17


def test_invalid_python_is_not_silently_treated_as_clean():
    with pytest.raises(SyntaxError):
        EnhancedAnalyzer().analyze("def broken(:\n    pass\n")


@pytest.mark.parametrize(
    ("code", "rule_id"),
    [
        ("import yaml\ndata = yaml.load(stream)\n", "security.unsafe_deserialization"),
        ("import yaml\ndata = yaml.unsafe_load(stream)\n", "security.unsafe_deserialization"),
        ("import pickle\nvalue = pickle.loads(payload)\n", "security.unsafe_deserialization"),
        ("import os\nos.system(command)\n", "security.command_injection"),
        ("import os.path\nos.system(command)\n", "security.command_injection"),
        ("import subprocess\nsubprocess.run(command, shell=True)\n", "security.command_injection"),
        ("import requests\nrequests.get(url, verify=False)\n", "security.ssl_disabled"),
        (
            'cursor.execute("SELECT * FROM users WHERE id = {}".format(user_id))\n',
            "security.sql_injection",
        ),
        (
            'cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)\n',
            "security.sql_injection",
        ),
        ("value = eval(source)\n", "security.eval_exec"),
    ],
)
def test_ast_security_rules_detect_supported_python_calls(code, rule_id):
    issues = EnhancedAnalyzer().analyze(code)

    assert any(issue.rule_id == rule_id for issue in issues)


def test_security_severity_threshold_filters_lower_severity_findings():
    spec = ProjectSpec()
    spec.security.max_severity = "critical"
    code = "import random\nvalue = random.random()\nresult = eval(source)\n"

    issues = EnhancedAnalyzer(spec).analyze(code)

    assert any(i.rule_id == "security.eval_exec" and i.severity == Severity.CRITICAL for i in issues)
    assert not any(i.rule_id == "security.insecure_random" for i in issues)


def test_parameterized_sql_query_is_not_reported_as_dynamic_sql():
    code = 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))\n'

    issues = EnhancedAnalyzer().analyze(code)

    assert not any(issue.rule_id == "security.sql_injection" for issue in issues)
