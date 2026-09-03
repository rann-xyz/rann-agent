"""
Semantic diff for RANN Agent.
As required by MASTER PROMPT Section 13.
"""

import ast
import difflib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import Enum
import structlog

logger = structlog.get_logger()


class ChangeType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class FunctionChange:
    name: str
    change_type: ChangeType
    line_range: Optional[Tuple[int, int]] = None
    signature_changed: bool = False
    body_changed: bool = False


@dataclass
class ClassChange:
    name: str
    change_type: ChangeType
    methods_added: List[str] = field(default_factory=list)
    methods_removed: List[str] = field(default_factory=list)
    methods_modified: List[str] = field(default_factory=list)
    base_classes_changed: bool = False


@dataclass
class ImportChange:
    change_type: ChangeType
    module: str
    names: List[str] = field(default_factory=list)


@dataclass
class SemanticDiffResult:
    before: str
    after: str
    function_changes: List[FunctionChange] = field(default_factory=list)
    class_changes: List[ClassChange] = field(default_factory=list)
    import_changes: List[ImportChange] = field(default_factory=list)
    config_changes: List[str] = field(default_factory=list)
    test_changes: List[str] = field(default_factory=list)
    line_diff: List[str] = field(default_factory=list)
    summary: str = ""

    @property
    def has_breaking_changes(self) -> bool:
        return any(
            c.change_type in (ChangeType.REMOVED, ChangeType.MODIFIED)
            for c in self.function_changes + self.class_changes
        )

    @property
    def files_changed(self) -> int:
        return 1  # Single file diff


