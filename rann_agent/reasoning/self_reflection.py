"""
Self-reflection and critique system.
"""

from typing import List, Dict, Any
from datetime import datetime


class SelfReflection:
    """
    Enables agent to reflect on its actions and learn.
    """
    
    def __init__(self):
        self.reflections = []
        self.critiques = []
    
    async def reflect(
        self,
        action: str,
        outcome: str,
        success: bool,
        lessons_learned: List[str] = None
    ) -> Dict:
        """Reflect on an action and its outcome."""
        reflection = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'outcome': outcome,
            'success': success,
            'lessons_learned': lessons_learned or [],
            'confidence': self._calculate_confidence(success)
        }
        
        self.reflections.append(reflection)
        return reflection
    
    async def critique(self, output: str, criteria: List[str]) -> Dict:
        """Critique own output against criteria."""
        critique = {
            'timestamp': datetime.now().isoformat(),
            'output': output,
            'criteria': criteria,
            'issues': [],
            'improvements': []
        }
        
        # Analyze against criteria
        for criterion in criteria:
            if not self._meets_criterion(output, criterion):
                critique['issues'].append(f"Does not meet: {criterion}")
                critique['improvements'].append(
                    f"Improve to meet: {criterion}"
                )
        
        self.critiques.append(critique)
        return critique
    
    def _calculate_confidence(self, success: bool) -> float:
        """Calculate confidence based on past success rate."""
        if not self.reflections:
            return 0.5
        
        recent = self.reflections[-10:]
        successes = sum(1 for r in recent if r['success'])
        return successes / len(recent)
    
    def _meets_criterion(self, output: str, criterion: str) -> bool:
        """Simple criterion check (can be enhanced)."""
        # Basic checks
        if 'complete' in criterion.lower():
            return len(output) > 100
        if 'concise' in criterion.lower():
            return len(output) < 1000
        return True
    
    async def get_insights(self) -> Dict[str, Any]:
        """Get insights from reflections."""
        if not self.reflections:
            return {}
        
        total = len(self.reflections)
        successes = sum(1 for r in self.reflections if r['success'])
        
        return {
            'total_reflections': total,
            'success_rate': successes / total if total > 0 else 0,
            'recent_confidence': self._calculate_confidence(True),
            'common_lessons': self._extract_common_lessons()
        }
    
    def _extract_common_lessons(self) -> List[str]:
        """Extract most common lessons learned."""
        all_lessons = []
        for r in self.reflections:
            all_lessons.extend(r.get('lessons_learned', []))
        
        # Count occurrences
        lesson_counts = {}
        for lesson in all_lessons:
            lesson_counts[lesson] = lesson_counts.get(lesson, 0) + 1
        
        # Return top 5
        sorted_lessons = sorted(
            lesson_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [lesson for lesson, count in sorted_lessons[:5]]
