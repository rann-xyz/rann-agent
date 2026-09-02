"""
Session search and conversation history management.
Search past conversations with FTS5 full-text search.
"""

import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class SessionSearch:
    """
    Full-text search over conversation history.
    Enables cross-session recall and learning.
    """
    
    def __init__(self, db_path: str = "./.sessions.db"):
        self.db_path = db_path
        self.conn = None
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize SQLite database with FTS5."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Create sessions table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """)
        
        # Create messages table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        # Create FTS5 virtual table for full-text search
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts 
            USING fts5(
                session_id,
                role,
                content,
                timestamp
            )
        """)
        
        self.conn.commit()
    
    async def add_session(
        self,
        session_id: str,
        title: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Create a new session."""
        try:
            now = datetime.now().isoformat()
            self.conn.execute("""
                INSERT INTO sessions (id, title, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, title, now, now, json.dumps(metadata or {})))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Failed to add session: {e}")
            return False
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> bool:
        """Add a message to session and FTS index."""
        try:
            timestamp = datetime.now().isoformat()
            
            # Add to messages table
            cursor = self.conn.execute("""
                INSERT INTO messages (session_id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
            """, (session_id, role, content, timestamp))
            
            # Add to FTS index
            self.conn.execute("""
                INSERT INTO messages_fts (session_id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
            """, (session_id, role, content, timestamp))
            
            # Update session updated_at
            self.conn.execute("""
                UPDATE sessions SET updated_at = ? WHERE id = ?
            """, (timestamp, session_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Failed to add message: {e}")
            return False
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Full-text search across all messages.
        
        Args:
            query: Search query
            limit: Max results
            session_id: Optional filter by session
        """
        try:
            if session_id:
                cursor = self.conn.execute("""
                    SELECT m.*, s.title as session_title
                    FROM messages_fts m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE messages_fts MATCH ? AND m.session_id = ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, session_id, limit))
            else:
                cursor = self.conn.execute("""
                    SELECT m.*, s.title as session_title
                    FROM messages_fts m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE messages_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'session_id': row['session_id'],
                    'session_title': row['session_title'],
                    'role': row['role'],
                    'content': row['content'],
                    'timestamp': row['timestamp']
                })
            
            return results
        except Exception as e:
            print(f"Search failed: {e}")
            return []
    
    async def get_session_history(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all messages from a session."""
        try:
            cursor = self.conn.execute("""
                SELECT role, content, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'role': row['role'],
                    'content': row['content'],
                    'timestamp': row['timestamp']
                })
            
            return results
        except Exception as e:
            print(f"Failed to get history: {e}")
            return []
    
    async def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent sessions."""
        try:
            cursor = self.conn.execute("""
                SELECT id, title, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    'id': row['id'],
                    'title': row['title'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })
            
            return sessions
        except Exception as e:
            print(f"Failed to list sessions: {e}")
            return []
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages."""
        try:
            self.conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self.conn.execute("DELETE FROM messages_fts WHERE session_id = ?", (session_id,))
            self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Failed to delete session: {e}")
            return False
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
