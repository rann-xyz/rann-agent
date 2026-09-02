"""
Semantic memory - stores facts, concepts, and knowledge.
"""

from typing import Dict, List, Any, Optional


class SemanticMemory:
    """Stores factual knowledge and concepts."""
    
    def __init__(self):
        self.facts = {}
        self.concepts = {}
        self.relationships = []
    
    async def add_fact(self, key: str, value: Any, category: str = "general"):
        """Store a fact."""
        self.facts[key] = {
            'value': value,
            'category': category,
            'confidence': 1.0
        }
    
    async def get_fact(self, key: str) -> Optional[Any]:
        """Retrieve a fact."""
        return self.facts.get(key, {}).get('value')
    
    async def add_concept(self, name: str, definition: str, attributes: Dict = None):
        """Store a concept."""
        self.concepts[name] = {
            'definition': definition,
            'attributes': attributes or {}
        }
    
    async def link(self, entity1: str, relationship: str, entity2: str):
        """Create relationship between entities."""
        self.relationships.append({
            'from': entity1,
            'relationship': relationship,
            'to': entity2
        })
    
    async def query(self, category: str = None) -> Dict:
        """Query semantic memory."""
        if category:
            return {k: v for k, v in self.facts.items() 
                   if v.get('category') == category}
        return self.facts