class SemanticDiff:
    """AST-based semantic diff that understands code structure."""

    def diff(self, before: str, after: str) -> SemanticDiffResult:
        """Compute semantic diff between two code versions."""
        result = SemanticDiffResult(before=before, after=after)

        # Line-level diff
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        diff = list(difflib.unified_diff(before_lines, after_lines, lineterm=""))
        result.line_diff = diff

        # Parse ASTs
        try:
            before_ast = ast.parse(before)
            after_ast = ast.parse(after)
        except SyntaxError:
            result.summary = "Syntax error in before or after"
            return result

        # Function changes
        result.function_changes = self._diff_functions(before_ast, after_ast)

        # Class changes
        result.class_changes = self._diff_classes(before_ast, after_ast)

        # Import changes
        result.import_changes = self._diff_imports(before_ast, after_ast)

        # Config changes (assignment statements at module level)
        result.config_changes = self._diff_config(before_ast, after_ast)

        # Test changes (files with test_ or _test)
        result.test_changes = self._diff_tests(before, after)

        # Build summary
        summary_parts = []
        if result.function_changes:
            summary_parts.append(f"{len(result.function_changes)} function(s) changed")
        if result.class_changes:
            summary_parts.append(f"{len(result.class_changes)} class(es) changed")
        if result.import_changes:
            summary_parts.append(f"{len(result.import_changes)} import(s) changed")
        result.summary = ", ".join(summary_parts) if summary_parts else "No semantic changes"

        return result

    def _diff_functions(self, before: ast.AST, after: ast.AST) -> List[FunctionChange]:
        changes = []
        before_funcs = {n.name: n for n in ast.walk(before) if isinstance(n, ast.FunctionDef)}
        after_funcs = {n.name: n for n in ast.walk(after) if isinstance(n, ast.FunctionDef)}

        all_names = set(before_funcs.keys()) | set(after_funcs.keys())
        for name in all_names:
            b, a = before_funcs.get(name), after_funcs.get(name)
            if b and not a:
                changes.append(FunctionChange(name=name, change_type=ChangeType.REMOVED,
                    line_range=(b.lineno, b.end_lineno or b.lineno)))
            elif a and not b:
                changes.append(FunctionChange(name=name, change_type=ChangeType.ADDED,
                    line_range=(a.lineno, a.end_lineno or a.lineno)))
            elif b and a:
                sig_changed = self._signature_changed(b, a)
                body_changed = ast.unparse(b) != ast.unparse(a) if hasattr(ast, 'unparse') else b.body != a.body
                if sig_changed or body_changed:
                    changes.append(FunctionChange(
                        name=name, change_type=ChangeType.MODIFIED,
                        line_range=(a.lineno, a.end_lineno or a.lineno),
                        signature_changed=sig_changed, body_changed=body_changed
                    ))
        return changes

    def _diff_classes(self, before: ast.AST, after: ast.AST) -> List[ClassChange]:
        changes = []
        before_classes = {n.name: n for n in ast.walk(before) if isinstance(n, ast.ClassDef)}
        after_classes = {n.name: n for n in ast.walk(after) if isinstance(n, ast.ClassDef)}

        all_names = set(before_classes.keys()) | set(after_classes.keys())
        for name in all_names:
            b, a = before_classes.get(name), after_classes.get(name)
            if b and not a:
                changes.append(ClassChange(name=name, change_type=ChangeType.REMOVED))
            elif a and not b:
                changes.append(ClassChange(name=name, change_type=ChangeType.ADDED))
            elif b and a:
                b_methods = {n.name for n in b.body if isinstance(n, ast.FunctionDef)}
                a_methods = {n.name for n in a.body if isinstance(n, ast.FunctionDef)}
                ca = ClassChange(name=name, change_type=ChangeType.MODIFIED)
                ca.methods_added = list(a_methods - b_methods)
                ca.methods_removed = list(b_methods - a_methods)
                changes.append(ca)
        return changes

    def _diff_imports(self, before: ast.AST, after: ast.AST) -> List[ImportChange]:
        changes = []
        before_imports = self._collect_imports(before)
        after_imports = self._collect_imports(after)

        all_modules = set(before_imports.keys()) | set(after_imports.keys())
        for mod in all_modules:
            b_names = before_imports.get(mod, [])
            a_names = after_imports.get(mod, [])
            if b_names and not a_names:
                changes.append(ImportChange(change_type=ChangeType.REMOVED, module=mod, names=b_names))
            elif a_names and not b_names:
                changes.append(ImportChange(change_type=ChangeType.ADDED, module=mod, names=a_names))
            elif set(b_names) != set(a_names):
                changes.append(ImportChange(change_type=ChangeType.MODIFIED, module=mod,
                    names=list(set(a_names) - set(b_names))))
        return changes

    def _collect_imports(self, tree: ast.AST) -> Dict[str, List[str]]:
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.setdefault(alias.name, []).append(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.setdefault(node.module or "", []).append(alias.asname or alias.name)
        return imports

    def _diff_config(self, before: ast.AST, after: ast.AST) -> List[str]:
        """Detect module-level assignments (config changes)."""
        before_assigns = {n.targets[0].id for n in ast.walk(before)
                         if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
        after_assigns = {n.targets[0].id for n in ast.walk(after)
                        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
        return list(after_assigns - before_assigns)

    def _diff_tests(self, before: str, after: str) -> List[str]:
        """Detect test-related changes."""
        changes = []
        patterns = ["def test_", "class Test", "async def test_", "def _test"]
        for p in patterns:
            if p in before and p not in after:
                changes.append(f"Removed {p}")
            elif p not in before and p in after:
                changes.append(f"Added {p}")
        return changes

    def _signature_changed(self, b: ast.FunctionDef, a: ast.FunctionDef) -> bool:
        """Check if function signature (params) changed."""
        b_args = [(arg.arg, arg.annotation) for arg in b.args.args]
        a_args = [(arg.arg, arg.annotation) for arg in a.args.args]
        return b_args != a_args


@dataclass
class ImpactReport:
    impact_level: str  # low, medium, high, critical
    affected_functions: List[str]
    affected_classes: List[str]
    affected_files: List[str]
    cascade_risk: bool
    recommendation: str


class ImpactAnalyzer:
    """Analyze impact of changes on codebase."""

    def __init__(self, codebase_index: Optional[Dict[str, Any]] = None):
        self.codebase_index = codebase_index or {}

    def analyze(self, diff: SemanticDiffResult, callers: Optional[List[str]] = None) -> ImpactReport:
        """Analyze impact of a diff on callers."""
        affected_functions = [c.name for c in diff.function_changes if c.change_type == ChangeType.MODIFIED]
        affected_classes = [c.name for c in diff.class_changes if c.change_type == ChangeType.MODIFIED]

        # Determine impact level
        if diff.has_breaking_changes and callers:
            impact_level = "critical"
        elif diff.has_breaking_changes:
            impact_level = "high"
        elif diff.function_changes or diff.class_changes:
            impact_level = "medium"
        else:
            impact_level = "low"

        cascade_risk = len(affected_functions) > 5 or len(affected_classes) > 3

        if impact_level == "critical":
            recommendation = "Require full regression testing before merge"
        elif impact_level == "high":
            recommendation = "Run affected test suite before merge"
        elif impact_level == "medium":
            recommendation = "Review impact on callers before merge"
        else:
            recommendation = "Safe to merge"

        return ImpactReport(
            impact_level=impact_level,
            affected_functions=affected_functions,
            affected_classes=affected_classes,
            affected_files=["current_file"],
            cascade_risk=cascade_risk,
            recommendation=recommendation
        )