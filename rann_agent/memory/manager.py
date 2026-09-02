"""
Memory management - persistent context and learned patterns
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import sqlite3
from datetime import datetime
import structlog

logger = structlog.get_logger()


class MemoryManager:
    """
    Manages persistent memory across sessions
    """
    
    def __init__(self, config):
        self.config = config
        
        # Setup database
        db_path = Path(config.database_url.replace("sqlite:///", "")).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self._init_database()
        
        logger.info("memory_manager_init", db=str(db_path))
    
    def _init_database(self):
        """Initialize SQLite database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    goal TEXT,
                    result TEXT,
                    turns INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_resolutions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error TEXT,
                    fix TEXT,
                    success BOOLEAN,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT,
                    pattern TEXT,
                    metadata TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    async def save_session(
        self,
        session_id: str,
        goal: str,
        result: Dict[str, Any],
        turns: int
    ):
        """Save session to memory"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO sessions (id, goal, result, turns) VALUES (?, ?, ?, ?)",
                    (session_id, goal, json.dumps(result), turns)
                )
                conn.commit()
            
            logger.info("session_saved", session_id=session_id)
        
        except Exception as e:
            logger.error("save_session_error", error=str(e))
    
    async def get_relevant_context(self, goal: str, limit: int = 3) -> str:
        """Get relevant past sessions for context"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Simple keyword matching (could use vector search)
                keywords = goal.lower().split()[:5]
                
                query = """
                    SELECT id, goal, result
                    FROM sessions
                    WHERE """ + " OR ".join(["LOWER(goal) LIKE ?" for _ in keywords]) + """
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                
                params = [f"%{kw}%" for kw in keywords] + [limit]
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                if not rows:
                    return ""
                
                context = "Relevant past sessions:\n\n"
                for session_id, past_goal, result_json in rows:
                    result = json.loads(result_json)
                    context += f"- {past_goal[:100]}\n  Result: {result.get('output', '')[:200]}\n\n"
                
                return context
        
        except Exception as e:
            logger.error("get_context_error", error=str(e))
            return ""
    
    async def save_error_resolution(self, error: str, fix: Dict[str, Any]):
        """Save successful error resolution"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO error_resolutions (error, fix, success) VALUES (?, ?, ?)",
                    (error, json.dumps(fix), True)
                )
                conn.commit()
            
            logger.info("error_resolution_saved", error=error[:100])
        
        except Exception as e:
            logger.error("save_error_resolution_error", error=str(e))
    
    async def search_similar_errors(self, error: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search for similar past errors and their fixes"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Simple keyword matching
                keywords = error.lower().split()[:5]
                
                query = """
                    SELECT error, fix
                    FROM error_resolutions
                    WHERE success = 1 AND (""" + " OR ".join(["LOWER(error) LIKE ?" for _ in keywords]) + """)
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                
                params = [f"%{kw}%" for kw in keywords] + [limit]
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [
                    {"error": row[0], "fix": json.loads(row[1])}
                    for row in rows
                ]
        
        except Exception as e:
            logger.error("search_errors_error", error=str(e))
            return []
    
    async def save_pattern(self, pattern_type: str, pattern: str, metadata: Dict[str, Any]):
        """Save learned pattern"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO learned_patterns (pattern_type, pattern, metadata) VALUES (?, ?, ?)",
                    (pattern_type, pattern, json.dumps(metadata))
                )
                conn.commit()
            
            logger.info("pattern_saved", type=pattern_type)
        
        except Exception as e:
            logger.error("save_pattern_error", error=str(e))
    
    def get_stats(self) -> Dict[str, int]:
        """Get memory statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                stats = {}
                
                cursor = conn.execute("SELECT COUNT(*) FROM sessions")
                stats["sessions"] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM error_resolutions WHERE success = 1")
                stats["successful_fixes"] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM learned_patterns")
                stats["patterns"] = cursor.fetchone()[0]
                
                return stats
        
        except Exception as e:
            logger.error("get_stats_error", error=str(e))
            return {}
