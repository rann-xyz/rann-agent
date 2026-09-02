"""
Codebase understanding and context management.
Inspired by Cursor's codebase awareness.
"""

import os
import ast
from typing import Dict, Any, List, Optional
from pathlib import Path
import json


class CodebaseContext:
    """
    Understands entire codebase structure and context.
    Inspired by Cursor's codebase awareness.
    """
    
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.file_index = {}
        self.symbol_index = {}
        self.dependency_graph = {}
        self.context_cache = {}
    
    async def index_codebase(self, extensions: List[str] = None) -> Dict[str, Any]:
        """
        Index entire codebase for quick access.
        
        Args:
            extensions: File extensions to index (default: ['.py', '.js', '.ts'])
        """
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs']
        
        stats = {
            'total_files': 0,
            'total_lines': 0,
            'languages': {},
            'modules': []
        }
        
        for ext in extensions:
            for file_path in self.root_path.rglob(f'*{ext}'):
                if self._should_skip(file_path):
                    continue
                
                await self._index_file(file_path)
                stats['total_files'] += 1
                
                # Count lines
                try:
                    with open(file_path) as f:
                        lines = len(f.readlines())
                        stats['total_lines'] += lines
                except:
                    pass
                
                # Track languages
                lang = self._get_language(ext)
                stats['languages'][lang] = stats['languages'].get(lang, 0) + 1
        
        return stats
    
    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        skip_dirs = {
            'node_modules', '.git', '__pycache__', 'venv', 
            '.venv', 'dist', 'build', '.next', 'target'
        }
        
        return any(skip_dir in path.parts for skip_dir in skip_dirs)
    
    def _get_language(self, ext: str) -> str:
        """Get language from extension."""
        lang_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'React',
            '.tsx': 'React/TypeScript',
            '.go': 'Go',
            '.rs': 'Rust'
        }
        return lang_map.get(ext, 'Unknown')
    
    async def _index_file(self, file_path: Path):
        """Index a single file."""
        rel_path = str(file_path.relative_to(self.root_path))
        
        try:
            with open(file_path) as f:
                content = f.read()
            
            self.file_index[rel_path] = {
                'path': str(file_path),
                'size': len(content),
                'lines': len(content.split('\n'))
            }
            
            # Parse Python files for symbols
            if file_path.suffix == '.py':
                await self._parse_python(rel_path, content)
        
        except Exception as e:
            print(f"Failed to index {rel_path}: {e}")
    
    async def _parse_python(self, file_path: str, content: str):
        """Parse Python file for functions, classes, imports."""
        try:
            tree = ast.parse(content)
            
            symbols = {
                'functions': [],
                'classes': [],
                'imports': []
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    symbols['functions'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args]
                    })
                
                elif isinstance(node, ast.ClassDef):
                    symbols['classes'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': [
                            n.name for n in node.body 
                            if isinstance(n, ast.FunctionDef)
                        ]
                    })
                
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            symbols['imports'].append(alias.name)
                    elif node.module:
                        symbols['imports'].append(node.module)
            
            self.symbol_index[file_path] = symbols
        
        except SyntaxError:
            pass
    
    async def find_symbol(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Find where a symbol is defined."""
        results = []
        
        for file_path, symbols in self.symbol_index.items():
            # Check functions
            for func in symbols.get('functions', []):
                if func['name'] == symbol_name:
                    results.append({
                        'file': file_path,
                        'type': 'function',
                        'line': func['line'],
                        'info': func
                    })
            
            # Check classes
            for cls in symbols.get('classes', []):
                if cls['name'] == symbol_name:
                    results.append({
                        'file': file_path,
                        'type': 'class',
                        'line': cls['line'],
                        'info': cls
                    })
        
        return results
    
    async def get_file_context(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get context for a specific file."""
        if file_path in self.context_cache:
            return self.context_cache[file_path]
        
        if file_path not in self.symbol_index:
            return None
        
        symbols = self.symbol_index[file_path]
        file_info = self.file_index.get(file_path, {})
        
        context = {
            'file': file_path,
            'size': file_info.get('size', 0),
            'lines': file_info.get('lines', 0),
            'functions': [f['name'] for f in symbols.get('functions', [])],
            'classes': [c['name'] for c in symbols.get('classes', [])],
            'imports': symbols.get('imports', []),
            'symbols_count': len(symbols.get('functions', [])) + len(symbols.get('classes', []))
        }
        
        self.context_cache[file_path] = context
        return context
    
    async def get_related_files(self, file_path: str) -> List[str]:
        """Get files related to this file (imports, dependencies)."""
        related = set()
        
        if file_path in self.symbol_index:
            symbols = self.symbol_index[file_path]
            imports = symbols.get('imports', [])
            
            # Find files that match imports
            for imp in imports:
                for indexed_file in self.symbol_index.keys():
                    if imp in indexed_file or indexed_file.replace('/', '.').replace('.py', '') in imp:
                        related.add(indexed_file)
        
        return list(related)
    
    async def search_code(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search across codebase."""
        results = []
        query_lower = query.lower()
        
        # Search in symbol names
        for file_path, symbols in self.symbol_index.items():
            for func in symbols.get('functions', []):
                if query_lower in func['name'].lower():
                    results.append({
                        'file': file_path,
                        'type': 'function',
                        'name': func['name'],
                        'line': func['line']
                    })
            
            for cls in symbols.get('classes', []):
                if query_lower in cls['name'].lower():
                    results.append({
                        'file': file_path,
                        'type': 'class',
                        'name': cls['name'],
                        'line': cls['line']
                    })
        
        return results[:limit]
    
    async def get_codebase_summary(self) -> Dict[str, Any]:
        """Get high-level codebase summary."""
        total_files = len(self.file_index)
        total_symbols = sum(
            len(s.get('functions', [])) + len(s.get('classes', []))
            for s in self.symbol_index.values()
        )
        
        languages = {}
        for file_path in self.file_index.keys():
            ext = Path(file_path).suffix
            lang = self._get_language(ext)
            languages[lang] = languages.get(lang, 0) + 1
        
        return {
            'total_files': total_files,
            'total_symbols': total_symbols,
            'languages': languages,
            'indexed_files': len(self.symbol_index)
        }
