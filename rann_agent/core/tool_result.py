"""
Tool Result

Structured result from tool execution.
Implements V3 Section 6 specification.
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class ToolResult:
    """
    Structured result from tool execution.

    Attributes:
        call_id: Unique identifier for this tool call
        tool_name: Name of the tool that was executed
        command: The command that was executed (for shell tools)
        success: Whether the tool executed successfully
        exit_code: Process exit code if applicable
        stdout: Standard output from the tool
        stderr: Standard error from the tool
        duration_ms: Execution time in milliseconds
        timed_out: Whether the execution timed out
        cancelled: Whether the execution was cancelled
        error_type: Type of error if execution failed
        error_message: Error message if execution failed
        artifacts: List of artifact paths/files produced
        evidence_id: Optional ID linking to evidence ledger
    """

    call_id: str
    tool_name: str
    command: str | None
    success: bool
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    cancelled: bool = False
    error_type: str | None = None
    error_message: str | None = None
    artifacts: list[str] = field(default_factory=list)
    evidence_id: str | None = None

    def __post_init__(self):
        """Validate and normalize result after initialization"""
        # Ensure stdout and stderr are strings
        if self.stdout is None:
            self.stdout = ""
        if self.stderr is None:
            self.stderr = ""

    @property
    def summary(self) -> str:
        """Get a one-line summary of the result"""
        if self.timed_out:
            return f"[TIMEOUT] {self.tool_name} after {self.duration_ms:.0f}ms"
        if self.cancelled:
            return f"[CANCELLED] {self.tool_name}"
        if self.success:
            return f"[OK] {self.tool_name} ({self.duration_ms:.0f}ms)"
        return f"[FAIL:{self.exit_code}] {self.tool_name}: {self.error_message or 'unknown error'}"

    @property
    def has_output(self) -> bool:
        """Check if tool produced any output"""
        return bool(self.stdout.strip() or self.stderr.strip())

    @property
    def output_lines(self) -> list[str]:
        """Get stdout as list of lines"""
        return [line for line in self.stdout.split("\n") if line]

    @property
    def error_lines(self) -> list[str]:
        """Get stderr as list of lines"""
        return [line for line in self.stderr.split("\n") if line]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "command": self.command,
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "artifacts": self.artifacts,
            "evidence_id": self.evidence_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolResult":
        """Deserialize from dictionary"""
        return cls(
            call_id=data["call_id"],
            tool_name=data["tool_name"],
            command=data.get("command"),
            success=data["success"],
            exit_code=data.get("exit_code"),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            duration_ms=data["duration_ms"],
            timed_out=data.get("timed_out", False),
            cancelled=data.get("cancelled", False),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
            artifacts=data.get("artifacts", []),
            evidence_id=data.get("evidence_id"),
        )

    @classmethod
    def success_result(
        cls,
        call_id: str,
        tool_name: str,
        command: str | None = None,
        stdout: str = "",
        stderr: str = "",
        duration_ms: float = 0.0,
        artifacts: list[str] | None = None,
        evidence_id: str | None = None,
    ) -> "ToolResult":
        """Factory for successful results"""
        return cls(
            call_id=call_id,
            tool_name=tool_name,
            command=command,
            success=True,
            exit_code=0,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            artifacts=artifacts or [],
            evidence_id=evidence_id,
        )

    @classmethod
    def error_result(
        cls,
        call_id: str,
        tool_name: str,
        command: str | None = None,
        exit_code: int = -1,
        error_message: str = "",
        error_type: str | None = None,
        stdout: str = "",
        stderr: str = "",
        duration_ms: float = 0.0,
        evidence_id: str | None = None,
    ) -> "ToolResult":
        """Factory for error results"""
        return cls(
            call_id=call_id,
            tool_name=tool_name,
            command=command,
            success=False,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            error_type=error_type,
            error_message=error_message,
            evidence_id=evidence_id,
        )

    @classmethod
    def timeout_result(
        cls,
        call_id: str,
        tool_name: str,
        command: str | None = None,
        duration_ms: float = 0.0,
    ) -> "ToolResult":
        """Factory for timeout results"""
        return cls(
            call_id=call_id,
            tool_name=tool_name,
            command=command,
            success=False,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            timed_out=True,
            error_type="TimeoutError",
            error_message=f"Tool {tool_name} timed out after {duration_ms:.0f}ms",
        )

    @classmethod
    def cancelled_result(
        cls,
        call_id: str,
        tool_name: str,
        command: str | None = None,
        duration_ms: float = 0.0,
    ) -> "ToolResult":
        """Factory for cancelled results"""
        return cls(
            call_id=call_id,
            tool_name=tool_name,
            command=command,
            success=False,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            cancelled=True,
            error_type="CancelledError",
            error_message=f"Tool {tool_name} was cancelled",
        )


def result_to_summary(result: ToolResult) -> dict[str, Any]:
    """
    Convert ToolResult to a summary dict for logging.

    Args:
        result: The ToolResult to summarize

    Returns:
        Summary dictionary suitable for logging
    """
    return {
        "call_id": result.call_id,
        "tool_name": result.tool_name,
        "success": result.success,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "timed_out": result.timed_out,
        "cancelled": result.cancelled,
        "has_artifacts": len(result.artifacts) > 0,
        "artifact_count": len(result.artifacts),
        "has_evidence": result.evidence_id is not None,
    }
