"""
Advanced Code Intelligence System
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Set, Optional
import structlog

logger = structlog.get_logger()


class CodeAnalyzer:
    """Advanced code analysis and understanding"""
    
    def __init__(self):
        self.patterns = {
            "code_smells": [
                (r"TODO|FIXME|HACK|XXX", "TODO comments"),
                (r"print\(", "Debug print statements"),
                (r"except:\s*pass", "Bare except with pass"),
                (r"eval\(|exec\(", "Dangerous eval/exec"),
                (r"import \*", "Wildcard imports"),
            ],
            "security": [
                (r"password\s*=\s*['\"]", "Hardcoded password"),
                (r"api[_-]?key\s*=\s*['\"]", "Hardcoded API key"),
                (r"SECRET\s*=\s*['\"]", "Hardcoded secret"),
                (r"md5|sha1", "Weak hashing algorithm"),
                (r"pickle\.loads?", "Unsafe pickle usage"),
            ],
        }
    
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Comprehensive file analysis"""
        try:
            content = file_path.read_text()
            
            # Parse AST
            tree = ast.parse(content)
            
            # Gather metrics
            metrics = self._calculate_metrics(tree, content)
            
            # Find issues
            issues = self._find_issues(content, file_path)
            
            # Analyze complexity
            complexity = self._calculate_complexity(tree)
            
            # Detect patterns
            patterns = self._detect_patterns(tree)
            
            return {
                "file": str(file_path),
                "metrics": metrics,
                "issues": issues,
                "complexity": complexity,
                "patterns": patterns,
                "health_score": self._calculate_health_score(issues, complexity),
            }
        
        except Exception as e:
            logger.error("analyze_file_failed", file=str(file_path), error=str(e))
            return {"file": str(file_path), "error": str(e)}
    
    def _calculate_metrics(self, tree: ast.AST, content: str) -> Dict[str, int]:
        """Calculate code metrics"""
        metrics = {
            "lines": len(content.splitlines()),
            "classes": 0,
            "functions": 0,
            "imports": 0,
            "comments": 0,
            "docstrings": 0,
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                metrics["classes"] += 1
            elif isinstance(node, ast.FunctionDef):
                metrics["functions"] += 1
            elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                metrics["imports"] += 1
        
        # Count comments
        metrics["comments"] = content.count("#")
        
        # Count docstrings
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                if ast.get_docstring(node):
                    metrics["docstrings"] += 1
        
        return metrics
    
    def _find_issues(self, content: str, file_path: Path) -> List[Dict]:
        """Find code issues and smells"""
        issues = []
        
        # Check patterns
        for category, patterns in self.patterns.items():
            for pattern, description in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    issues.append({
                        "category": category,
                        "type": description,
                        "line": line_num,
                        "snippet": content.split('\n')[line_num - 1].strip(),
                        "severity": "high" if category == "security" else "medium",
                    })
        
        return issues
    
    def _calculate_complexity(self, tree: ast.AST) -> Dict[str, Any]:
        """Calculate cyclomatic complexity"""
        complexities = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = self._function_complexity(node)
                complexities.append({
                    "function": node.name,
                    "complexity": complexity,
                    "line": node.lineno,
                    "rating": self._complexity_rating(complexity),
                })
        
        return {
            "functions": complexities,
            "average": sum(c["complexity"] for c in complexities) / len(complexities) if complexities else 0,
            "max": max((c["complexity"] for c in complexities), default=0),
        }
    
    def _function_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity for a function"""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            # Decision points increase complexity
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _complexity_rating(self, complexity: int) -> str:
        """Rate complexity level"""
        if complexity <= 5:
            return "low"
        elif complexity <= 10:
            return "medium"
        elif complexity <= 20:
            return "high"
        else:
            return "very_high"
    
    def _detect_patterns(self, tree: ast.AST) -> Dict[str, List[str]]:
        """Detect design patterns and anti-patterns"""
        patterns = {
            "design_patterns": [],
            "anti_patterns": [],
        }
        
        # Detect singleton pattern
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check for singleton indicators
                has_instance = any(
                    isinstance(n, ast.Name) and n.id == "_instance"
                    for n in ast.walk(node)
                )
                if has_instance:
                    patterns["design_patterns"].append(f"Singleton: {node.name}")
                
                # Check for god class (too many methods)
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                if len(methods) > 20:
                    patterns["anti_patterns"].append(f"God Class: {node.name} ({len(methods)} methods)")
        
        return patterns
    
    def _calculate_health_score(self, issues: List[Dict], complexity: Dict) -> float:
        """Calculate overall code health score (0-100)"""
        score = 100.0
        
        # Deduct for issues
        for issue in issues:
            if issue["severity"] == "high":
                score -= 5
            elif issue["severity"] == "medium":
                score -= 2
            else:
                score -= 1
        
        # Deduct for high complexity
        avg_complexity = complexity.get("average", 0)
        if avg_complexity > 10:
            score -= (avg_complexity - 10) * 2
        
        return max(0, min(100, score))


class CodeGenerator:
    """Intelligent code generation"""
    
    def __init__(self, analyzer: CodeAnalyzer):
        self.analyzer = analyzer
    
    def generate_tests(self, file_path: Path) -> str:
        """Generate unit tests for a file"""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
            
            tests = []
            tests.append('import pytest')
            tests.append('from unittest.mock import Mock, patch\n')
            tests.append(f'from {file_path.stem} import *\n\n')
            
            # Generate test for each function
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
                    test = self._generate_function_test(node)
                    tests.append(test)
            
            return '\n'.join(tests)
        
        except Exception as e:
            logger.error("generate_tests_failed", error=str(e))
            return f"# Error generating tests: {e}"
    
    def _generate_function_test(self, node: ast.FunctionDef) -> str:
        """Generate test for a function"""
        func_name = node.name
        args = [arg.arg for arg in node.args.args if arg.arg != 'self']
        
        test = f"""
def test_{func_name}_success():
    \"\"\"Test {func_name} with valid inputs\"\"\"
    # Arrange
    {self._generate_mock_args(args)}
    
    # Act
    result = {func_name}({', '.join(args)})
    
    # Assert
    assert result is not None
    # TODO: Add more specific assertions


def test_{func_name}_error_handling():
    \"\"\"Test {func_name} error handling\"\"\"
    # TODO: Test edge cases and error conditions
    pass
"""
        return test
    
    def _generate_mock_args(self, args: List[str]) -> str:
        """Generate mock arguments"""
        mocks = []
        for arg in args:
            if 'id' in arg.lower():
                mocks.append(f"{arg} = 1")
            elif 'name' in arg.lower():
                mocks.append(f'{arg} = "test"')
            elif 'data' in arg.lower():
                mocks.append(f"{arg} = {{}}")
            else:
                mocks.append(f"{arg} = None")
        
        return '\n    '.join(mocks)
    
    def generate_docstring(self, node: ast.FunctionDef) -> str:
        """Generate docstring for a function"""
        args = node.args.args
        
        docstring = f'"""\n    {node.name}\n\n'
        
        if args:
            docstring += "    Args:\n"
            for arg in args:
                if arg.arg != 'self':
                    docstring += f"        {arg.arg}: Description of {arg.arg}\n"
        
        # Check if function has return
        has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))
        if has_return:
            docstring += "\n    Returns:\n"
            docstring += "        Description of return value\n"
        
        docstring += '    """'
        return docstring
    
    def suggest_refactoring(self, file_path: Path) -> List[str]:
        """Suggest refactoring improvements"""
        suggestions = []
        
        analysis = self.analyzer.analyze_file(file_path)
        
        # Check complexity
        for func in analysis.get("complexity", {}).get("functions", []):
            if func["complexity"] > 10:
                suggestions.append(
                    f"Refactor {func['function']}() - complexity {func['complexity']} is too high. "
                    f"Consider breaking into smaller functions."
                )
        
        # Check issues
        for issue in analysis.get("issues", []):
            if issue["severity"] == "high":
                suggestions.append(
                    f"Fix {issue['type']} at line {issue['line']}: {issue['snippet']}"
                )
        
        # Check metrics
        metrics = analysis.get("metrics", {})
        if metrics.get("lines", 0) > 500:
            suggestions.append(
                f"File has {metrics['lines']} lines - consider splitting into multiple files"
            )
        
        if metrics.get("functions", 0) > 20:
            suggestions.append(
                f"File has {metrics['functions']} functions - consider organizing into classes"
            )
        
        return suggestions
