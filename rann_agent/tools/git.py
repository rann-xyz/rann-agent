"""
Git operations tool
"""

from typing import Dict, Any
import structlog

from rann_agent.tools.registry import Tool, ToolResult

logger = structlog.get_logger()


class GitTool(Tool):
    """Git operations"""
    
    name = "git"
    description = "Git version control operations"
    parameters = {
        "action": {"type": "string", "required": True},  # status | add | commit | push | pull | diff
        "files": {"type": "array", "default": []},
        "message": {"type": "string", "default": ""},
        "branch": {"type": "string", "default": None},
        "workdir": {"type": "string", "default": "."},
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, action: str, files: list = None, message: str = "", branch: str = None, workdir: str = ".", **kwargs) -> Dict[str, Any]:
        """Execute git command"""
        try:
            import subprocess
            
            if action == "status":
                cmd = "git status --short"
            
            elif action == "add":
                if not files:
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error="No files specified for git add"
                    ).to_dict()
                cmd = f"git add {' '.join(files)}"
            
            elif action == "commit":
                if not message:
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error="No commit message specified"
                    ).to_dict()
                cmd = f'git commit -m "{message}"'
            
            elif action == "push":
                branch_arg = f" {branch}" if branch else ""
                cmd = f"git push{branch_arg}"
            
            elif action == "pull":
                cmd = "git pull"
            
            elif action == "diff":
                files_arg = " " + " ".join(files) if files else ""
                cmd = f"git diff{files_arg}"
            
            elif action == "log":
                cmd = "git log --oneline -10"
            
            elif action == "branch":
                if branch:
                    cmd = f"git checkout -b {branch}"
                else:
                    cmd = "git branch"
            
            else:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Unknown git action: {action}"
                ).to_dict()
            
            # Execute
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=workdir,
                timeout=30
            )
            
            return ToolResult(
                tool=self.name,
                success=result.returncode == 0,
                output=result.stdout if result.returncode == 0 else result.stderr,
                error=result.stderr if result.returncode != 0 else None,
                metadata={"action": action, "exit_code": result.returncode}
            ).to_dict()
            
        except Exception as e:
            logger.error("git_error", action=action, error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()
