"""
Autonomous coding agent - end-to-end development.
Inspired by Devin AI and Claude Code.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
import asyncio


class TaskStatus(Enum):
    """Development task status."""
    PLANNING = "planning"
    CODING = "coding"
    TESTING = "testing"
    DEBUGGING = "debugging"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DevelopmentTask:
    """Represents a development task."""
    task_id: str
    description: str
    requirements: List[str]
    status: TaskStatus = TaskStatus.PLANNING
    files_modified: List[str] = None
    tests_written: int = 0
    bugs_fixed: int = 0
    
    def __post_init__(self):
        if self.files_modified is None:
            self.files_modified = []


class AutonomousCoder:
    """
    Autonomous AI software engineer.
    Plans, codes, tests, debugs end-to-end.
    Inspired by Devin AI.
    """
    
    def __init__(self):
        self.current_task = None
        self.task_history = []
        self.workspace = {}
        self.test_results = []
    
    async def plan_implementation(
        self,
        task_description: str,
        requirements: List[str]
    ) -> Dict[str, Any]:
        """
        Plan how to implement a feature.
        
        Returns:
            Implementation plan with steps
        """
        plan = {
            'task': task_description,
            'requirements': requirements,
            'steps': [],
            'files_to_create': [],
            'files_to_modify': [],
            'tests_needed': []
        }
        
        # Analyze requirements
        for req in requirements:
            req_lower = req.lower()
            
            # Detect what needs to be done
            if 'api' in req_lower or 'endpoint' in req_lower:
                plan['steps'].append({
                    'step': 'Create API endpoint',
                    'description': req,
                    'estimated_time': '30 minutes'
                })
                plan['files_to_create'].append('api/endpoints.py')
                plan['tests_needed'].append('test_api.py')
            
            elif 'database' in req_lower or 'model' in req_lower:
                plan['steps'].append({
                    'step': 'Define database model',
                    'description': req,
                    'estimated_time': '20 minutes'
                })
                plan['files_to_create'].append('models/models.py')
                plan['tests_needed'].append('test_models.py')
            
            elif 'ui' in req_lower or 'frontend' in req_lower:
                plan['steps'].append({
                    'step': 'Build UI component',
                    'description': req,
                    'estimated_time': '45 minutes'
                })
                plan['files_to_create'].append('components/Component.tsx')
                plan['tests_needed'].append('Component.test.tsx')
            
            elif 'test' in req_lower:
                plan['steps'].append({
                    'step': 'Write tests',
                    'description': req,
                    'estimated_time': '25 minutes'
                })
            
            else:
                plan['steps'].append({
                    'step': 'Implement feature',
                    'description': req,
                    'estimated_time': '30 minutes'
                })
        
        # Add standard steps
        plan['steps'].extend([
            {
                'step': 'Write unit tests',
                'description': 'Ensure code coverage',
                'estimated_time': '20 minutes'
            },
            {
                'step': 'Run tests and debug',
                'description': 'Fix any issues',
                'estimated_time': '15 minutes'
            },
            {
                'step': 'Code review and refactor',
                'description': 'Optimize and clean',
                'estimated_time': '15 minutes'
            }
        ])
        
        return plan
    
    async def implement_feature(
        self,
        task_description: str,
        requirements: List[str]
    ) -> DevelopmentTask:
        """
        Autonomously implement a complete feature.
        
        Returns:
            Completed task with results
        """
        task = DevelopmentTask(
            task_id=f"task_{len(self.task_history)}",
            description=task_description,
            requirements=requirements
        )
        
        self.current_task = task
        
        try:
            # Step 1: Plan
            task.status = TaskStatus.PLANNING
            plan = await self.plan_implementation(task_description, requirements)
            
            # Step 2: Code
            task.status = TaskStatus.CODING
            for step in plan['steps']:
                if 'test' not in step['step'].lower():
                    # Simulate coding
                    await asyncio.sleep(0.1)
                    task.files_modified.append(f"file_{len(task.files_modified)}.py")
            
            # Step 3: Write tests
            task.status = TaskStatus.TESTING
            for test_file in plan['tests_needed']:
                task.tests_written += 1
                await asyncio.sleep(0.1)
            
            # Step 4: Debug if needed
            task.status = TaskStatus.DEBUGGING
            # Simulate finding and fixing bugs
            bugs_found = min(2, len(requirements))
            for _ in range(bugs_found):
                task.bugs_fixed += 1
                await asyncio.sleep(0.1)
            
            # Step 5: Review
            task.status = TaskStatus.REVIEWING
            await asyncio.sleep(0.1)
            
            # Complete
            task.status = TaskStatus.COMPLETED
            self.task_history.append(task)
            
            return task
        
        except Exception as e:
            task.status = TaskStatus.FAILED
            self.task_history.append(task)
            raise e
    
    async def debug_issue(
        self,
        error_message: str,
        stack_trace: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Autonomously debug an issue.
        
        Returns:
            Debug analysis and fix suggestions
        """
        analysis = {
            'error_type': self._classify_error(error_message),
            'root_cause': None,
            'fix_suggestions': [],
            'files_to_check': []
        }
        
        # Analyze error
        error_lower = error_message.lower()
        
        if 'nameerror' in error_lower or 'not defined' in error_lower:
            analysis['root_cause'] = 'Variable or function not defined'
            analysis['fix_suggestions'].append('Check if variable is imported or defined')
            analysis['fix_suggestions'].append('Verify spelling of variable name')
        
        elif 'typeerror' in error_lower:
            analysis['root_cause'] = 'Type mismatch or wrong arguments'
            analysis['fix_suggestions'].append('Check function signature')
            analysis['fix_suggestions'].append('Verify argument types')
        
        elif 'keyerror' in error_lower:
            analysis['root_cause'] = 'Dictionary key not found'
            analysis['fix_suggestions'].append('Use .get() method with default')
            analysis['fix_suggestions'].append('Check if key exists before accessing')
        
        elif 'importerror' in error_lower or 'modulenotfounderror' in error_lower:
            analysis['root_cause'] = 'Module not installed or not found'
            analysis['fix_suggestions'].append('Install missing package')
            analysis['fix_suggestions'].append('Check import path')
        
        elif 'attributeerror' in error_lower:
            analysis['root_cause'] = 'Attribute does not exist on object'
            analysis['fix_suggestions'].append('Check object type')
            analysis['fix_suggestions'].append('Verify attribute name')
        
        else:
            analysis['root_cause'] = 'Unknown error'
            analysis['fix_suggestions'].append('Review stack trace')
            analysis['fix_suggestions'].append('Add debug logging')
        
        # Extract files from stack trace
        import re
        files = re.findall(r'File "([^"]+)"', stack_trace)
        analysis['files_to_check'] = list(set(files))
        
        return analysis
    
    def _classify_error(self, error_message: str) -> str:
        """Classify error type."""
        error_lower = error_message.lower()
        
        if 'syntax' in error_lower:
            return 'SyntaxError'
        elif 'name' in error_lower:
            return 'NameError'
        elif 'type' in error_lower:
            return 'TypeError'
        elif 'value' in error_lower:
            return 'ValueError'
        elif 'key' in error_lower:
            return 'KeyError'
        elif 'import' in error_lower or 'module' in error_lower:
            return 'ImportError'
        elif 'attribute' in error_lower:
            return 'AttributeError'
        else:
            return 'UnknownError'
    
    async def write_tests(
        self,
        function_code: str,
        function_name: str
    ) -> str:
        """
        Automatically generate tests for a function.
        
        Returns:
            Test code
        """
        test_code = f'''import pytest
from module import {function_name}


def test_{function_name}_success():
    """Test successful execution."""
    result = {function_name}()
    assert result is not None


def test_{function_name}_edge_cases():
    """Test edge cases."""
    # Test with None
    with pytest.raises(ValueError):
        {function_name}(None)
    
    # Test with empty input
    result = {function_name}("")
    assert result == ""


def test_{function_name}_error_handling():
    """Test error handling."""
    with pytest.raises(Exception):
        {function_name}(invalid_input)
'''
        
        return test_code
    
    async def review_code(
        self,
        code: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Perform code review.
        
        Returns:
            Review with suggestions
        """
        review = {
            'quality_score': 0,
            'issues': [],
            'suggestions': [],
            'strengths': []
        }
        
        score = 100
        
        if language == 'python':
            # Check for docstrings
            if '"""' in code or "'''" in code:
                review['strengths'].append('Has docstrings')
            else:
                review['issues'].append('Missing docstrings')
                score -= 10
            
            # Check for type hints
            if '->' in code or ': str' in code or ': int' in code:
                review['strengths'].append('Uses type hints')
            else:
                review['suggestions'].append('Add type hints for better clarity')
                score -= 5
            
            # Check for error handling
            if 'try:' in code and 'except' in code:
                review['strengths'].append('Has error handling')
            else:
                review['suggestions'].append('Add error handling')
                score -= 10
            
            # Check line length
            long_lines = [l for l in code.split('\n') if len(l) > 100]
            if long_lines:
                review['issues'].append(f'{len(long_lines)} lines exceed 100 characters')
                score -= 5
        
        review['quality_score'] = max(0, score)
        
        return review
    
    async def get_task_summary(self) -> Dict[str, Any]:
        """Get summary of all tasks."""
        completed = sum(1 for t in self.task_history if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.task_history if t.status == TaskStatus.FAILED)
        
        return {
            'total_tasks': len(self.task_history),
            'completed': completed,
            'failed': failed,
            'success_rate': completed / len(self.task_history) if self.task_history else 0,
            'total_files_modified': sum(len(t.files_modified) for t in self.task_history),
            'total_tests_written': sum(t.tests_written for t in self.task_history),
            'total_bugs_fixed': sum(t.bugs_fixed for t in self.task_history)
        }
