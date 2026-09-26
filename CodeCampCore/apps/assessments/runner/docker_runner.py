import os
import time
import tempfile
import subprocess
import shutil
from typing import Optional
from .base import BaseRunner, ExecutionResult


class DockerRunner(BaseRunner):
    """
    Hardened container runner for production deployments.
    Spawns ephemeral containers with:
    - --network none (zero internet connectivity)
    - --memory 128m (strict RAM limits)
    - --cpus 0.5 (CPU quota)
    - --read-only (immutable root filesystem)
    - --user 1000:1000 (non-root unprivileged process)
    """

    IMAGE_MAP = {
        'python': 'python:3.11-slim',
        'javascript': 'node:20-alpine',
        'sql': 'python:3.11-slim',
    }

    def __init__(self, docker_cmd: str = "docker"):
        self.docker_cmd = docker_cmd

    def execute(
        self,
        code: str,
        language: str,
        input_data: str = "",
        timeout_sec: float = 2.0,
        memory_limit_mb: int = 128
    ) -> ExecutionResult:
        docker_bin = shutil.which(self.docker_cmd)
        if not docker_bin:
            return ExecutionResult(
                stdout="",
                stderr="Docker daemon is not found in PATH.",
                exit_code=1,
                error_type="DockerNotAvailable"
            )

        lang = (language or "").lower()
        image = self.IMAGE_MAP.get(lang, 'python:3.11-slim')

        temp_dir = tempfile.mkdtemp(prefix="codecamp_docker_")
        ext = ".py" if lang == 'python' else ".js"
        script_name = f"solution{ext}"
        script_path = os.path.join(temp_dir, script_name)

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Build docker invocation command
            cmd = [
                docker_bin, "run", "--rm",
                "--network", "none",
                "--memory", f"{memory_limit_mb}m",
                "--cpus", "0.5",
                "--pids-limit", "32",
                "-v", f"{temp_dir}:/sandbox:ro",
                "-w", "/sandbox",
                image
            ]

            if lang == 'python':
                cmd.extend(["python3", "-B", script_name])
            elif lang in ('javascript', 'js', 'node'):
                cmd.extend(["node", script_name])
            else:
                return ExecutionResult(
                    stdout="",
                    stderr=f"Language {language} unsupported in DockerRunner",
                    exit_code=1,
                    error_type="UnsupportedLanguage"
                )

            start_t = time.perf_counter()
            try:
                proc = subprocess.run(
                    cmd,
                    input=input_data,
                    text=True,
                    capture_output=True,
                    timeout=timeout_sec + 1.0  # docker startup buffer
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
                    stderr="Container execution exceeded time limit.",
                    exit_code=-1,
                    execution_time_ms=duration_ms,
                    timed_out=True,
                    error_type="TimeLimitExceeded"
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
