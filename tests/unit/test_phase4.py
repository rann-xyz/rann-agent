"""Unit tests for Phase 4: Memory modules (working, procedural)"""

import pytest
import tempfile
import shutil
from rann_agent.memory.working import WorkingMemory, WorkingMemoryItem
from rann_agent.memory.procedural import ProceduralMemory, Skill


class TestWorkingMemory:
    def test_store_and_recall(self):
        wm = WorkingMemory()
        wm.store("key1", "value1")
        assert wm.recall("key1") == "value1"
    
    def test_recall_missing(self):
        wm = WorkingMemory()
        assert wm.recall("nonexistent") is None
    
    def test_access_count(self):
        wm = WorkingMemory()
        wm.store("key1", "value1")
        wm.recall("key1")
        wm.recall("key1")
        item = wm._items["key1"]
        assert item.access_count == 2
    
    def test_forget(self):
        wm = WorkingMemory()
        wm.store("key1", "value1")
        assert wm.forget("key1")
        assert wm.recall("key1") is None
    
    def test_update(self):
        wm = WorkingMemory()
        wm.store("key1", "old")
        assert wm.update("key1", "new")
        assert wm.recall("key1") == "new"
    
    def test_lru_eviction(self):
        wm = WorkingMemory(max_items=2)
        wm.store("a", "1")
        wm.store("b", "2")
        wm.store("c", "3")  # Should evict 'a'
        
        assert wm.recall("a") is None
        assert wm.recall("b") == "2"
        assert wm.recall("c") == "3"
    
    def test_clear(self):
        wm = WorkingMemory()
        wm.store("a", "1")
        wm.store("b", "2")
        wm.clear()
        assert len(wm.keys()) == 0
    
    def test_search(self):
        wm = WorkingMemory()
        wm.store("animal_cat", "A cat")
        wm.store("animal_dog", "A dog")
        wm.store("plant_tree", "A tree")
        
        results = wm.search("cat")
        assert len(results) == 1
        assert results[0] == "A cat"
    
    def test_stats(self):
        wm = WorkingMemory()
        wm.store("a", "1")
        wm.recall("a")
        
        stats = wm.stats()
        assert stats["total_items"] == 1
        assert stats["max_items"] == 1000


class TestProceduralMemory:
    def test_builtin_skills(self):
        pm = ProceduralMemory()
        skills = list(pm._skills.values())
        assert len(skills) >= 4
        assert any(s.skill_id == "code_review" for s in skills)
    
    def test_store_and_get(self):
        pm = ProceduralMemory()
        skill = Skill(
            skill_id="test_skill",
            name="Test",
            description="A test skill",
            category="testing",
            code="print('test')"
        )
        pm.store(skill)
        
        retrieved = pm.get("test_skill")
        assert retrieved is not None
        assert retrieved.name == "Test"
    
    def test_search(self):
        pm = ProceduralMemory()
        results = pm.search("code")
        
        assert len(results) >= 1
        assert any(s.skill_id == "code_review" for s in results)
    
    def test_search_by_category(self):
        pm = ProceduralMemory()
        results = pm.search("review", category="development")
        
        assert len(results) >= 1
    
    def test_get_by_category(self):
        pm = ProceduralMemory()
        dev_skills = pm.get_by_category("development")
        
        assert len(dev_skills) >= 2
    
    def test_record_execution(self):
        pm = ProceduralMemory()
        pm.record_execution("code_review", success=True, execution_time_ms=100)
        pm.record_execution("code_review", success=True, execution_time_ms=200)
        pm.record_execution("code_review", success=False, execution_time_ms=50)
        
        skill = pm.get("code_review")
        assert skill.success_count == 2
        assert skill.failure_count == 1
        # Average: (100 + 200 + 50) / 3 = 116.67
        assert abs(skill.avg_execution_time_ms - 116.67) < 0.1
    
    def test_get_best_skill(self):
        pm = ProceduralMemory()
        # Add a skill with more successes
        pm.record_execution("code_review", success=True, execution_time_ms=100)
        pm.record_execution("code_review", success=True, execution_time_ms=100)
        
        best = pm.get_best_skill("review code")
        assert best is not None
        assert best.skill_id == "code_review"
    
    def test_persistence(self):
        tmpdir = tempfile.mkdtemp()
        try:
            pm = ProceduralMemory(storage_path=tmpdir)
            skill = Skill(
                skill_id="persist_test",
                name="Persist",
                description="Test persistence",
                category="test",
                code="x = 1"
            )
            pm.store(skill)
            
            # Load new instance
            pm2 = ProceduralMemory(storage_path=tmpdir)
            retrieved = pm2.get("persist_test")
            assert retrieved is not None
            assert retrieved.name == "Persist"
        finally:
            shutil.rmtree(tmpdir)