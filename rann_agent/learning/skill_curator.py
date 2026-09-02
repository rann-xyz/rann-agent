"""
Skill curator - autonomous skill creation and improvement.
Agent creates skills from experience and improves them during use.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class SkillCurator:
    """
    Manages autonomous skill creation and improvement.
    Agent creates skills after complex tasks and improves them during use.
    """
    
    def __init__(self, skills_dir: str = "./skills"):
        self.skills_dir = skills_dir
        self.skills = {}
        self.skill_usage = {}
    
    async def should_create_skill(self, task_complexity: int, steps_count: int) -> bool:
        """
        Determine if a task warrants skill creation.
        
        Args:
            task_complexity: Complexity score (1-10)
            steps_count: Number of steps taken
        """
        # Create skill if complex (5+) or many steps (5+)
        return task_complexity >= 5 or steps_count >= 5
    
    async def create_skill_from_experience(
        self,
        task_name: str,
        task_description: str,
        steps: List[str],
        outcome: str,
        lessons_learned: List[str] = None
    ) -> str:
        """
        Automatically create a skill from completed task.
        
        Args:
            task_name: Name of the task
            task_description: What the task does
            steps: Steps taken to complete
            outcome: Result of the task
            lessons_learned: Important lessons
        """
        skill_id = f"skill_{task_name.lower().replace(' ', '_')}"
        
        skill = {
            'id': skill_id,
            'name': task_name,
            'description': task_description,
            'steps': steps,
            'outcome': outcome,
            'lessons_learned': lessons_learned or [],
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'usage_count': 0,
            'success_count': 0,
            'version': 1
        }
        
        self.skills[skill_id] = skill
        self.skill_usage[skill_id] = []
        
        return skill_id
    
    async def use_skill(
        self,
        skill_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use a skill and track its usage.
        
        Returns:
            Skill steps and metadata
        """
        if skill_id not in self.skills:
            return {'error': 'Skill not found'}
        
        skill = self.skills[skill_id]
        skill['usage_count'] += 1
        
        # Track usage
        usage = {
            'timestamp': datetime.now().isoformat(),
            'context': context,
            'success': None  # To be updated later
        }
        self.skill_usage[skill_id].append(usage)
        
        return {
            'skill_id': skill_id,
            'name': skill['name'],
            'steps': skill['steps'],
            'lessons_learned': skill['lessons_learned']
        }
    
    async def record_skill_outcome(
        self,
        skill_id: str,
        success: bool,
        feedback: Optional[str] = None
    ):
        """Record outcome of skill usage."""
        if skill_id not in self.skills:
            return
        
        skill = self.skills[skill_id]
        
        if success:
            skill['success_count'] += 1
        
        # Update latest usage record
        if skill_id in self.skill_usage and self.skill_usage[skill_id]:
            self.skill_usage[skill_id][-1]['success'] = success
            self.skill_usage[skill_id][-1]['feedback'] = feedback
    
    async def improve_skill(
        self,
        skill_id: str,
        new_steps: List[str] = None,
        new_lessons: List[str] = None
    ) -> bool:
        """
        Improve a skill based on usage experience.
        
        Args:
            skill_id: Skill to improve
            new_steps: Updated steps
            new_lessons: New lessons learned
        """
        if skill_id not in self.skills:
            return False
        
        skill = self.skills[skill_id]
        
        if new_steps:
            skill['steps'] = new_steps
        
        if new_lessons:
            skill['lessons_learned'].extend(new_lessons)
            # Remove duplicates
            skill['lessons_learned'] = list(set(skill['lessons_learned']))
        
        skill['version'] += 1
        skill['updated_at'] = datetime.now().isoformat()
        
        return True
    
    async def analyze_skill_performance(self, skill_id: str) -> Dict[str, Any]:
        """Analyze how well a skill performs."""
        if skill_id not in self.skills:
            return {}
        
        skill = self.skills[skill_id]
        usage_history = self.skill_usage.get(skill_id, [])
        
        total_uses = skill['usage_count']
        successes = skill['success_count']
        success_rate = successes / total_uses if total_uses > 0 else 0
        
        # Find common failure patterns
        failures = [u for u in usage_history if u.get('success') is False]
        
        return {
            'skill_id': skill_id,
            'name': skill['name'],
            'total_uses': total_uses,
            'success_count': successes,
            'success_rate': success_rate,
            'version': skill['version'],
            'failure_count': len(failures),
            'needs_improvement': success_rate < 0.8
        }
    
    async def suggest_skill_improvements(self, skill_id: str) -> List[str]:
        """Suggest improvements based on usage patterns."""
        analysis = await self.analyze_skill_performance(skill_id)
        
        suggestions = []
        
        if analysis.get('success_rate', 1.0) < 0.8:
            suggestions.append("Success rate is low - review and update steps")
        
        if analysis.get('total_uses', 0) > 10:
            suggestions.append("Highly used skill - consider optimizing steps")
        
        usage_history = self.skill_usage.get(skill_id, [])
        failures = [u for u in usage_history if u.get('success') is False]
        
        if len(failures) > 3:
            suggestions.append("Multiple failures detected - add error handling steps")
        
        return suggestions
    
    async def list_skills(self) -> List[Dict[str, Any]]:
        """List all skills with stats."""
        skills_list = []
        
        for skill_id, skill in self.skills.items():
            analysis = await self.analyze_skill_performance(skill_id)
            
            skills_list.append({
                'id': skill_id,
                'name': skill['name'],
                'description': skill['description'],
                'usage_count': skill['usage_count'],
                'success_rate': analysis.get('success_rate', 0),
                'version': skill['version'],
                'created_at': skill['created_at'],
                'updated_at': skill['updated_at']
            })
        
        return skills_list
    
    async def export_skill(self, skill_id: str) -> Optional[str]:
        """Export skill as markdown."""
        if skill_id not in self.skills:
            return None
        
        skill = self.skills[skill_id]
        
        markdown = f"""# {skill['name']}

**Description:** {skill['description']}

**Version:** {skill['version']}
**Created:** {skill['created_at']}
**Updated:** {skill['updated_at']}

## Steps

"""
        for i, step in enumerate(skill['steps'], 1):
            markdown += f"{i}. {step}\n"
        
        if skill['lessons_learned']:
            markdown += "\n## Lessons Learned\n\n"
            for lesson in skill['lessons_learned']:
                markdown += f"- {lesson}\n"
        
        markdown += f"\n## Performance\n\n"
        markdown += f"- Usage count: {skill['usage_count']}\n"
        markdown += f"- Success count: {skill['success_count']}\n"
        
        return markdown
