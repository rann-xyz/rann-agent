"""
Advanced reasoning capabilities using Chain-of-Thought and Tree-of-Thought.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json


@dataclass
class ThoughtNode:
    """Represents a single thought in reasoning tree."""
    content: str
    parent: Optional['ThoughtNode'] = None
    children: List['ThoughtNode'] = None
    score: float = 0.0
    depth: int = 0
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class ChainOfThought:
    """
    Chain-of-Thought reasoning - sequential step-by-step thinking.
    """
    
    def __init__(self):
        self.steps = []
        self.current_step = 0
    
    async def add_step(self, thought: str, reasoning: str):
        """Add reasoning step."""
        self.steps.append({
            'step': len(self.steps) + 1,
            'thought': thought,
            'reasoning': reasoning
        })
    
    async def get_chain(self) -> List[Dict]:
        """Get full reasoning chain."""
        return self.steps
    
    async def to_prompt(self) -> str:
        """Convert to prompt format."""
        prompt = "Let's think step by step:\n\n"
        for step in self.steps:
            prompt += f"Step {step['step']}: {step['thought']}\n"
            prompt += f"Reasoning: {step['reasoning']}\n\n"
        return prompt


class TreeOfThought:
    """
    Tree-of-Thought reasoning - explores multiple reasoning paths.
    """
    
    def __init__(self, max_depth: int = 5, branching_factor: int = 3):
        self.root = None
        self.max_depth = max_depth
        self.branching_factor = branching_factor
        self.all_nodes = []
    
    async def create_root(self, content: str) -> ThoughtNode:
        """Create root thought."""
        self.root = ThoughtNode(content=content, depth=0)
        self.all_nodes.append(self.root)
        return self.root
    
    async def expand_node(self, node: ThoughtNode, thoughts: List[str]) -> List[ThoughtNode]:
        """Expand a node with child thoughts."""
        if node.depth >= self.max_depth:
            return []
        
        children = []
        for thought in thoughts[:self.branching_factor]:
            child = ThoughtNode(
                content=thought,
                parent=node,
                depth=node.depth + 1
            )
            node.children.append(child)
            self.all_nodes.append(child)
            children.append(child)
        
        return children
    
    async def evaluate_node(self, node: ThoughtNode, score: float):
        """Assign score to a thought node."""
        node.score = score
    
    async def get_best_path(self) -> List[ThoughtNode]:
        """Get path with highest cumulative score."""
        if not self.root:
            return []
        
        def path_score(node: ThoughtNode) -> float:
            score = node.score
            current = node.parent
            while current:
                score += current.score
                current = current.parent
            return score
        
        # Find leaf with best score
        leaves = [n for n in self.all_nodes if not n.children]
        if not leaves:
            return [self.root]
        
        best_leaf = max(leaves, key=path_score)
        
        # Build path
        path = []
        current = best_leaf
        while current:
            path.insert(0, current)
            current = current.parent
        
        return path
    
    async def to_tree_structure(self) -> Dict:
        """Convert to tree structure."""
        def node_to_dict(node: ThoughtNode) -> Dict:
            return {
                'content': node.content,
                'score': node.score,
                'depth': node.depth,
                'children': [node_to_dict(c) for c in node.children]
            }
        
        if not self.root:
            return {}
        
        return node_to_dict(self.root)
