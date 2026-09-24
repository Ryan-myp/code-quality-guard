"""AST-based analyzer for Python source code."""

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .rule_registry import load_rule_registry
from .spec_parser import ProjectSpec


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    INFO = "info"


SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "warning": 2,
    "info": 1,
}


@dataclass
class Issue:
    """A finding with source location and remediation guidance."""

    rule_id: str
    severity: Severity
    line: int
    column: int
    message: str
    fix: Optional[str] = None
    confidence: float = 1.0
    context: str = ""


class EnhancedAnalyzer:
    """Analyze Python syntax and source comments without scanning literal text."""

    SENSITIVE_NAME = re.compile(
        r"(?:password|passwd|passphrase|secret|api[_-]?key|access[_-]?token|"
        r"auth[_-]?token|private[_-]?key|client[_-]?secret)",
        re.IGNORECASE,
    )
    RANDOM_CALLS = {
        "random.random",
        "random.randint",
        "random.randrange",
        "random.choice",
        "random.choices",
        "random.getrandbits",
    }
    SHELL_FUNCTIONS = {
        "subprocess.call",
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.check_call",
        "subprocess.check_output",
    }

    def __init__(self, spec: Optional[ProjectSpec] = None):
        self.spec = spec or ProjectSpec()
        validation_errors = self.spec.validate()
        if validation_errors:
            raise ValueError("Invalid project spec: {}".format("; ".join(validation_errors)))
        self.rule_registry = load_rule_registry()
        self.issues: List[Issue] = []
        self._seen: Set[Tuple[str, int, int]] = set()
        self._lines: List[str] = []
        self._module_aliases: Dict[str, str] = {}
        self._imported_names: Dict[str, str] = {}
        self._parents: Dict[int, ast.AST] = {}

    def analyze(self, code: str, file_path: Optional[Path] = None) -> List[Issue]:
        """Analyze valid Python source and return findings in source order."""
        del file_path  # Reserved for future path-sensitive rules.
        self.issues = []
        self._seen = set()
        self._lines = code.splitlines()
        tree = ast.parse(code)
        self._build_import_maps(tree)
        self._parents = {
            id(child): parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_function(node)
            elif isinstance(node, ast.ClassDef):
                self._check_docstring(node)
            elif isinstance(node, ast.ExceptHandler):
                self._check_exception_handler(node)
            elif isinstance(node, ast.Call):
                self._check_call(node)
            elif isinstance(node, (ast.JoinedStr, ast.BinOp)):
                if self._is_dynamic_sql(node):
                    self._add_security_issue("security.sql_injection", node)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                self._check_secret_assignment(node)
            elif isinstance(node, ast.Attribute):
                self._check_ssl_assignment(node)

        self._check_source_lines()
        self._check_comments(code)
        self.issues.sort(key=lambda issue: (issue.line, issue.column, issue.rule_id))
        return list(self.issues)

    def _build_import_maps(self, tree: ast.Module) -> None:
        self._module_aliases = {}
        self._imported_names = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name.split(".")[0]
                    self._module_aliases[local_name] = (
                        alias.name if alias.asname else local_name
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    self._imported_names[local_name] = "{}.{}".format(module, alias.name)

    def _resolved_name(self, node: Optional[ast.AST]) -> str:
        attributes = []
        current = node
        while isinstance(current, ast.Attribute):
            attributes.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            return ""
        base = self._imported_names.get(
            current.id, self._module_aliases.get(current.id, current.id)
        )
        return ".".join([base] + list(reversed(attributes)))

    def _add_issue(
        self,
        rule_id: str,
        severity: Severity,
        node: ast.AST,
        message: str,
        fix: Optional[str],
        confidence: float,
        security: bool = False,
    ) -> None:
        if security:
            configured = SEVERITY_RANK[self.spec.security.max_severity]
            if SEVERITY_RANK[severity.value] < configured:
                return
        line = max(1, getattr(node, "lineno", 1))
        raw_column = max(0, getattr(node, "col_offset", 0))
        column = raw_column
        if rule_id != "ai_slop.redundant_todo" and line <= len(self._lines):
            encoded_prefix = self._lines[line - 1].encode("utf-8")[:raw_column]
            column = len(encoded_prefix.decode("utf-8", errors="ignore"))
        key = (rule_id, line, column)
        if key in self._seen:
            return
        self._seen.add(key)
        line_text = self._lines[line - 1] if line <= len(self._lines) else ""
        if self.SENSITIVE_NAME.search(line_text):
            line_text = re.sub(
                r"""(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")""",
                '"<redacted>"',
                line_text,
            )
        self.issues.append(
            Issue(
                rule_id=rule_id,
                severity=severity,
                line=line,
                column=column,
                message=message,
                fix=fix,
                confidence=confidence,
                context=line_text.strip()[:120],
            )
        )

    def _add_security_issue(self, rule_id: str, node: ast.AST) -> None:
        self._add_rule(rule_id, node, security=True)

    def _add_rule(
        self,
        rule_id: str,
        node: ast.AST,
        message: Optional[str] = None,
        security: bool = False,
    ) -> None:
        metadata = self.rule_registry.get(rule_id)
        if metadata is None:
            raise ValueError("Rule is missing from the catalog: {}".format(rule_id))
        self._add_issue(
            rule_id,
            Severity(metadata["severity"]),
            node,
            message or metadata["description"],
            metadata.get("fix"),
            float(metadata["confidence"]),
            security=security,
        )

    def _check_function(self, node: ast.FunctionDef) -> None:
        start_line = node.lineno
        if node.decorator_list:
            start_line = min(start_line, *(decorator.lineno for decorator in node.decorator_list))
        end_line = getattr(node, "end_lineno", node.lineno)
        function_length = end_line - start_line + 1
        if function_length > self.spec.code_quality.max_function_length:
            self._add_rule(
                "code_quality.function_too_long",
                node,
                "函数过长 ({} 行，限制 {} 行)".format(
                    function_length, self.spec.code_quality.max_function_length
                ),
            )

        parameter_count = self._parameter_count(node)
        if parameter_count > self.spec.code_quality.max_parameters:
            self._add_rule(
                "code_quality.too_many_parameters",
                node,
                "参数过多 ({} 个，限制 {} 个)".format(
                    parameter_count, self.spec.code_quality.max_parameters
                ),
            )

        nesting_depth = self._calculate_nesting_depth(node)
        if nesting_depth > self.spec.code_quality.max_nesting_depth:
            self._add_rule(
                "code_quality.deep_nesting",
                node,
                "嵌套过深 (深度 {}，限制 {})".format(
                    nesting_depth, self.spec.code_quality.max_nesting_depth
                ),
            )
        self._check_docstring(node)

    def _parameter_count(self, node: ast.FunctionDef) -> int:
        args = node.args
        parameters = (
            list(args.posonlyargs)
            + list(args.args)
            + list(args.kwonlyargs)
            + ([args.vararg] if args.vararg else [])
            + ([args.kwarg] if args.kwarg else [])
        )
        parent = self._parents.get(id(node))
        if (
            isinstance(parent, ast.ClassDef)
            and parameters
            and parameters[0].arg in ("self", "cls")
        ):
            parameters = parameters[1:]
        return len(parameters)

    def _check_docstring(self, node: ast.AST) -> None:
        if not self.spec.code_quality.require_docstrings:
            return
        name = getattr(node, "name", "")
        if name.startswith("_") or ast.get_docstring(node):
            return
        self._add_rule(
            "code_quality.missing_docstring",
            node,
            "公开定义缺少文档字符串",
        )

    def _check_exception_handler(self, node: ast.ExceptHandler) -> None:
        rules = []
        if node.type is None:
            rules.append("ai_slop.bare_except")
        elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
            rules.append("ai_slop.generic_exception")
        elif (
            isinstance(node.type, ast.Tuple)
            and any(
                isinstance(item, ast.Name) and item.id == "Exception"
                for item in node.type.elts
            )
        ):
            rules.append("ai_slop.generic_exception")
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            rules.append("ai_slop.swallow_exception")
        for rule_id in rules:
            self._add_rule(rule_id, node)

    def _check_call(self, node: ast.Call) -> None:
        name = self._resolved_name(node.func)
        short_name = name.rsplit(".", 1)[-1]

        if name in ("eval", "builtins.eval"):
            self._add_security_issue("security.eval_exec", node)
        elif name in ("exec", "builtins.exec"):
            self._add_security_issue("security.exec", node)

        if name in self.RANDOM_CALLS:
            self._add_security_issue("security.insecure_random", node)

        if name == "os.system" or name == "os.popen":
            self._add_security_issue("security.command_injection", node)
        elif name in self.SHELL_FUNCTIONS and any(
            keyword.arg == "shell" and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        ):
            self._add_security_issue("security.command_injection", node)

        if name.endswith((".loads", ".load")) or short_name in (
            "unsafe_load",
            "unsafe_load_all",
        ):
            self._check_deserialization(node, name, short_name)

        for keyword in node.keywords:
            if keyword.arg == "verify" and isinstance(keyword.value, ast.Constant):
                if keyword.value.value is False:
                    self._add_security_issue("security.ssl_disabled", node)
            if keyword.arg and self.SENSITIVE_NAME.search(keyword.arg):
                if self._nonempty_string(keyword.value):
                    self._add_security_issue("security.hardcoded_secret", keyword.value)

        if short_name in ("execute", "executemany", "query") and node.args:
            if self._is_dynamic_sql(node.args[0]):
                self._add_security_issue("security.sql_injection", node.args[0])

        if short_name == "open" and node.args and self._has_parent_path(node.args[0]):
            self._add_security_issue("security.path_traversal", node)

    def _check_deserialization(self, node: ast.Call, name: str, short_name: str) -> None:
        module_name = name.rsplit(".", 1)[0]
        if module_name in ("pickle", "marshal") and short_name in ("load", "loads"):
            self._add_security_issue("security.unsafe_deserialization", node)
            return
        if module_name in ("yaml", "ruamel.yaml") and short_name in (
            "unsafe_load",
            "unsafe_load_all",
        ):
            self._add_security_issue("security.unsafe_deserialization", node)
            return
        if name in ("yaml.load", "ruamel.yaml.load") or (
            short_name == "load" and name.rsplit(".", 1)[0] in ("yaml", "ruamel.yaml")
        ):
            loader = next((kw.value for kw in node.keywords if kw.arg == "Loader"), None)
            loader_name = self._resolved_name(loader) if loader is not None else ""
            if not loader_name.endswith(("SafeLoader", "CSafeLoader")):
                self._add_security_issue("security.unsafe_deserialization", node)

    def _check_secret_assignment(self, node: ast.AST) -> None:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
            targets, value = [node.target], node.value
        else:
            return
        if not self._nonempty_string(value):
            return
        for target in targets:
            for name_node in self._target_names(target):
                if self.SENSITIVE_NAME.search(name_node):
                    self._add_security_issue("security.hardcoded_secret", node)
                    return

    def _target_names(self, target: ast.AST) -> List[str]:
        names = []
        pending = [target]
        while pending:
            current = pending.pop()
            if isinstance(current, ast.Name):
                names.append(current.id)
            elif isinstance(current, ast.Attribute):
                names.append(current.attr)
            elif isinstance(current, (ast.Tuple, ast.List)):
                pending.extend(current.elts)
            elif isinstance(current, ast.Subscript):
                key = current.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    names.append(key.value)
        return names

    @staticmethod
    def _nonempty_string(node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return isinstance(node.value, str) and bool(node.value.strip())
        return False

    def _check_ssl_assignment(self, node: ast.Attribute) -> None:
        parent = self._parents.get(id(node))
        if not (
            isinstance(parent, ast.Assign)
            and any(target is node for target in parent.targets)
            and node.attr == "verify"
            and isinstance(parent.value, ast.Constant)
            and parent.value.value is False
        ):
            return
        self._add_security_issue("security.ssl_disabled", parent)

    def _is_dynamic_sql(self, node: ast.AST) -> bool:
        if isinstance(node, ast.JoinedStr):
            prefix = []
            for value in node.values:
                if isinstance(value, ast.FormattedValue):
                    return self._looks_like_sql("".join(prefix))
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    prefix.append(value.value)
            return False
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("format", "format_map")
            and (node.args or node.keywords)
        ):
            template = self._leading_string(node.func.value)
            return self._looks_like_sql(template)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            template = self._leading_string(node.left)
            return self._looks_like_sql(template) and self._contains_dynamic(node.right)
        return False

    def _leading_string(self, node: ast.AST) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self._leading_string(node.left)
        return ""

    def _string_constants(self, node: ast.AST) -> List[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        return [
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        ]

    def _contains_dynamic(self, node: ast.AST) -> bool:
        return any(
            isinstance(child, (ast.Name, ast.Call, ast.FormattedValue))
            for child in ast.walk(node)
        )

    @staticmethod
    def _looks_like_sql(value: str) -> bool:
        return bool(re.match(r"\s*(SELECT|INSERT|UPDATE|DELETE|REPLACE)\b", value, re.IGNORECASE))

    def _has_parent_path(self, node: ast.AST) -> bool:
        return any(
            part == ".."
            for value in self._string_constants(node)
            for part in re.split(r"[/\\]+", value)
        )

    def _check_source_lines(self) -> None:
        limit = self.spec.code_quality.max_line_length
        for line_number, line in enumerate(self._lines, 1):
            if len(line) > limit:
                synthetic_node = ast.Constant(value=None)
                synthetic_node.lineno = line_number
                synthetic_node.col_offset = 0
                self._add_rule(
                    "code_quality.line_too_long",
                    synthetic_node,
                    "行过长 ({} 字符，限制 {})".format(len(line), limit),
                )

    def _check_comments(self, code: str) -> None:
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type == tokenize.COMMENT and re.search(r"\b(TODO|FIXME)\b", token.string):
                line = token.start[0]
                column = token.start[1]
                key = ("ai_slop.redundant_todo", line, column)
                if key in self._seen:
                    continue
                synthetic_node = ast.Constant(value=None)
                synthetic_node.lineno = line
                synthetic_node.col_offset = column
                self._add_rule("ai_slop.redundant_todo", synthetic_node)

    def _calculate_nesting_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        control_types = (
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.With,
            ast.AsyncWith,
            ast.Try,
        )
        match_type = getattr(ast, "Match", None)
        if match_type is not None:
            control_types += (match_type,)
        max_depth = current_depth
        pending = [(statement, current_depth, False) for statement in node.body]
        while pending:
            child, parent_depth, is_elif = pending.pop()
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.If):
                child_depth = parent_depth if is_elif else parent_depth + 1
                max_depth = max(max_depth, child_depth)
                pending.extend((statement, child_depth, False) for statement in child.body)
                pending.extend(
                    (
                        statement,
                        child_depth,
                        isinstance(statement, ast.If)
                        and statement.col_offset == child.col_offset,
                    )
                    for statement in child.orelse
                )
                continue
            child_depth = parent_depth + 1 if isinstance(child, control_types) else parent_depth
            max_depth = max(max_depth, child_depth)
            pending.extend(
                (grandchild, child_depth, False)
                for grandchild in ast.iter_child_nodes(child)
            )
        return max_depth

    def get_summary(self, issues: Optional[List[Issue]] = None) -> Dict[str, Any]:
        """Return counts for the current findings or an explicitly supplied set."""
        selected = self.issues if issues is None else issues
        summary = {
            "total_issues": len(selected),
            "by_severity": {
                severity.value: sum(1 for issue in selected if issue.severity == severity)
                for severity in Severity
            },
            "by_rule": {},
        }
        for issue in selected:
            summary["by_rule"][issue.rule_id] = summary["by_rule"].get(issue.rule_id, 0) + 1
        return summary
