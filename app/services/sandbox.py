"""Runs learner code in a separate process with limits.

The isolation here is "do not take the server down" grade: a separate process,
limits on CPU, memory and file size, a timeout and an empty working directory.
That is enough for teaching tasks, but NOT enough for a public service running
untrusted code: real protection is a container without network access.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass, field

from app.config import settings

# Imports that teaching tasks never need and that usually mean an attempt to escape
FORBIDDEN_MODULES = (
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "requests",
    "urllib",
    "http",
    "ctypes",
    "multiprocessing",
    "importlib",
    "builtins",
)
FORBIDDEN_CALLS = ("eval(", "exec(", "compile(", "__import__", "open(", "input(")

# Marker that separates the learner's own output from the harness result
RESULT_MARKER = "---CODEHOG-JSON---"


@dataclass
class CheckResult:
    """Outcome of one check: what was called, what was expected, what came back."""

    call: str
    expected: object
    got: object = None
    passed: bool = False
    error: str = ""


@dataclass
class RunResult:
    """Outcome of a whole run."""

    passed: bool = False
    stdout: str = ""
    error: str = ""
    duration_ms: int = 0
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """One line for logs: the last error line, or how many checks passed."""
        error_lines = self.error.strip().splitlines()
        if error_lines:
            return error_lines[-1][:200]
        passed_count = sum(1 for check in self.checks if check.passed)
        return f"passed {passed_count} of {len(self.checks)}"


class CodeInspector:
    """Static pre-check before running the code."""

    @staticmethod
    def find_forbidden(code: str) -> str | None:
        """A message for the learner if the code uses something forbidden, otherwise None."""
        for line in (raw.strip() for raw in code.splitlines()):
            if line.startswith(("import ", "from ")):
                module = line.split()[1].split(".")[0]
                if module in FORBIDDEN_MODULES:
                    return f"Модуль {module} в задачах недоступен"
        for call in FORBIDDEN_CALLS:
            if call in code:
                return f"Конструкция {call.rstrip('(')} здесь запрещена"
        return None


# Runs inside the child process. STUDENT_CODE, CHECKS, OUTPUT_LIMIT and
# NAMESPACE are defined right before it.
HARNESS = f'''
import json, io, contextlib

result = {{"checks": [], "stdout": "", "error": ""}}
buffer = io.StringIO()
try:
    with contextlib.redirect_stdout(buffer):
        exec(compile(STUDENT_CODE, "solution.py", "exec"), NAMESPACE)
except Exception as e:
    result["error"] = f"{{type(e).__name__}}: {{e}}"

if not result["error"]:
    for check in CHECKS:
        entry = {{"call": check["call"], "expected": check.get("expect"),
                 "got": None, "passed": False, "error": ""}}
        try:
            with contextlib.redirect_stdout(buffer):
                got = eval(check["call"], NAMESPACE)
            entry["got"] = got
            entry["passed"] = got == check.get("expect")
        except Exception as e:
            entry["error"] = f"{{type(e).__name__}}: {{e}}"
        result["checks"].append(entry)

result["stdout"] = buffer.getvalue()[:OUTPUT_LIMIT]
print("{RESULT_MARKER}")
print(json.dumps(result, ensure_ascii=False, default=repr))
'''


class Sandbox:
    """Executes learner code and compares the results with the expected ones."""

    def __init__(self, timeout: float | None = None, memory_mb: int | None = None) -> None:
        self.timeout = timeout or settings.code_timeout_sec
        self.memory_mb = memory_mb or settings.code_memory_mb

    def _limits(self):
        """A function that the child process calls before exec. Not available on Windows."""
        try:
            import resource
        except ImportError:  # pragma: no cover
            return None

        memory = self.memory_mb * 1024 * 1024
        cpu = max(1, int(self.timeout))

        def apply() -> None:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
            try:
                resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
            except (ValueError, OSError):
                pass  # macOS does not always apply RLIMIT_AS
            os.setsid()

        return apply

    def run(self, code: str, checks: list[dict] | None = None) -> RunResult:
        checks = checks or []
        violation = CodeInspector.find_forbidden(code)
        if violation:
            return RunResult(passed=False, error=violation)

        program = (
            f"STUDENT_CODE = {code!r}\n"
            # Checks are passed as a JSON string and parsed inside. JSON pasted
            # as is would not be Python: true/false/null in expected values
            # used to crash the run with a NameError.
            f"CHECKS = __import__('json').loads({json.dumps(checks, ensure_ascii=False)!r})\n"
            f"OUTPUT_LIMIT = {settings.code_output_limit}\n"
            f"NAMESPACE = {{'__name__': '__main__'}}\n" + textwrap.dedent(HARNESS)
        )

        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="codehog-") as workdir:
            script_path = os.path.join(workdir, "runner.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(program)
            env = {
                "PATH": "/usr/bin:/bin",
                "PYTHONDONTWRITEBYTECODE": "1",
                "HOME": workdir,
                "PYTHONIOENCODING": "utf-8",
            }
            try:
                process = subprocess.run(
                    [sys.executable, "-I", "-S", script_path],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=workdir,
                    env=env,
                    preexec_fn=self._limits(),
                )
            except subprocess.TimeoutExpired:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                return RunResult(
                    passed=False,
                    duration_ms=elapsed_ms,
                    error=(
                        f"Код выполнялся дольше {self.timeout:.0f} с — похоже на бесконечный цикл"
                    ),
                )
            except Exception as e:  # pragma: no cover
                return RunResult(passed=False, error=f"Не удалось запустить: {e}")

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return self._parse(process, elapsed_ms)

    @staticmethod
    def _parse(process: subprocess.CompletedProcess, elapsed_ms: int) -> RunResult:
        if RESULT_MARKER not in process.stdout:
            error = (process.stderr or "Программа завершилась неожиданно").strip()
            if "MemoryError" in error:
                error = "Не хватило памяти — программа запросила слишком много"
            return RunResult(passed=False, error=error[:1000], duration_ms=elapsed_ms)

        raw = process.stdout.split(RESULT_MARKER, 1)[1].strip()
        try:
            data = json.loads(raw)
        except ValueError:
            return RunResult(
                passed=False, error="Не удалось разобрать результат", duration_ms=elapsed_ms
            )

        checks = [
            CheckResult(
                call=check["call"],
                expected=check.get("expected"),
                got=check.get("got"),
                passed=bool(check.get("passed")),
                error=check.get("error", ""),
            )
            for check in data.get("checks", [])
        ]
        success = bool(checks) and all(check.passed for check in checks) and not data.get("error")
        if not checks and not data.get("error"):
            success = True  # a task without checks only needs the code to run
        return RunResult(
            passed=success,
            stdout=data.get("stdout", ""),
            error=data.get("error", ""),
            duration_ms=elapsed_ms,
            checks=checks,
        )
