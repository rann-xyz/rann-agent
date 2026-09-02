"""
Advanced code intelligence tool
"""

from typing import Dict, Any
from pathlib import Path
import structlog

from rann_agent.tools.registry import Tool, ToolResult
from rann_agent.intelligence.code_intelligence import CodeAnalyzer, CodeGenerator

logger = structlog.get_logger()


class CodeIntelligenceTool(Tool):
    """Advanced code analysis and generation"""
    
    name = "code_intelligence"
    description = "Analyze code, detect issues, generate tests, suggest refactoring"
    parameters = {
        "action": {"type": "string", "required": True},  # analyze | generate_tests | suggest_refactor | generate_docs
        "path": {"type": "string", "required": True},
        "options": {"type": "object", "default": {}},
    }
    
    def __init__(self, config):
        self.config = config
        self.analyzer = CodeAnalyzer()
        self.generator = CodeGenerator(self.analyzer)
    
    async def execute(self, action: str, path: str, options: dict = None, **kwargs) -> Dict[str, Any]:
        """Execute code intelligence action"""
        
        file_path = Path(path).expanduser().resolve()
        
        if not file_path.exists():
            return ToolResult(
                tool=self.name,
                success=False,
                error=f"File not found: {path}"
            ).to_dict()
        
        try:
            if action == "analyze":
                return await self._analyze_code(file_path, options or {})
            
            elif action == "generate_tests":
                return await self._generate_tests(file_path)
            
            elif action == "suggest_refactor":
                return await self._suggest_refactoring(file_path)
            
            elif action == "generate_docs":
                return await self._generate_documentation(file_path)
            
            else:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Unknown action: {action}"
                ).to_dict()
        
        except Exception as e:
            logger.error("code_intelligence_error", action=action, error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()
    
    async def _analyze_code(self, file_path: Path, options: dict) -> Dict[str, Any]:
        """Analyze code file"""
        analysis = self.analyzer.analyze_file(file_path)
        
        # Format output
        output = self._format_analysis(analysis)
        
        return ToolResult(
            tool=self.name,
            success=True,
            output=output,
            metadata=analysis
        ).to_dict()
    
    def _format_analysis(self, analysis: Dict) -> str:
        """Format analysis results"""
        lines = []
        
        lines.append(f"📊 Code Analysis: {analysis['file']}")
        lines.append("=" * 60)
        
        # Health score
        health = analysis.get("health_score", 0)
        emoji = "🟢" if health >= 80 else "🟡" if health >= 60 else "🔴"
        lines.append(f"\n{emoji} Health Score: {health:.1f}/100")
        
        # Metrics
        metrics = analysis.get("metrics", {})
        lines.append(f"\n📈 Metrics:")
        lines.append(f"  Lines: {metrics.get('lines', 0)}")
        lines.append(f"  Functions: {metrics.get('functions', 0)}")
        lines.append(f"  Classes: {metrics.get('classes', 0)}")
        lines.append(f"  Comments: {metrics.get('comments', 0)}")
        lines.append(f"  Docstrings: {metrics.get('docstrings', 0)}")
        
        # Complexity
        complexity = analysis.get("complexity", {})
        lines.append(f"\n🔄 Complexity:")
        lines.append(f"  Average: {complexity.get('average', 0):.1f}")
        lines.append(f"  Max: {complexity.get('max', 0)}")
        
        # High complexity functions
        high_complexity = [
            f for f in complexity.get("functions", [])
            if f["complexity"] > 10
        ]
        if high_complexity:
            lines.append(f"\n  ⚠️  High complexity functions:")
            for func in high_complexity[:5]:
                lines.append(f"    • {func['function']}() - complexity {func['complexity']}")
        
        # Issues
        issues = analysis.get("issues", [])
        if issues:
            lines.append(f"\n⚠️  Issues Found: {len(issues)}")
            
            # Group by category
            by_category = {}
            for issue in issues:
                cat = issue["category"]
                by_category.setdefault(cat, []).append(issue)
            
            for category, cat_issues in by_category.items():
                lines.append(f"\n  {category.upper()}:")
                for issue in cat_issues[:5]:
                    lines.append(f"    Line {issue['line']}: {issue['type']}")
                    lines.append(f"      → {issue['snippet']}")
        
        # Patterns
        patterns = analysis.get("patterns", {})
        if patterns.get("design_patterns"):
            lines.append(f"\n✨ Design Patterns:")
            for pattern in patterns["design_patterns"]:
                lines.append(f"  • {pattern}")
        
        if patterns.get("anti_patterns"):
            lines.append(f"\n❌ Anti-Patterns:")
            for pattern in patterns["anti_patterns"]:
                lines.append(f"  • {pattern}")
        
        return "\n".join(lines)
    
    async def _generate_tests(self, file_path: Path) -> Dict[str, Any]:
        """Generate unit tests"""
        tests = self.generator.generate_tests(file_path)
        
        return ToolResult(
            tool=self.name,
            success=True,
            output=f"Generated tests:\n\n{tests}",
            metadata={"test_file": f"test_{file_path.name}"}
        ).to_dict()
    
    async def _suggest_refactoring(self, file_path: Path) -> Dict[str, Any]:
        """Suggest refactoring improvements"""
        suggestions = self.generator.suggest_refactoring(file_path)
        
        output = "💡 Refactoring Suggestions:\n\n"
        if suggestions:
            for i, suggestion in enumerate(suggestions, 1):
                output += f"{i}. {suggestion}\n"
        else:
            output += "✅ No refactoring needed - code looks good!"
        
        return ToolResult(
            tool=self.name,
            success=True,
            output=output,
            metadata={"suggestions": suggestions}
        ).to_dict()
    
    async def _generate_documentation(self, file_path: Path) -> Dict[str, Any]:
        """Generate documentation"""
        # TODO: Implement comprehensive doc generation
        return ToolResult(
            tool=self.name,
            success=True,
            output="Documentation generation coming soon!"
        ).to_dict()
