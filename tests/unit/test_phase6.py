"""Unit tests for Phase 6: Skills (registry, loader, evaluator)"""

import pytest
import tempfile
import shutil
from rann_agent.skills.registry import SkillRegistry, SkillMetadata
from rann_agent.skills.loader import SkillLoader
from rann_agent.skills.evaluator import SkillEvaluator, TestCase


class TestSkillRegistry:
    def test_register_and_get(self):
        registry = SkillRegistry()
        meta = SkillMetadata(
            name="test_skill",
            description="A test",
            category="testing"
        )
        registry.register("test_skill", meta, "def run(): return 1")
        
        skill = registry.get("test_skill")
        assert skill is not None
        assert skill.name == "test_skill"
    
    def test_search(self):
        registry = SkillRegistry()
        registry.register(
            "analyze_code",
            SkillMetadata(name="analyze_code", description="Analyze code quality", category="dev"),
            "code"
        )
        
        results = registry.search("analyze")
        assert len(results) >= 1
    
    def test_list_enabled(self):
        registry = SkillRegistry()
        registry.register("s1", SkillMetadata(name="s1", description="", category="dev"), "code")
        registry.register("s2", SkillMetadata(name="s2", description="", category="dev"), "code")
        
        enabled = registry.list_enabled()
        assert len(enabled) >= 2
    
    def test_enable_disable(self):
        registry = SkillRegistry()
        registry.register("toggle_test", SkillMetadata(name="toggle_test", description="", category="test"), "code")
        
        registry.disable("toggle_test")
        disabled = registry.list_disabled()
        assert any(s.name == "toggle_test" for s in disabled)
        
        registry.enable("toggle_test")
        enabled = registry.list_enabled()
        assert any(s.name == "toggle_test" for s in enabled)


class TestSkillLoader:
    def test_load_simple_skill(self):
        loader = SkillLoader()
        code = "def run(x): return x * 2"
        
        result = loader.load_skill("double", code)
        assert result.loaded
        assert result.module is not None
        assert result.module.run(5) == 10
    
    def test_load_syntax_error(self):
        loader = SkillLoader()
        result = loader.load_skill("bad", "def run(): {")  # Invalid syntax
        assert result is not None
    
    def test_execute_skill(self):
        loader = SkillLoader()
        result = loader.execute_skill("test", "def run(): return 42")
        assert result is not None


class TestSkillEvaluator:
    def test_evaluate_success(self):
        ev = SkillEvaluator()
        code = "def run(a, b): return a + b"
        test_cases = [
            TestCase(name="add_positive", input={"a": 1, "b": 2}, expected=3),
            TestCase(name="add_zero", input={"a": 0, "b": 0}, expected=0),
        ]
        
        result = ev.evaluate_skill("test_add", code, test_cases)
        
        assert result.success_rate == 1.0
        assert result.passed_count == 2
    
    def test_evaluate_failure(self):
        ev = SkillEvaluator()
        code = "def run(a, b): return a - b"
        test_cases = [
            TestCase(name="add", input={"a": 1, "b": 2}, expected=3),
        ]
        
        result = ev.evaluate_skill("test_add", code, test_cases)
        
        assert result.success_rate == 0.0
        assert result.failed_count == 1
    
    def test_evaluate_syntax_error(self):
        ev = SkillEvaluator()
        code = "def run(a, b) return a + b"
        
        result = ev.evaluate_skill("test_broken", code, [])
        assert result.success_rate == 0.0