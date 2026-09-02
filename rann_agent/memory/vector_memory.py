"""
Vector-based memory system with RAG capabilities.
Uses ChromaDB for efficient similarity search and retrieval.
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import json


class VectorMemory:
    """
    Long-term memory using vector embeddings.
    Enables semantic search and retrieval-augmented generation.
    """
    
    def __init__(self, collection_name: str = "agent_memory"):
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self.embeddings_cache = {}
        
    async def initialize(self):
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Use persistent storage
            self.client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory="./.chroma_db"
            ))
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Agent long-term memory"}
            )
            
            return True
        except ImportError:
            print("ChromaDB not installed. Install with: pip install chromadb")
            return False
        except Exception as e:
            print(f"Failed to initialize vector memory: {e}")
            return False
    
    async def store(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        category: str = "general"
    ) -> str:
        """
        Store information in vector memory.
        
        Args:
            content: Text content to store
            metadata: Additional metadata
            category: Category/type of memory
            
        Returns:
            Memory ID
        """
        if not self.collection:
            await self.initialize()
        
        # Generate unique ID
        memory_id = hashlib.sha256(
            f"{content}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Prepare metadata
        meta = {
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "source": "agent"
        }
        if metadata:
            meta.update(metadata)
        
        # Store in collection
        try:
            self.collection.add(
                documents=[content],
                metadatas=[meta],
                ids=[memory_id]
            )
            return memory_id
        except Exception as e:
            print(f"Failed to store memory: {e}")
            return ""
    
    async def retrieve(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories based on semantic similarity.
        
        Args:
            query: Search query
            n_results: Number of results to return
            category: Filter by category
            
        Returns:
            List of relevant memories with metadata
        """
        if not self.collection:
            await self.initialize()
        
        try:
            # Build where clause
            where = {}
            if category:
                where["category"] = category
            
            # Query collection
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where if where else None
            )
            
            # Format results
            memories = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    memories.append({
                        'id': results['ids'][0][i],
                        'content': doc,
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if 'distances' in results else None
                    })
            
            return memories
        except Exception as e:
            print(f"Failed to retrieve memories: {e}")
            return []
    
    async def update(self, memory_id: str, content: str, metadata: Optional[Dict] = None):
        """Update existing memory."""
        if not self.collection:
            await self.initialize()
        
        try:
            meta = metadata or {}
            meta['updated_at'] = datetime.now().isoformat()
            
            self.collection.update(
                ids=[memory_id],
                documents=[content],
                metadatas=[meta]
            )
            return True
        except Exception as e:
            print(f"Failed to update memory: {e}")
            return False
    
    async def delete(self, memory_id: str):
        """Delete memory by ID."""
        if not self.collection:
            await self.initialize()
        
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            print(f"Failed to delete memory: {e}")
            return False
    
    async def search_by_metadata(
        self,
        filters: Dict[str, Any],
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search memories by metadata filters."""
        if not self.collection:
            await self.initialize()
        
        try:
            results = self.collection.get(
                where=filters,
                limit=n_results
            )
            
            memories = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents']):
                    memories.append({
                        'id': results['ids'][i],
                        'content': doc,
                        'metadata': results['metadatas'][i]
                    })
            
            return memories
        except Exception as e:
            print(f"Failed to search by metadata: {e}")
            return []
    
    async def get_recent(self, n_results: int = 10, category: Optional[str] = None) -> List[Dict]:
        """Get most recent memories."""
        if not self.collection:
            await self.initialize()
        
        try:
            where = {"category": category} if category else None
            results = self.collection.get(
                where=where,
                limit=n_results
            )
            
            memories = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents']):
                    memories.append({
                        'id': results['ids'][i],
                        'content': doc,
                        'metadata': results['metadatas'][i]
                    })
            
            # Sort by timestamp
            memories.sort(
                key=lambda x: x['metadata'].get('timestamp', ''),
                reverse=True
            )
            
            return memories
        except Exception as e:
            print(f"Failed to get recent memories: {e}")
            return []
    
    async def clear(self, category: Optional[str] = None):
        """Clear all memories or specific category."""
        if not self.collection:
            await self.initialize()
        
        try:
            if category:
                # Delete by category
                results = self.collection.get(where={"category": category})
                if results and results['ids']:
                    self.collection.delete(ids=results['ids'])
            else:
                # Clear entire collection
                self.client.delete_collection(self.collection_name)
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Agent long-term memory"}
                )
            return True
        except Exception as e:
            print(f"Failed to clear memories: {e}")
            return False
    
    async def summarize_context(self, query: str, max_tokens: int = 2000) -> str:
        """
        Retrieve and summarize relevant context for a query.
        Used for RAG (Retrieval-Augmented Generation).
        """
        memories = await self.retrieve(query, n_results=10)
        
        if not memories:
            return ""
        
        # Build context
        context_parts = []
        total_length = 0
        
        for mem in memories:
            content = mem['content']
            length = len(content.split())
            
            if total_length + length > max_tokens:
                break
            
            context_parts.append(f"[{mem['metadata'].get('category', 'general')}] {content}")
            total_length += length
        
        return "\n\n".join(context_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        if not self.collection:
            return {}
        
        try:
            count = self.collection.count()
            return {
                "total_memories": count,
                "collection_name": self.collection_name
            }
        except Exception as e:
            print(f"Failed to get stats: {e}")
            return {}
