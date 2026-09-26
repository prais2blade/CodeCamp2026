from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod


@dataclass
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: float = 0.0
    memory_kb: float = 0.0
    timed_out: bool = False
    error_type: Optional[str] = None  # 'Timeout', 'MemoryLimit', 'RuntimeError', 'SecurityViolation', etc.

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.error_type


@dataclass
class CaseEvaluation:
    test_case_id: int
    title: str
    passed: bool
    input_data: str
    expected_output: str
    actual_output: str
    error_message: str = ""
    execution_time_ms: float = 0.0
    is_hidden: bool = False
    points_awarded: int = 0
    points_possible: int = 10


class BaseRunner(ABC):
    """
    Abstract interface for code execution runners.
    Implementations must isolate student code execution from the host Django process.
    """

    @abstractmethod
    def execute(
        self,
        code: str,
        language: str,
        input_data: str = "",
        timeout_sec: float = 2.0,
        memory_limit_mb: int = 128
    ) -> ExecutionResult:
        pass

    def evaluate_test_cases(
        self,
        code: str,
        language: str,
        test_cases: List[Any],
        timeout_sec: float = 2.0,
        memory_limit_mb: int = 128
    ) -> List[CaseEvaluation]:
        """
        Runs code sequentially or in batch against all provided test cases.
        """
        results: List[CaseEvaluation] = []
        for tc in test_cases:
            res = self.execute(
                code=code,
                language=language,
                input_data=tc.input_data or "",
                timeout_sec=timeout_sec,
                memory_limit_mb=memory_limit_mb
            )

            actual = (res.stdout or "").strip()
            expected = (tc.expected_output or "").strip()

            # Normalise line endings for consistent comparisons
            actual_norm = "\n".join(line.rstrip() for line in actual.splitlines())
            expected_norm = "\n".join(line.rstrip() for line in expected.splitlines())

            passed = (res.is_success and actual_norm == expected_norm)
            points_awarded = tc.points if passed else 0

            error_msg = ""
            if res.timed_out:
                error_msg = f"Time Limit Exceeded ({timeout_sec}s)"
            elif res.error_type:
                error_msg = f"[{res.error_type}] {res.stderr}"
            elif not passed and res.stderr:
                error_msg = res.stderr

            results.append(
                CaseEvaluation(
                    test_case_id=tc.id,
                    title=tc.title,
                    passed=passed,
                    input_data=tc.input_data,
                    expected_output=expected,
                    actual_output=actual,
                    error_message=error_msg,
                    execution_time_ms=res.execution_time_ms,
                    is_hidden=tc.is_hidden,
                    points_awarded=points_awarded,
                    points_possible=tc.points
                )
            )

        return results
