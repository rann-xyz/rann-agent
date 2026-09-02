"""
Real-time code completion and suggestions.
Inspired by GitHub Copilot and Cursor.
"""

from typing import List, Dict, Any, Optional
import re


class CodeCompletion:
    """
    AI-powered code completion and suggestions.
    Inspired by GitHub Copilot.
    """
    
    def __init__(self):
        self.context_window = []
        self.completion_cache = {}
    
    async def suggest_completion(
        self,
        code_before: str,
        code_after: str = "",
        language: str = "python",
        max_suggestions: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Suggest code completions based on context.
        
        Args:
            code_before: Code before cursor
            code_after: Code after cursor
            language: Programming language
            max_suggestions: Max number of suggestions
        """
        suggestions = []
        
        # Detect context
        context = self._analyze_context(code_before, language)
        
        # Generate suggestions based on context
        if context['type'] == 'function_definition':
            suggestions.extend(self._suggest_function_body(context, language))
        
        elif context['type'] == 'import':
            suggestions.extend(self._suggest_imports(context, language))
        
        elif context['type'] == 'variable_assignment':
            suggestions.extend(self._suggest_variable_value(context, language))
        
        elif context['type'] == 'control_flow':
            suggestions.extend(self._suggest_control_flow(context, language))
        
        else:
            # General suggestions
            suggestions.extend(self._suggest_general(code_before, language))
        
        return suggestions[:max_suggestions]
    
    def _analyze_context(self, code: str, language: str) -> Dict[str, Any]:
        """Analyze code context to determine what to suggest."""
        lines = code.strip().split('\n')
        last_line = lines[-1] if lines else ""
        
        context = {
            'type': 'general',
            'language': language,
            'last_line': last_line,
            'indentation': len(last_line) - len(last_line.lstrip())
        }
        
        # Python-specific detection
        if language == 'python':
            if re.match(r'^\s*def\s+\w+\(.*\):', last_line):
                context['type'] = 'function_definition'
                context['function_name'] = re.search(r'def\s+(\w+)', last_line).group(1)
            
            elif re.match(r'^\s*(from|import)\s+', last_line):
                context['type'] = 'import'
            
            elif re.match(r'^\s*\w+\s*=', last_line):
                context['type'] = 'variable_assignment'
            
            elif re.match(r'^\s*(if|for|while|try|with)\s+', last_line):
                context['type'] = 'control_flow'
                context['keyword'] = re.match(r'^\s*(\w+)', last_line).group(1)
        
        return context
    
    def _suggest_function_body(
        self,
        context: Dict[str, Any],
        language: str
    ) -> List[Dict[str, Any]]:
        """Suggest function body implementation."""
        suggestions = []
        indent = ' ' * (context['indentation'] + 4)
        
        if language == 'python':
            # Common patterns
            suggestions.append({
                'code': f'\n{indent}"""Function docstring."""\n{indent}pass',
                'description': 'Function with docstring',
                'confidence': 0.8
            })
            
            suggestions.append({
                'code': f'\n{indent}try:\n{indent}    pass\n{indent}except Exception as e:\n{indent}    print(f"Error: {{e}}")',
                'description': 'Try-except block',
                'confidence': 0.6
            })
        
        return suggestions
    
    def _suggest_imports(
        self,
        context: Dict[str, Any],
        language: str
    ) -> List[Dict[str, Any]]:
        """Suggest import statements."""
        suggestions = []
        
        if language == 'python':
            common_imports = [
                'from typing import Dict, List, Any, Optional',
                'import asyncio',
                'import json',
                'from datetime import datetime',
                'import os',
                'from pathlib import Path'
            ]
            
            for imp in common_imports[:3]:
                suggestions.append({
                    'code': imp,
                    'description': 'Common import',
                    'confidence': 0.7
                })
        
        return suggestions
    
    def _suggest_variable_value(
        self,
        context: Dict[str, Any],
        language: str
    ) -> List[Dict[str, Any]]:
        """Suggest variable values."""
        suggestions = []
        
        # Detect variable name pattern
        last_line = context['last_line']
        var_name = re.search(r'(\w+)\s*=', last_line)
        
        if var_name:
            name = var_name.group(1).lower()
            
            # Suggest based on name
            if 'path' in name or 'dir' in name:
                suggestions.append({
                    'code': ' Path(".")',
                    'description': 'Path object',
                    'confidence': 0.7
                })
            
            elif 'config' in name or 'settings' in name:
                suggestions.append({
                    'code': ' {}',
                    'description': 'Empty dict for config',
                    'confidence': 0.7
                })
            
            elif 'list' in name or 'items' in name:
                suggestions.append({
                    'code': ' []',
                    'description': 'Empty list',
                    'confidence': 0.7
                })
        
        return suggestions
    
    def _suggest_control_flow(
        self,
        context: Dict[str, Any],
        language: str
    ) -> List[Dict[str, Any]]:
        """Suggest control flow body."""
        suggestions = []
        indent = ' ' * (context['indentation'] + 4)
        keyword = context.get('keyword', '')
        
        if keyword == 'if':
            suggestions.append({
                'code': f'\n{indent}pass',
                'description': 'If body',
                'confidence': 0.8
            })
        
        elif keyword == 'for':
            suggestions.append({
                'code': f'\n{indent}pass',
                'description': 'For loop body',
                'confidence': 0.8
            })
        
        elif keyword == 'try':
            suggestions.append({
                'code': f'\n{indent}pass\nexcept Exception as e:\n{indent}print(f"Error: {{e}}")',
                'description': 'Try-except',
                'confidence': 0.9
            })
        
        return suggestions
    
    def _suggest_general(
        self,
        code: str,
        language: str
    ) -> List[Dict[str, Any]]:
        """General purpose suggestions."""
        suggestions = []
        
        # Pattern-based suggestions
        if 'async' in code:
            suggestions.append({
                'code': 'await ',
                'description': 'Await async call',
                'confidence': 0.6
            })
        
        if 'def ' in code and 'return' not in code:
            suggestions.append({
                'code': 'return ',
                'description': 'Return statement',
                'confidence': 0.5
            })
        
        return suggestions
    
    async def suggest_refactoring(
        self,
        code: str,
        language: str = "python"
    ) -> List[Dict[str, Any]]:
        """Suggest code refactoring improvements."""
        suggestions = []
        
        if language == 'python':
            lines = code.split('\n')
            
            # Detect long functions
            func_lines = 0
            in_function = False
            
            for line in lines:
                if re.match(r'^\s*def\s+', line):
                    in_function = True
                    func_lines = 0
                elif in_function:
                    if line.strip() and not line.strip().startswith('#'):
                        func_lines += 1
                    if func_lines > 50:
                        suggestions.append({
                            'type': 'refactor',
                            'description': 'Function is too long (50+ lines), consider splitting',
                            'severity': 'warning'
                        })
                        break
            
            # Detect repeated code
            if code.count('try:') > 3:
                suggestions.append({
                    'type': 'refactor',
                    'description': 'Multiple try-except blocks, consider error handling decorator',
                    'severity': 'info'
                })
            
            # Suggest type hints
            if 'def ' in code and '->' not in code and 'typing' not in code:
                suggestions.append({
                    'type': 'refactor',
                    'description': 'Add type hints for better code clarity',
                    'severity': 'info'
                })
        
        return suggestions
    
    async def explain_code(self, code: str, language: str = "python") -> str:
        """Generate explanation of code."""
        lines = code.split('\n')
        
        explanations = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Detect patterns
            if re.match(r'def\s+\w+', line):
                func_name = re.search(r'def\s+(\w+)', line).group(1)
                explanations.append(f"Defines function '{func_name}'")
            
            elif re.match(r'class\s+\w+', line):
                class_name = re.search(r'class\s+(\w+)', line).group(1)
                explanations.append(f"Defines class '{class_name}'")
            
            elif re.match(r'(from|import)\s+', line):
                explanations.append("Imports dependencies")
            
            elif '=' in line and not line.startswith('if'):
                var = line.split('=')[0].strip()
                explanations.append(f"Assigns value to '{var}'")
        
        return '\n'.join(explanations) if explanations else "Code snippet"
