import os
import shutil
import subprocess
from django.conf import settings
from .base import BaseRunner
from .subprocess_runner import SubprocessSandboxRunner
from .docker_runner import DockerRunner


_runner_instance: BaseRunner = None


def _is_docker_healthy() -> bool:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False
    try:
        res = subprocess.run([docker_bin, "info"], capture_output=True, timeout=2)
        return res.returncode == 0
    except Exception:
        return False


def get_code_runner() -> BaseRunner:
    """
    Factory function to retrieve the configured code runner.
    In production environments with active Docker, returns DockerRunner.
    In local dev / Windows environments or when Docker is unavailable,
    falls back cleanly to SubprocessSandboxRunner.
    """
    global _runner_instance
    if _runner_instance is not None:
        return _runner_instance

    preferred_runner = getattr(settings, 'ASSESSMENT_CODE_RUNNER', 'auto')

    if preferred_runner == 'docker':
        _runner_instance = DockerRunner()
    elif preferred_runner == 'subprocess':
        _runner_instance = SubprocessSandboxRunner()
    else:  # 'auto'
        if _is_docker_healthy():
            _runner_instance = DockerRunner()
        else:
            _runner_instance = SubprocessSandboxRunner()

    return _runner_instance
