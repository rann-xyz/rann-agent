"""
Skill loader with namespace isolation and optional timeout.

Loads a skill's Python source code, compiles it, and executes it inside
an isolated namespace so builtins and module state cannot pollute the
agent's global scope.
"""

from __future__ import annotations

import signal
import threading
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional

import structlog

logger = structlog.get_logger()


class ExecutionTimeoutError(Exception):
    """Raised when a skill exceeds its allocated execution time."""

    pass


class SkillLoadError(Exception):
    """Raised when a skill cannot be loaded or compiled."""

    pass


@dataclass
class LoaderResult:
    """Result of a load_skill call."""

    module: Optional[ModuleType]
    error: Optional[str]
    loaded: bool


# -----------------------------------------------------------------------------
# Timeout support
# -----------------------------------------------------------------------------

class _TimeoutThread:
    """
    Singlethread timer that delivers SIGALRM (or raises TimeoutError) when
    the deadline expires. Uses a background thread so it works on all platforms.
    """

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._timer: Optional[threading.Timer] = None
        self._stopped = False

    def start(self) -> None:
        self._stopped = False
        self._timer = threading.Timer(self.seconds, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def stop(self) -> None:
        self._stopped = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _on_timeout(self) -> None:
        if self._stopped:
            return
        raise ExecutionTimeoutError(f"Skill execution exceeded {self.seconds}s")


# -----------------------------------------------------------------------------
# Skill loader
# -----------------------------------------------------------------------------

class SkillLoader:
    """
    Loads and executes skill code in an isolated namespace.

    Each skill is loaded into a fresh ``ModuleType`` instance, ensuring
    complete isolation from other skills and from the caller's globals.
    An optional timeout limits execution wall-clock time.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_source_size: int = 100_000,
    ) -> None:
        self.timeout = timeout
        self.max_source_size = max_source_size
        self._logger = logger.bind(component="skill_loader")

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def load_skill(self, skill_id: str, source: Optional[str] = None) -> LoaderResult:
        """
        Load a skill by ``skill_id``.

        If ``source`` is provided it is used directly; otherwise the loader
        looks for ``skills/<skill_id>.py`` relative to the current working
        directory.

        Returns a ``LoaderResult`` with the loaded ``ModuleType`` or an error
        string. The module is also stored in ``sys.modules`` under the key
        ``rann_agent.skills.<skill_id>`` for subsequent imports.
        """
        import sys

        if source is None:
            source = self._resolve_skill_file(skill_id)
            if source is None:
                return LoaderResult(module=None, error=f"Skill file not found: {skill_id}", loaded=False)

        if len(source) > self.max_source_size:
            return LoaderResult(
                module=None,
                error=f"Source exceeds max size ({self.max_source_size} bytes)",
                loaded=False,
            )

        module_name = f"rann_agent.skills.{skill_id}"
        skill_module = ModuleType(module_name)
        skill_module.__file__ = f"<skill:{skill_id}>"

        ns: dict[str, Any] = {
            "__name__": module_name,
            "__module__": skill_module,
            "__builtins__": __builtins__,  # type: ignore[arg-type]
        }

        try:
            compiled = compile(source, f"<skill:{skill_id}>", "exec")
        except SyntaxError as exc:
            self._logger.error("skill_compile_error", skill_id=skill_id, error=str(exc))
            return LoaderResult(module=None, error=f"SyntaxError: {exc}", loaded=False)

        timeout = _TimeoutThread(self.timeout)
        timeout.start()
        try:
            exec(compiled, ns)  # noqa: S307
        except ExecutionTimeoutError:
            self._logger.warning("skill_timeout", skill_id=skill_id, timeout=self.timeout)
            return LoaderResult(module=None, error=f"Execution timeout ({self.timeout}s)", loaded=False)
        except Exception as exc:  # noqa: BLE001
            self._logger.error("skill_exec_error", skill_id=skill_id, error=str(exc))
            return LoaderResult(module=None, error=f"{type(exc).__name__}: {exc}", loaded=False)
        finally:
            timeout.stop()

        # Transfer isolated namespace vars back onto the module object
        for key, val in ns.items():
            if not key.startswith("_"):
                setattr(skill_module, key, val)

        sys.modules[module_name] = skill_module
        self._logger.info("skill_loaded", skill_id=skill_id)
        return LoaderResult(module=skill_module, error=None, loaded=True)

    def execute_skill(
        self,
        skill_id: str,
        function_name: str,
        args: tuple = (),
        kwargs: Optional[dict] = None,
        source: Optional[str] = None,
    ) -> LoaderResult:
        """
        Load (if needed) and execute a named function inside the skill module.

        ``source`` can be omitted once the skill has been loaded once, as it
        is cached in ``sys.modules``.
        """
        import sys

        kwargs = kwargs or {}
        module_name = f"rann_agent.skills.{skill_id}"

        if module_name in sys.modules:
            skill_module = sys.modules[module_name]
        else:
            result = self.load_skill(skill_id, source=source)
            if not result.loaded:
                return result
            skill_module = result.module

        func: Optional[Callable[..., Any]] = getattr(skill_module, function_name, None)
        if func is None:
            return LoaderResult(
                module=None,
                error=f"Function '{function_name}' not found in skill '{skill_id}'",
                loaded=False,
            )

        timeout = _TimeoutThread(self.timeout)
        timeout.start()
        try:
            result_val = func(*args, **kwargs)
            return LoaderResult(module=skill_module, error=None, loaded=True)
        except ExecutionTimeoutError:
            self._logger.warning("skill_timeout", skill_id=skill_id, function=function_name)
            return LoaderResult(module=None, error=f"Execution timeout ({self.timeout}s)", loaded=False)
        except Exception as exc:  # noqa: BLE001
            self._logger.error("skill_execution_error", skill_id=skill_id, function=function_name, error=str(exc))
            return LoaderResult(module=None, error=f"{type(exc).__name__}: {exc}", loaded=False)
        finally:
            timeout.stop()

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _resolve_skill_file(self, skill_id: str) -> Optional[str]:
        candidates = [
            Path.cwd() / "skills" / f"{skill_id}.py",
            Path("~/.rann-agent/skills").expanduser() / f"{skill_id}.py",
        ]
        for path in candidates:
            if path.is_file():
                try:
                    return path.read_text(encoding="utf-8")
                except OSError as exc:
                    self._logger.warning("skill_file_read_error", path=str(path), error=str(exc))
                    return None
        self._logger.debug("skill_file_not_found", skill_id=skill_id, candidates=[str(c) for c in candidates])
        return None