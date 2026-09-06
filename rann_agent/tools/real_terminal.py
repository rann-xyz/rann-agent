"""
Real terminal executor for RANN Agent.
Multi-shell provider architecture with optional PTY support.
"""

from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

MAX_OUTPUT_SIZE = 1024 * 1024  # 1MB per stdout/stderr


# ---------------------------------------------------------------------------
# ToolResult dataclass (kept for backward compatibility)
# ---------------------------------------------------------------------------


@dataclass
class ToolResult:
    """Structured result from tool execution."""

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


# ---------------------------------------------------------------------------
# ShellProvider abstract base class + concrete implementations
# ---------------------------------------------------------------------------


class ShellProvider(ABC):
    """
    Abstract base for shell execution providers.

    Subclasses must implement:
      - name: str  (provider identifier)
      - _build_cmd(self, command: str) -> List[str]  (shell invocation)
      - _supports_input(self) -> bool  (whether stdin is supported)

    The execute() method is shared; subclasses only need to provide the
    command-building logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. 'bash', 'zsh', 'python3'."""
        ...

    @abstractmethod
    def _build_cmd(self, command: str) -> list[str]:
        """
        Return the argument list used to run *command* in this shell.

        Example for BashProvider: ['/bin/bash', '-c', command]
        Example for PythonProvider: ['python3', '-c', command]
        """
        ...

    def _supports_input(self) -> bool:
        """Whether this provider reads from stdin."""
        return True

    def _shell_wrapper(self) -> bool:
        """Whether this provider wraps the command in a shell (vs. direct exec)."""
        return True

    # ------------------------------------------------------------------
    # Shared execute() — same timeout / env / cwd / error-handling logic
    # for every provider.
    # ------------------------------------------------------------------

    def execute(
        self,
        command: str,
        cwd: str,
        timeout: int,
        env: dict[str, str],
        input_data: str | None = None,
    ) -> ToolResult:
        """
        Run *command* in this shell and return a ToolResult.

        This is the canonical execution path shared by all providers.
        Subclasses only override _build_cmd() to specialise the subprocess
        invocation.
        """

        call_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]
        start_time = time.time()

        cmd_list = self._build_cmd(command)
        cmd_str = command  # Preserve original command string for ToolResult

        logger.info(
            "shell_provider_executing",
            provider=self.name,
            call_id=call_id,
            command=cmd_str,
            cwd=cwd,
            timeout=timeout,
        )

        try:
            proc = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=(
                    subprocess.PIPE if (input_data and self._supports_input()) else None
                ),
                cwd=cwd,
                env=env,
                shell=False,  # Security: never enable shell=True
                preexec_fn=os.setsid,  # Process group for cancellation
            )

            if input_data and proc.stdin:
                proc.stdin.write(input_data.encode())
                proc.stdin.close()

            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(
                    "shell_provider_timed_out",
                    provider=self.name,
                    call_id=call_id,
                    timeout=timeout,
                )
                return self._make_result(
                    call_id=call_id,
                    command=cmd_str,
                    success=False,
                    exit_code=None,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    duration_ms=duration_ms,
                    timed_out=True,
                    error_type="TimeoutError",
                    error_message=f"Command exceeded {timeout}s timeout",
                )

            stdout = self._decode(stdout_bytes)
            stderr = self._decode(stderr_bytes)

            stdout = self._truncate(stdout, "stdout")
            stderr = self._truncate(stderr, "stderr")

            duration_ms = (time.time() - start_time) * 1000
            exit_code = proc.returncode
            success = exit_code == 0

            logger.info(
                "shell_provider_completed",
                provider=self.name,
                call_id=call_id,
                exit_code=exit_code,
                duration_ms=round(duration_ms, 2),
            )

            return self._make_result(
                call_id=call_id,
                command=cmd_str,
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
            )

        except FileNotFoundError as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "shell_provider_not_found",
                provider=self.name,
                call_id=call_id,
                error=str(e),
            )
            return self._make_result(
                call_id=call_id,
                command=cmd_str,
                success=False,
                exit_code=127,
                stdout="",
                stderr=f"Command not found: {cmd_list[0]}",
                duration_ms=duration_ms,
                error_type="FileNotFoundError",
                error_message=str(e),
            )

        except PermissionError as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "shell_provider_permission_denied",
                provider=self.name,
                call_id=call_id,
                error=str(e),
            )
            return self._make_result(
                call_id=call_id,
                command=cmd_str,
                success=False,
                exit_code=126,
                stdout="",
                stderr=f"Permission denied: {cmd_str}",
                duration_ms=duration_ms,
                error_type="PermissionError",
                error_message=str(e),
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "shell_provider_error",
                provider=self.name,
                call_id=call_id,
                error=str(e),
            )
            return self._make_result(
                call_id=call_id,
                command=cmd_str,
                success=False,
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_message=str(e),
            )

    # ------------------------------------------------------------------
    # Helper methods (can be overridden by subclasses if needed)
    # ------------------------------------------------------------------

    def _decode(self, data: bytes) -> str:
        """Decode bytes to string, replacing malformed characters."""
        return data.decode("utf-8", errors="replace")

    def _truncate(self, text: str, label: str) -> str:
        """Truncate output exceeding MAX_OUTPUT_SIZE."""
        if len(text) > MAX_OUTPUT_SIZE:
            logger.warning(
                "output_truncated",
                provider=self.name,
                label=label,
                original_size=len(text),
            )
            return (
                text[:MAX_OUTPUT_SIZE]
                + f"\n... [{label} truncated, was {len(text)} bytes]"
            )
        return text

    def _make_result(
        self,
        call_id: str,
        command: str,
        success: bool,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        duration_ms: float,
        timed_out: bool = False,
        cancelled: bool = False,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> ToolResult:
        """Construct a ToolResult with all fields populated."""
        return ToolResult(
            call_id=call_id,
            tool_name="terminal",
            command=command,
            success=success,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
            cancelled=cancelled,
            error_type=error_type,
            error_message=error_message,
        )


# ---------------------------------------------------------------------------
# Concrete shell providers
# ---------------------------------------------------------------------------


class BashProvider(ShellProvider):
    """Execute commands via /bin/bash -c."""

    name = "bash"

    def _build_cmd(self, command: str) -> list[str]:
        return ["/bin/bash", "-c", command]

    @property
    def available(self) -> bool:
        return os.path.isfile("/bin/bash") and os.access("/bin/bash", os.X_OK)


class ZshProvider(ShellProvider):
    """Execute commands via /bin/zsh -c, falling back to bash if unavailable."""

    name = "zsh"

    def _build_cmd(self, command: str) -> list[str]:
        return ["/bin/zsh", "-c", command]

    @property
    def available(self) -> bool:
        return os.path.isfile("/bin/zsh") and os.access("/bin/zsh", os.X_OK)


class PwshProvider(ShellProvider):
    """Execute commands via PowerShell Core (pwsh) -c."""

    name = "pwsh"

    def _build_cmd(self, command: str) -> list[str]:
        return ["/usr/bin/pwsh", "-c", command]

    @property
    def available(self) -> bool:
        return os.path.isfile("/usr/bin/pwsh") and os.access("/usr/bin/pwsh", os.X_OK)


class CmdProvider(ShellProvider):
    """Execute commands via Windows cmd.exe /C ( Wine/Crossover on Linux, or native on Windows)."""

    name = "cmd"

    def _build_cmd(self, command: str) -> list[str]:
        return ["/bin/cmd", "/C", command]

    @property
    def available(self) -> bool:
        # Only available on Windows or under Wine
        return os.path.isfile("/bin/cmd") and os.access("/bin/cmd", os.X_OK)


class FishProvider(ShellProvider):
    """Execute commands via /usr/bin/fish -c."""

    name = "fish"

    def _build_cmd(self, command: str) -> list[str]:
        return ["/usr/bin/fish", "-c", command]

    @property
    def available(self) -> bool:
        return os.path.isfile("/usr/bin/fish") and os.access("/usr/bin/fish", os.X_OK)


class PythonProvider(ShellProvider):
    """Execute inline Python via python3 -c (no shell wrapping)."""

    name = "python3"

    def _build_cmd(self, command: str) -> list[str]:
        return ["python3", "-c", command]

    @property
    def available(self) -> bool:
        return os.path.isfile("/usr/bin/python3") and os.access(
            "/usr/bin/python3", os.X_OK
        )


# ---------------------------------------------------------------------------
# PTYProvider — interactive pseudo-terminal shell
# ---------------------------------------------------------------------------


class PTYProvider(ShellProvider):
    """
    Interactive PTY-backed shell using pty.openpty().

    Runs ``bash -i -s`` (interactive, reading commands from stdin) and
    maintains a command history buffer across calls so that consecutive
    executions share a single shell session.

    Window-resize events (SIGWINCH) are forwarded to the PTY slave so
    that interactive tools (e.g. vim, less) respond correctly.

    Enable via ``terminal.pty_enabled: true`` in config.
    """

    name = "pty"

    def __init__(self) -> None:
        super().__init__()
        self._master_fd: int | None = None
        self._slave_fd: int | None = None
        self._proc: subprocess.Popen | None = None
        self._history: list[str] = []
        self._closed = False

    # ------------------------------------------------------------------
    # ShellProvider interface
    # ------------------------------------------------------------------

    def _build_cmd(self, command: str) -> list[str]:
        # Not used when we manage the PTY directly
        return ["/bin/bash", "-i", "-s"]

    def _supports_input(self) -> bool:
        return True

    def _shell_wrapper(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_running(self, cwd: str, env: dict[str, str]) -> None:
        """Start the interactive bash process if it is not already running."""
        if self._proc is not None and self._proc.poll() is None:
            return

        self._master_fd, self._slave_fd = os.openpty()
        self._closed = False

        # Set environment so bash knows it's interactive
        env = dict(env)
        env.setdefault("TERM", os.environ.get("TERM", "xterm-256color"))

        self._proc = subprocess.Popen(
            ["/bin/bash", "-i", "-s"],
            stdin=self._slave_fd,
            stdout=self._slave_fd,
            stderr=self._slave_fd,
            cwd=cwd,
            env=env,
            # Use start_new_session OR preexec_fn=os.setsid, not both.
            # start_new_session=True calls setsid() in the child.
            start_new_session=True,
        )

        # Close slave FD in master process — child has its own reference
        os.close(self._slave_fd)
        self._slave_fd = None

        # Drain any initial bash output (e.g. motd, welcome messages)
        self._drain_pty(timeout=1.0)

    def _drain_pty(self, timeout: float = 0.5) -> str:
        """Read available output from the PTY without blocking."""
        import select as _select

        if self._master_fd is None:
            return ""
        data = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                rd, _, _ = _select.select([self._master_fd], [], [], 0.05)
                if rd:
                    chunk = os.read(self._master_fd, 4096)
                    if not chunk:
                        break
                    data += chunk
            except OSError:
                break
        return data.decode("utf-8", errors="replace")

    def _write_command(self, command: str) -> None:
        """Send a command + newline to the PTY."""
        if self._master_fd is None:
            raise RuntimeError("PTY not open")
        os.write(self._master_fd, (command + "\n").encode())

    def _read_output(self, timeout: float = 30.0) -> str:
        """Read output until the shell prompt reappears or timeout."""
        import select as _select

        if self._master_fd is None:
            return ""
        output = b""
        deadline = time.time() + timeout

        # Simple prompt detection: read until we see a line ending with
        # one of the common bash prompt characters (#, $, %)
        # The shell echoes the command we sent, so we strip that below.
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                rd, _, _ = _select.select(
                    [self._master_fd], [], [], min(0.1, remaining)
                )
                if rd:
                    chunk = os.read(self._master_fd, 4096)
                    if not chunk:
                        break
                    output += chunk
                    # Heuristic: if we see a line that ends with prompt chars
                    # and contains at least one newline, we're probably done.
                    if self._looks_like_prompt_output(output):
                        break
            except OSError:
                break

        return output.decode("utf-8", errors="replace")

    PROMPT_RE = re.compile(r"[#$%]\s*$", re.MULTILINE)

    def _looks_like_prompt_output(self, data: bytes) -> bool:
        """Return True if the data looks like shell output that has finished."""
        try:
            text = data.decode("utf-8", errors="replace")
            # We want at least one newline and a trailing prompt marker
            return bool(self.PROMPT_RE.search(text))
        except Exception:
            return False

    def _strip_echo(self, command: str, output: str) -> str:
        """Remove the echoed command line from output."""
        # The PTY echoes the command we typed; strip the first line if it matches.
        escaped = re.escape(command)
        pattern = rf"^\s*{escaped}\s*$"
        return re.sub(pattern, "", output, count=1, flags=re.MULTILINE).lstrip()

    def execute(
        self,
        command: str,
        cwd: str,
        timeout: int,
        env: dict[str, str],
        input_data: str | None = None,
    ) -> ToolResult:

        call_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]
        start_time = time.time()

        logger.info(
            "pty_provider_executing",
            call_id=call_id,
            command=command,
            cwd=cwd,
            timeout=timeout,
        )

        try:
            self._ensure_running(cwd=cwd, env=env)

            if self._master_fd is None:
                raise RuntimeError("Failed to open PTY")

            # Send the command
            self._write_command(command)

            # Read response
            raw_output = self._read_output(timeout=float(timeout))

            # Strip echoed command
            stdout = self._strip_echo(command, raw_output)

            # Truncate
            stdout = self._truncate(stdout, "stdout")

            duration_ms = (time.time() - start_time) * 1000

            # Capture exit code via $?
            self._write_command("echo __EXIT_CODE__=$?")
            raw_exit = self._read_output(timeout=2.0)
            exit_code_str = self._extract_exit_code(raw_exit)
            try:
                exit_code = int(exit_code_str) if exit_code_str else 0
            except ValueError:
                exit_code = 0

            success = exit_code == 0

            # Append to persistent history
            self._history.append(command)

            logger.info(
                "pty_provider_completed",
                call_id=call_id,
                exit_code=exit_code,
                duration_ms=round(duration_ms, 2),
            )

            return self._make_result(
                call_id=call_id,
                command=command,
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr="",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("pty_provider_error", call_id=call_id, error=str(e))
            return self._make_result(
                call_id=call_id,
                command=command,
                success=False,
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_message=str(e),
            )

    def _extract_exit_code(self, output: str) -> str:
        """Parse __EXIT_CODE__=<N> from output."""
        m = re.search(r"__EXIT_CODE__=(\d+)", output)
        return m.group(1) if m else ""

    def close(self) -> None:
        """Shut down the PTY shell and clean up file descriptors."""
        if self._proc is not None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
                except Exception:
                    pass
            self._proc = None

        for fd in [self._master_fd, self._slave_fd]:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass

        self._master_fd = None
        self._slave_fd = None
        self._closed = True

    @property
    def history(self) -> list[str]:
        """Return the command history accumulated so far."""
        return list(self._history)

    def handle_sigwinch(self, signum: int, frame: Any) -> None:
        """Handle window resize signal by updating PTY size."""
        if self._master_fd is None or self._slave_fd is None:
            return
        try:
            import fcntl
            import struct
            import termios

            size = struct.pack("HHHH", 0, 0, 0, 0)
            # Get current window size from slave
            try:
                winsize = fcntl.ioctl(self._slave_fd, termios.TIOCGWINSZ, size)
            except OSError:
                return
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
        except Exception as ex:
            logger.warning("pty_sigwinch_failed", error=str(ex))


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_PROVIDER_REGISTRY: dict[str, ShellProvider] = {}


def _make_provider(name: str) -> ShellProvider | None:
    """Instantiate a provider by name, or return None if unavailable."""
    factories = {
        "bash": BashProvider,
        "zsh": ZshProvider,
        "pwsh": PwshProvider,
        "cmd": CmdProvider,
        "fish": FishProvider,
        "python3": PythonProvider,
        "pty": PTYProvider,
    }
    cls = factories.get(name)
    if cls is None:
        return None
    provider = cls()
    # Check availability; skip providers that aren't installed
    if hasattr(provider, "available") and not provider.available:
        logger.debug("shell_provider_unavailable", provider=name)
        return None
    return provider


def get_shell_provider(name: str) -> ShellProvider | None:
    """
    Return a singleton instance of the named shell provider.

    The same provider instance is returned on every call for the same *name*.
    Returns None if the provider is unknown or unavailable on this system.
    """
    if name not in _PROVIDER_REGISTRY:
        _PROVIDER_REGISTRY[name] = _make_provider(name) or _PROVIDER_REGISTRY.get(name)
    return _PROVIDER_REGISTRY.get(name)


def reset_shell_providers() -> None:
    """Clear the provider singleton cache (useful for testing)."""
    for p in _PROVIDER_REGISTRY.values():
        if hasattr(p, "close"):
            p.close()
    _PROVIDER_REGISTRY.clear()


# ---------------------------------------------------------------------------
# RealTerminalExecutor — the public API
# ---------------------------------------------------------------------------


class RealTerminalExecutor:
    """
    Production-quality command executor with pluggable shell providers.

    Backward-compatible with the original single-shell implementation:
    the execute() signature is unchanged, with the addition of an optional
    ``shell`` keyword argument that selects which provider to use.

    When ``terminal.pty_enabled: true`` is set in config the PTY provider
    is used automatically, giving a fully interactive shell experience.

    Config schema::

        terminal:
            default_shell: bash
            allowed_shells: [bash, zsh, fish, python3]
            pty_enabled: false
            workspace_root: null
            default_timeout: 60
            allowed_env_vars: []
            forbidden_env_patterns: [API_KEY, SECRET, PASSWORD, TOKEN, PRIVATE,
                                     ANTHROPIC, OPENAI, HERMES]
    """

    def __init__(
        self,
        workspace_root: str | None = None,
        allowed_env_vars: list[str] | None = None,
        forbidden_env_patterns: list[str] | None = None,
        default_timeout: int = 60,
        *,
        default_shell: str = "bash",
        allowed_shells: list[str] | None = None,
        pty_enabled: bool = False,
    ) -> None:
        self.workspace_root = (
            os.path.abspath(workspace_root) if workspace_root else os.getcwd()
        )
        self.allowed_env_vars = allowed_env_vars or []
        self.forbidden_env_patterns = forbidden_env_patterns or [
            "API_KEY",
            "SECRET",
            "PASSWORD",
            "TOKEN",
            "PRIVATE",
            "ANTHROPIC",
            "OPENAI",
            "HERMES",
        ]
        self.default_timeout = default_timeout
        self.default_shell = default_shell
        self.allowed_shells = allowed_shells or ["bash", "zsh", "fish", "python3"]
        self.pty_enabled = pty_enabled

        # Install SIGWINCH handler if PTY is enabled
        if self.pty_enabled:
            self._pty_provider: PTYProvider | None = None
            # Defer PTYProvider creation until first use so that signal
            # handlers are registered in the main thread on Unix.
        else:
            self._pty_provider = None

        logger.info(
            "terminal_executor_initialized",
            workspace_root=self.workspace_root,
            default_shell=self.default_shell,
            allowed_shells=self.allowed_shells,
            pty_enabled=self.pty_enabled,
        )

    # ------------------------------------------------------------------
    # Environment and cwd helpers
    # ------------------------------------------------------------------

    def _filter_env(self, env: dict[str, str]) -> dict[str, str]:
        """Remove forbidden environment variables."""
        filtered: dict[str, str] = {}
        for key, value in env.items():
            upper_key = key.upper()
            if any(pat in upper_key for pat in self.forbidden_env_patterns):
                continue
            if self.allowed_env_vars and key not in self.allowed_env_vars:
                continue
            filtered[key] = value
        return filtered

    def _validate_cwd(self, cwd: str) -> str:
        """Ensure cwd is within workspace_root."""
        abs_cwd = os.path.abspath(cwd)
        if not abs_cwd.startswith(self.workspace_root):
            raise ValueError(
                f"Working directory {abs_cwd} is outside workspace {self.workspace_root}"
            )
        return abs_cwd

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    def _resolve_provider(self, shell: str | None) -> ShellProvider:
        """
        Return the ShellProvider for *shell*, falling back sensibly.

        Priority:
        1. Explicit *shell* argument if provided and allowed.
        2. PTY provider if self.pty_enabled is True.
        3. default_shell from config.
        4. 'bash' as last resort.
        """
        if shell and shell in self.allowed_shells:
            provider = get_shell_provider(shell)
            if provider is not None:
                return provider
            # Fall through to next option

        if self.pty_enabled:
            # Lazy-init PTYProvider so it is created in the main thread
            if self._pty_provider is None:
                self._pty_provider = PTYProvider()
                # Register SIGWINCH handler (Unix only)
                if hasattr(signal, "SIGWINCH"):
                    signal.signal(
                        signal.SIGWINCH,
                        lambda s, f: self._pty_provider.handle_sigwinch(s, f),
                    )
            return self._pty_provider

        provider = get_shell_provider(self.default_shell)
        if provider is not None:
            return provider

        # Last-resort fallback to bash (should always be present on Unix)
        bash = get_shell_provider("bash")
        if bash is not None:
            return bash

        raise RuntimeError("No shell provider available (tried bash)")

    # ------------------------------------------------------------------
    # Public execute() — backward-compatible signature
    # ------------------------------------------------------------------

    def execute(
        self,
        command: str | list[str],
        cwd: str | None = None,
        timeout: int | None = None,
        input_data: str | None = None,
        check: bool = False,
        shell: str | None = None,
    ) -> ToolResult:
        """
        Execute *command* and return a structured ToolResult.

        Backward-compatible signature::

            execute(command, cwd=None, timeout=None, input_data=None,
                    check=False, shell=None)

        Parameters
        ----------
        command:
            Shell command string or list of arguments.
        cwd:
            Working directory (default: workspace_root).
        timeout:
            Timeout in seconds (default: default_timeout from config).
        input_data:
            String to send to stdin.
        check:
            Raise CalledProcessError on non-zero exit (like subprocess.check_call).
        shell:
            Shell provider to use: 'bash', 'zsh', 'pwsh', 'cmd', 'fish',
            'python3', or 'pty'.  Defaults to config.default_shell or 'bash'.

        Returns
        -------
        ToolResult
        """
        import time as time_module

        start_time = time_module.time()

        # Normalise command to string
        if isinstance(command, list):
            cmd_str = " ".join(command)
        else:
            cmd_str = command

        # Validate cwd
        work_dir = self._validate_cwd(cwd or self.workspace_root)

        # Filter environment
        env = self._filter_env(os.environ.copy())

        # Resolve provider
        provider = self._resolve_provider(shell)

        # Normalise timeout
        timeout_val = timeout or self.default_timeout

        logger.info(
            "terminal_execute",
            shell_provider=provider.name,
            command=cmd_str,
            cwd=work_dir,
            timeout=timeout_val,
        )

        # Delegate to provider
        result = provider.execute(
            command=cmd_str,
            cwd=work_dir,
            timeout=timeout_val,
            env=env,
            input_data=input_data,
        )

        duration_ms = (time_module.time() - start_time) * 1000
        # Ensure duration_ms reflects wall-clock time
        result.duration_ms = duration_ms

        if check and not result.success:
            raise subprocess.CalledProcessError(result.exit_code or 1, cmd_str)

        return result

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel(self, call_id: str) -> bool:
        """
        Cancel a running command by sending SIGTERM to its process group.

        Note: cancellation is best-effort; the process may have already
        terminated.  This method currently affects the most recently
        launched PTY process; in a full multi-process implementation
        each execute() would be tracked independently.
        """
        logger.info("cancel_requested", call_id=call_id)
        if self._pty_provider is not None:
            try:
                self._pty_provider.close()
            except Exception as e:
                logger.warning("pty_cancel_failed", error=str(e))
        return True

    def close(self) -> None:
        """Clean up all providers (especially PTY)."""
        if self._pty_provider is not None:
            self._pty_provider.close()
            self._pty_provider = None
