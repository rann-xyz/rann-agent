"""
MCTS (Monte Carlo Tree Search) for strategic planning.
"""

import math
import random
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MCTSNode:
    """MCTS tree node."""
    state: Any
    parent: Optional['MCTSNode'] = None
    children: List['MCTSNode'] = None
    visits: int = 0
    value: float = 0.0
    untried_actions: List[Any] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.untried_actions is None:
            self.untried_actions = []


class MCTSPlanner:
    """
    Monte Carlo Tree Search for planning and decision making.
    """
    
    def __init__(self, exploration_weight: float = 1.41):
        self.exploration_weight = exploration_weight
        self.root = None
    
    async def search(
        self,
        initial_state: Any,
        possible_actions: List[Any],
        iterations: int = 1000
    ) -> Any:
        """
        Perform MCTS to find best action.
        
        Args:
            initial_state: Starting state
            possible_actions: List of possible actions
            iterations: Number of search iterations
        """
        self.root = MCTSNode(
            state=initial_state,
            untried_actions=possible_actions.copy()
        )
        
        for _ in range(iterations):
            node = self._select(self.root)
            
            if node.untried_actions:
                node = self._expand(node)
            
            reward = await self._simulate(node)
            self._backpropagate(node, reward)
        
        # Return best child
        return self._best_child(self.root, 0).state
    
    def _select(self, node: MCTSNode) -> MCTSNode:
        """Select most promising node."""
        while not node.untried_actions and node.children:
            node = self._best_child(node, self.exploration_weight)
        return node
    
    def _expand(self, node: MCTSNode) -> MCTSNode:
        """Expand node with new child."""
        action = node.untried_actions.pop()
        child_state = self._apply_action(node.state, action)
        
        child = MCTSNode(state=child_state, parent=node)
        node.children.append(child)
        
        return child
    
    async def _simulate(self, node: MCTSNode) -> float:
        """Simulate random playthrough."""
        # Random simulation - can be replaced with heuristics
        return random.random()
    
    def _backpropagate(self, node: MCTSNode, reward: float):
        """Backpropagate reward up the tree."""
        while node is not None:
            node.visits += 1
            node.value += reward
            node = node.parent
    
    def _best_child(self, node: MCTSNode, c: float) -> MCTSNode:
        """Select best child using UCB1."""
        def ucb1(child: MCTSNode) -> float:
            if child.visits == 0:
                return float('inf')
            
            exploitation = child.value / child.visits
            exploration = c * math.sqrt(
                math.log(node.visits) / child.visits
            )
            
            return exploitation + exploration
        
        return max(node.children, key=ucb1)
    
    def _apply_action(self, state: Any, action: Any) -> Any:
        """Apply action to state (override for specific domains)."""
        return state
