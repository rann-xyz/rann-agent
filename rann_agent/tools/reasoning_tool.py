"""
Reasoning tools - CoT, ToT, Self-Reflection, MCTS.
"""

from typing import Dict, Any, List
from ..reasoning.thought_process import ChainOfThought, TreeOfThought
from ..reasoning.self_reflection import SelfReflection
from ..reasoning.mcts_planner import MCTSPlanner


class ReasoningTool:
    """Advanced reasoning capabilities."""
    
    name = "reasoning"
    description = "Advanced reasoning with CoT, ToT, Self-Reflection, MCTS"
    
    def __init__(self):
        self.cot = ChainOfThought()
        self.tot = TreeOfThought()
        self.reflection = SelfReflection()
        self.mcts = MCTSPlanner()
    
    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        Execute reasoning operations.
        
        Actions:
            - chain_of_thought: Step-by-step reasoning
            - tree_of_thought: Explore multiple reasoning paths
            - reflect: Reflect on action and outcome
            - critique: Critique output against criteria
            - plan_mcts: Plan using Monte Carlo Tree Search
        """
        if action == "chain_of_thought":
            thought = kwargs.get("thought", "")
            reasoning = kwargs.get("reasoning", "")
            await self.cot.add_step(thought, reasoning)
            chain = await self.cot.get_chain()
            return {"success": True, "chain": chain}
        
        elif action == "tree_of_thought":
            root_content = kwargs.get("root", "")
            if not self.tot.root:
                await self.tot.create_root(root_content)
            
            best_path = await self.tot.get_best_path()
            return {
                "success": True,
                "best_path": [node.content for node in best_path]
            }
        
        elif action == "reflect":
            action_taken = kwargs.get("action", "")
            outcome = kwargs.get("outcome", "")
            success = kwargs.get("success", True)
            lessons = kwargs.get("lessons_learned", [])
            
            reflection = await self.reflection.reflect(
                action_taken, outcome, success, lessons
            )
            return {"success": True, "reflection": reflection}
        
        elif action == "critique":
            output = kwargs.get("output", "")
            criteria = kwargs.get("criteria", [])
            
            critique = await self.reflection.critique(output, criteria)
            return {"success": True, "critique": critique}
        
        elif action == "plan_mcts":
            initial_state = kwargs.get("initial_state")
            actions = kwargs.get("possible_actions", [])
            iterations = kwargs.get("iterations", 1000)
            
            best_action = await self.mcts.search(
                initial_state, actions, iterations
            )
            return {"success": True, "best_action": best_action}
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
