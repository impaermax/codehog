"""Запуск кода ученика в отдельном процессе с ограничениями.

Изоляция здесь — уровня «не уронить сервер»: отдельный процесс, лимиты CPU,
памяти, числа процессов и размера файлов, таймаут и пустой рабочий каталог.
Этого достаточно для учебных задач, но НЕ достаточно для публичного сервиса
с недоверенным кодом: полноценная защита — контейнер без сети (см. Dockerfile).
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

# Импорты, которые в учебных задачах не нужны и чаще всего означают попытку выйти наружу
ЗАПРЕЩЁННЫЕ = (
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "requests",
    "urllib", "http", "ctypes", "multiprocessing", "importlib", "builtins",
)
ЗАПРЕЩЁННЫЕ_ВЫЗОВЫ = ("eval(", "exec(", "compile(", "__import__", "open(", "input(")


@dataclass
class РезультатПроверки:
    """Итог одной проверки: что вызывали, что ждали, что получили."""

    call: str
    expected: object
    got: object = None
    passed: bool = False
    error: str = ""


@dataclass
class РезультатЗапуска:
    """Итог всего запуска кода."""

    passed: bool = False
    stdout: str = ""
    error: str = ""
    duration_ms: int = 0
    checks: list[РезультатПроверки] = field(default_factory=list)

    @property
    def сводка(self) -> str:
        если_ошибка = self.error.strip().splitlines()
        if если_ошибка:
            return если_ошибка[-1][:200]
        сдал = sum(1 for п in self.checks if п.passed)
        return f"пройдено {сдал} из {len(self.checks)}"


class ПроверкаКода:
    """Статический предварительный контроль до запуска."""

    @staticmethod
    def найти_запрещённое(код: str) -> str | None:
        строки = [с.strip() for с in код.splitlines()]
        for строка in строки:
            if строка.startswith(("import ", "from ")):
                модуль = строка.split()[1].split(".")[0]
                if модуль in ЗАПРЕЩЁННЫЕ:
                    return f"Модуль {модуль} в задачах недоступен"
        for вызов in ЗАПРЕЩЁННЫЕ_ВЫЗОВЫ:
            if вызов in код:
                return f"Конструкция {вызов.rstrip('(')} здесь запрещена"
        return None


ОБВЯЗКА = '''
import json, sys, io, contextlib

РЕЗУЛЬТАТ = {"checks": [], "stdout": "", "error": ""}
буфер = io.StringIO()
try:
    with contextlib.redirect_stdout(буфер):
        exec(compile(КОД_УЧЕНИКА, "solution.py", "exec"), ПРОСТРАНСТВО)
except Exception as e:
    РЕЗУЛЬТАТ["error"] = f"{type(e).__name__}: {e}"

if not РЕЗУЛЬТАТ["error"]:
    for проверка in ПРОВЕРКИ:
        запись = {"call": проверка["call"], "expected": проверка.get("expect"),
                  "got": None, "passed": False, "error": ""}
        try:
            with contextlib.redirect_stdout(буфер):
                получено = eval(проверка["call"], ПРОСТРАНСТВО)
            запись["got"] = получено
            запись["passed"] = получено == проверка.get("expect")
        except Exception as e:
            запись["error"] = f"{type(e).__name__}: {e}"
        РЕЗУЛЬТАТ["checks"].append(запись)

РЕЗУЛЬТАТ["stdout"] = буфер.getvalue()[:ЛИМИТ_ВЫВОДА]
print("---CODEHOG-JSON---")
print(json.dumps(РЕЗУЛЬТАТ, ensure_ascii=False, default=repr))
'''


class Песочница:
    """Исполняет код ученика и сверяет результаты с ожидаемыми."""

    def __init__(self, таймаут: float | None = None, память_мб: int | None = None) -> None:
        self.таймаут = таймаут or settings.code_timeout_sec
        self.память_мб = память_мб or settings.code_memory_mb

    def _ограничения(self):
        """Вызывается в дочернем процессе до exec. На Windows не поддерживается."""
        try:
            import resource
        except ImportError:  # pragma: no cover
            return None

        память = self.память_мб * 1024 * 1024
        cpu = max(1, int(self.таймаут))

        def применить() -> None:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
            try:
                resource.setrlimit(resource.RLIMIT_AS, (память, память))
            except (ValueError, OSError):
                pass  # на macOS RLIMIT_AS применяется не всегда
            os.setsid()

        return применить

    def запустить(self, код: str, проверки: list[dict] | None = None) -> РезультатЗапуска:
        проверки = проверки or []
        помеха = ПроверкаКода.найти_запрещённое(код)
        if помеха:
            return РезультатЗапуска(passed=False, error=помеха)

        программа = (
            f"КОД_УЧЕНИКА = {код!r}\n"
            f"ПРОВЕРКИ = {json.dumps(проверки, ensure_ascii=False)}\n"
            f"ЛИМИТ_ВЫВОДА = {settings.code_output_limit}\n"
            f"ПРОСТРАНСТВО = {{'__name__': '__main__'}}\n"
            + textwrap.dedent(ОБВЯЗКА)
        )

        начало = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="codehog-") as рабочая:
            файл = os.path.join(рабочая, "runner.py")
            with open(файл, "w", encoding="utf-8") as f:
                f.write(программа)
            окружение = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                         "HOME": рабочая, "PYTHONIOENCODING": "utf-8"}
            try:
                процесс = subprocess.run(
                    [sys.executable, "-I", "-S", файл],
                    capture_output=True, text=True, timeout=self.таймаут,
                    cwd=рабочая, env=окружение, preexec_fn=self._ограничения(),
                )
            except subprocess.TimeoutExpired:
                прошло = int((time.monotonic() - начало) * 1000)
                return РезультатЗапуска(
                    passed=False, duration_ms=прошло,
                    error=f"Код выполнялся дольше {self.таймаут:.0f} с — похоже на бесконечный цикл",
                )
            except Exception as e:  # pragma: no cover
                return РезультатЗапуска(passed=False, error=f"Не удалось запустить: {e}")

        прошло = int((time.monotonic() - начало) * 1000)
        return self._разобрать(процесс, прошло)

    @staticmethod
    def _разобрать(процесс: subprocess.CompletedProcess, прошло: int) -> РезультатЗапуска:
        маркер = "---CODEHOG-JSON---"
        if маркер not in процесс.stdout:
            ошибка = (процесс.stderr or "Программа завершилась неожиданно").strip()
            if "MemoryError" in ошибка:
                ошибка = "Не хватило памяти — программа запросила слишком много"
            return РезультатЗапуска(passed=False, error=ошибка[:1000], duration_ms=прошло)

        сырое = процесс.stdout.split(маркер, 1)[1].strip()
        try:
            данные = json.loads(сырое)
        except ValueError:
            return РезультатЗапуска(passed=False, error="Не удалось разобрать результат", duration_ms=прошло)

        проверки = [
            РезультатПроверки(
                call=п["call"], expected=п.get("expected"), got=п.get("got"),
                passed=bool(п.get("passed")), error=п.get("error", ""),
            )
            for п in данные.get("checks", [])
        ]
        успех = bool(проверки) and all(п.passed for п in проверки) and not данные.get("error")
        if not проверки and not данные.get("error"):
            успех = True  # задание без проверок: достаточно что код отработал
        return РезультатЗапуска(
            passed=успех, stdout=данные.get("stdout", ""), error=данные.get("error", ""),
            duration_ms=прошло, checks=проверки,
        )
