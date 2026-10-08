"""Run Go's formatter and vet analyzers and normalize their findings."""

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .enhanced_analyzer import Issue, Severity


@dataclass
class GoAnalysis:
    """Normalized results from the Go toolchain."""

    file_results: Dict[str, List[Issue]] = field(default_factory=dict)
    scan_errors: List[Dict[str, str]] = field(default_factory=list)


class GoAnalyzer:
    """Check a Go module with gofmt and `go vet -json ./...`."""

    TIMEOUT_SECONDS = 120

    def analyze(self, project_path: Path, files: List[Path]) -> GoAnalysis:
        root = Path(project_path)
        result = GoAnalysis()
        validation_error = self._validate_project(root, files)
        if validation_error:
            result.scan_errors.append({"path": str(root), "error": validation_error})
            return result

        go_executable, gofmt_executable, missing = self._find_tools()
        if missing:
            result.scan_errors.append(
                {
                    "path": str(root),
                    "error": "Required Go toolchain command(s) not found: {}.".format(
                        ", ".join(missing)
                    ),
                }
            )
            return result

        root = root.resolve()
        result.file_results = {self._file_key(path, root): [] for path in files}
        relative_files = [self._relative_file(path, root) for path in files]
        self._check_format(gofmt_executable, root, relative_files, result)
        self._check_vet(go_executable, root, result)
        return result

    @staticmethod
    def _validate_project(root: Path, files: List[Path]) -> Optional[str]:
        if not root.is_dir():
            return "Go scans require a module directory containing go.mod."
        if not (root / "go.mod").is_file():
            return "Go module root not found: go.mod is required."
        if not files:
            return "No Go source files found."
        return None

    @staticmethod
    def _find_tools():
        go_executable = shutil.which("go")
        gofmt_executable = shutil.which("gofmt")
        missing = [
            name
            for name, executable in (
                ("go", go_executable),
                ("gofmt", gofmt_executable),
            )
            if executable is None
        ]
        return go_executable, gofmt_executable, missing

    def _check_format(
        self,
        executable: str,
        root: Path,
        files: List[str],
        result: GoAnalysis,
    ) -> None:
        try:
            completed = subprocess.run(
                [executable, "-l"] + files,
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            result.scan_errors.append(
                {"path": "gofmt", "error": "{}: {}".format(type(error).__name__, error)}
            )
            return

        if completed.returncode != 0:
            result.scan_errors.append(
                {
                    "path": "gofmt",
                    "error": self._command_failure(completed, "gofmt"),
                }
            )
            return
        self._record_unformatted_files(completed.stdout, root, result)

    def _record_unformatted_files(
        self, output: str, root: Path, result: GoAnalysis
    ) -> None:
        for output_line in output.splitlines():
            file_key = self._output_file_key(output_line, root)
            if file_key is None:
                result.scan_errors.append(
                    {
                        "path": "gofmt",
                        "error": "gofmt returned an invalid file path: {}".format(
                            output_line[:300]
                        ),
                    }
                )
                continue
            result.file_results.setdefault(file_key, []).append(
                Issue(
                    rule_id="go.gofmt",
                    severity=Severity.WARNING,
                    line=1,
                    column=0,
                    message="Go source is not formatted with gofmt.",
                    fix="Run gofmt -w on this file.",
                    confidence=1.0,
                    context="gofmt",
                )
            )

    def _check_vet(self, executable: str, root: Path, result: GoAnalysis) -> None:
        try:
            completed = subprocess.run(
                [executable, "vet", "-json", "./..."],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            result.scan_errors.append(
                {"path": "go vet", "error": "{}: {}".format(type(error).__name__, error)}
            )
            return

        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        diagnostics, parse_errors = self._parse_vet_output(output, root)
        result.scan_errors.extend(parse_errors)
        for file_key, issue in diagnostics:
            result.file_results.setdefault(file_key, []).append(issue)

        if completed.returncode != 0 and not diagnostics and not parse_errors:
            result.scan_errors.append(
                {
                    "path": "go vet",
                    "error": self._command_failure(completed, "go vet"),
                }
            )

    def _parse_vet_output(
        self, output: str, root: Path
    ) -> Tuple[List[Tuple[str, Issue]], List[Dict[str, str]]]:
        diagnostics: List[Tuple[str, Issue]] = []
        documents, errors = self._decode_vet_documents(output)
        if errors:
            return diagnostics, errors
        for document in documents:
            found, document_errors = self._parse_vet_document(document, root)
            diagnostics.extend(found)
            errors.extend(document_errors)
        return diagnostics, errors

    def _decode_vet_documents(
        self, output: str
    ) -> Tuple[List[object], List[Dict[str, str]]]:
        if not output.strip():
            return [], []
        decoder = json.JSONDecoder()
        documents = []
        offset = 0
        while offset < len(output):
            start = output.find("{", offset)
            if start < 0:
                break
            try:
                document, end = decoder.raw_decode(output, start)
            except json.JSONDecodeError:
                offset = start + 1
                continue
            documents.append(document)
            offset = end
        if documents:
            return documents, []
        return [], [
            {
                "path": "go vet",
                "error": "go vet produced output without a valid JSON document: {}".format(
                    output.strip()[:500]
                ),
            }
        ]

    def _parse_vet_document(
        self, document: object, root: Path
    ) -> Tuple[List[Tuple[str, Issue]], List[Dict[str, str]]]:
        diagnostics: List[Tuple[str, Issue]] = []
        errors: List[Dict[str, str]] = []
        if not isinstance(document, dict):
            return diagnostics, [
                {"path": "go vet", "error": "Unexpected go vet JSON document."}
            ]
        for package, analyzers in document.items():
            found, package_errors = self._parse_package_result(
                str(package), analyzers, root
            )
            diagnostics.extend(found)
            errors.extend(package_errors)
        return diagnostics, errors

    def _parse_package_result(
        self, package: str, analyzers: object, root: Path
    ) -> Tuple[List[Tuple[str, Issue]], List[Dict[str, str]]]:
        diagnostics: List[Tuple[str, Issue]] = []
        errors: List[Dict[str, str]] = []
        if not isinstance(analyzers, dict):
            return diagnostics, [
                {"path": package, "error": "Unexpected go vet package result."}
            ]
        for analyzer, entries in analyzers.items():
            if not isinstance(entries, list):
                detail = self._error_detail(entries)
                errors.append(
                    {
                        "path": package,
                        "error": "go vet {}: {}".format(analyzer, detail),
                    }
                )
                continue
            for entry in entries:
                parsed = self._parse_diagnostic(package, str(analyzer), entry, root)
                if isinstance(parsed, dict):
                    errors.append(parsed)
                else:
                    diagnostics.append(parsed)
        return diagnostics, errors

    def _parse_diagnostic(
        self, package: str, analyzer: str, entry: object, root: Path
    ):
        if not isinstance(entry, dict):
            return {
                "path": package,
                "error": "go vet {} returned an invalid diagnostic.".format(analyzer),
            }
        position = entry.get("posn")
        message = entry.get("message")
        if not isinstance(position, str) or not isinstance(message, str):
            return {
                "path": package,
                "error": "go vet {} returned a diagnostic without a location or message.".format(
                    analyzer
                ),
            }
        parsed_position = self._parse_position(position)
        if parsed_position is None:
            return {
                "path": package,
                "error": "go vet returned an invalid position: {}".format(position[:300]),
            }

        raw_path, line, column = parsed_position
        file_key = self._output_file_key(raw_path, root)
        if file_key is None:
            return {
                "path": package,
                "error": "go vet returned an invalid file path: {}".format(raw_path[:300]),
            }
        category = entry.get("category")
        analyzer_name = category if isinstance(category, str) and category else analyzer
        return file_key, Issue(
            rule_id="go.vet",
            severity=Severity.WARNING,
            line=line,
            column=column,
            message="{}: {}".format(analyzer_name, message),
            fix="Fix the diagnostic and rerun go vet ./....",
            confidence=1.0,
            context=analyzer_name,
        )

    @staticmethod
    def _parse_position(position: str) -> Optional[Tuple[str, int, int]]:
        parts = position.rsplit(":", 2)
        if len(parts) != 3 or not parts[0]:
            return None
        try:
            line = int(parts[1])
            column = int(parts[2])
        except ValueError:
            return None
        if line < 1 or column < 1:
            return None
        return parts[0], line, column - 1

    @staticmethod
    def _output_file_key(output_path: str, root: Path) -> Optional[str]:
        value = output_path.strip()
        if not value:
            return None
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        try:
            return path.resolve().relative_to(root).as_posix()
        except ValueError:
            return None

    @staticmethod
    def _relative_file(path: Path, root: Path) -> str:
        return Path(path).resolve().relative_to(root).as_posix()

    @staticmethod
    def _file_key(path: Path, root: Path) -> str:
        return GoAnalyzer._relative_file(path, root)

    @staticmethod
    def _error_detail(value: object) -> str:
        if isinstance(value, dict):
            error = value.get("error")
            if isinstance(error, str):
                return error[:1000]
        if isinstance(value, str):
            return value[:1000]
        return "unexpected analyzer output"

    @staticmethod
    def _command_failure(completed: subprocess.CompletedProcess, command: str) -> str:
        detail = (completed.stderr or completed.stdout).strip()
        if not detail:
            detail = "command exited with status {}".format(completed.returncode)
        return "{} failed: {}".format(command, detail[:1000])
