import os
import sys
import time
import tempfile
import subprocess
import shutil
import sqlite3
from typing import Optional
from .base import BaseRunner, ExecutionResult


PYTHON_SANDBOX_PRELUDE = """# -*- coding: utf-8 -*-
import sys
import builtins

# Block dangerous operations in dev sandbox
_BLOCKED_MODULES = {
    'subprocess', 'shutil', 'socket', 'http', 'urllib',
    'requests', 'asyncio', 'multiprocessing', 'threading', 'posix', 'nt'
}

_orig_import = builtins.__import__

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root_pkg = name.split('.')[0]
    if root_pkg in _BLOCKED_MODULES:
        raise ImportError(f"Security restriction: module '{root_pkg}' is prohibited in this sandbox.")
    return _orig_import(name, globals, locals, fromlist, level)

builtins.__import__ = _safe_import

# Prohibit os module command executions
try:
    import os
    os.system = None
    os.popen = None
    os.spawnl = None
    os.execv = None
except Exception:
    pass
"""


class SubprocessSandboxRunner(BaseRunner):
    """
    Local development and fallback runner.
    Executes student code inside isolated child processes with security wrappers,
    strict per-test timeouts, and captured IO.
    """

    def execute(
        self,
        code: str,
        language: str,
        input_data: str = "",
        timeout_sec: float = 2.0,
        memory_limit_mb: int = 128
    ) -> ExecutionResult:
        lang = (language or "").lower()
        if lang == 'python':
            return self._run_python(code, input_data, timeout_sec)
        elif lang in ('javascript', 'js', 'node'):
            return self._run_javascript(code, input_data, timeout_sec)
        elif lang == 'sql':
            return self._run_sql(code, input_data, timeout_sec)
        else:
            return ExecutionResult(
                stdout="",
                stderr=f"Unsupported execution language: {language}",
                exit_code=1,
                error_type="UnsupportedLanguage"
            )

    def _run_python(self, code: str, input_data: str, timeout_sec: float) -> ExecutionResult:
        temp_dir = tempfile.mkdtemp(prefix="codecamp_py_")
        script_path = os.path.join(temp_dir, "solution.py")

        try:
            full_code = f"{PYTHON_SANDBOX_PRELUDE}\n# --- Student Submission ---\n{code}"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(full_code)

            start_t = time.perf_counter()
            try:
                proc = subprocess.run(
                    [sys.executable, "-B", script_path],
                    input=input_data,
                    text=True,
                    capture_output=True,
                    timeout=timeout_sec,
                    cwd=temp_dir
                )
                duration_ms = round((time.perf_counter() - start_t) * 1000, 2)

                stdout = proc.stdout[:65536]  # cap output at 64KB
                stderr = proc.stderr[:65536]
                error_type = None

                if proc.returncode != 0:
                    if "Security restriction" in stderr:
                        error_type = "SecurityViolation"
                    elif "RecursionError" in stderr:
                        error_type = "RecursionLimitExceeded"
                    else:
                        error_type = "RuntimeError"

                return ExecutionResult(
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=proc.returncode,
                    execution_time_ms=duration_ms,
                    timed_out=False,
                    error_type=error_type
                )

            except subprocess.TimeoutExpired as exc:
                duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
                return ExecutionResult(
                    stdout=(exc.stdout or "")[:65536],
                    stderr="Process exceeded time limit.",
                    exit_code=-1,
                    execution_time_ms=duration_ms,
                    timed_out=True,
                    error_type="TimeLimitExceeded"
                )

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _run_javascript(self, code: str, input_data: str, timeout_sec: float) -> ExecutionResult:
        node_bin = shutil.which("node")
        if not node_bin:
            return ExecutionResult(
                stdout="",
                stderr="Node.js runtime is not available on this host. Please contact academy support.",
                exit_code=1,
                error_type="MissingRuntime"
            )

        temp_dir = tempfile.mkdtemp(prefix="codecamp_js_")
        script_path = os.path.join(temp_dir, "solution.js")

        try:
            # Wrap to safely read stdin if requested
            js_prelude = """
            // JavaScript Sandbox wrapper
            const fs = require('fs');
            """
            full_code = f"{js_prelude}\n{code}"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(full_code)

            start_t = time.perf_counter()
            try:
                proc = subprocess.run(
                    [node_bin, "--disallow-code-generation-from-strings", script_path],
                    input=input_data,
                    text=True,
                    capture_output=True,
                    timeout=timeout_sec,
                    cwd=temp_dir
                )
                duration_ms = round((time.perf_counter() - start_t) * 1000, 2)

                return ExecutionResult(
                    stdout=proc.stdout[:65536],
                    stderr=proc.stderr[:65536],
                    exit_code=proc.returncode,
                    execution_time_ms=duration_ms,
                    timed_out=False,
                    error_type="RuntimeError" if proc.returncode != 0 else None
                )
            except subprocess.TimeoutExpired:
                duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
                return ExecutionResult(
                    stdout="",
                    stderr="JavaScript execution exceeded time limit.",
                    exit_code=-1,
                    execution_time_ms=duration_ms,
                    timed_out=True,
                    error_type="TimeLimitExceeded"
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _run_sql(self, code: str, input_data: str, timeout_sec: float) -> ExecutionResult:
        """
        Executes SQL queries against an ephemeral in-memory SQLite database.
        input_data can optionally contain schema/DDL setup statements.
        """
        start_t = time.perf_counter()
        try:
            conn = sqlite3.connect(":memory:")
            cursor = conn.cursor()

            # Execute schema setup if present
            if input_data.strip():
                cursor.executescript(input_data)

            # Execute student query
            cursor.execute(code.strip())
            rows = cursor.fetchall()
            conn.commit()

            output_lines = []
            for row in rows[:500]:  # Cap at 500 rows
                output_lines.append(", ".join(str(val) for val in row))

            stdout = "\n".join(output_lines)
            duration_ms = round((time.perf_counter() - start_t) * 1000, 2)

            return ExecutionResult(
                stdout=stdout,
                stderr="",
                exit_code=0,
                execution_time_ms=duration_ms,
                timed_out=False
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return ExecutionResult(
                stdout="",
                stderr=str(exc),
                exit_code=1,
                execution_time_ms=duration_ms,
                error_type="SQLError"
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass
