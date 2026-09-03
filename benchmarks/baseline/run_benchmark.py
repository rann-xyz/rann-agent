"""
RANN Agent Baseline Benchmark

Captures current state metrics before refactoring.
All future changes must be compared against this baseline.
"""

import asyncio
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rann_agent.core.agent import Agent
from rann_agent.core.config import Config
from rann_agent.tools.registry import ToolRegistry


class BenchmarkMetrics:
    def __init__(self):
        self.metrics = {
            "timestamp": datetime.now().isoformat(),
            "task_success": [],
            "first_attempt_success": [],
            "tool_success": {},
            "test_success": 0,
            "test_total": 0,
            "recovery_success": 0,
            "recovery_attempts": 0,
            "latency": [],
            "token_usage": {"input": 0, "output": 0},
            "model_calls": 0,
            "tool_calls": 0,
            "failure_rate": 0,
            "regression_count": 0,
        }
    
    def record_task(self, success: bool, first_attempt: bool, latency: float):
        self.metrics["task_success"].append(success)
        self.metrics["first_attempt_success"].append(first_attempt)
        self.metrics["latency"].append(latency)
    
    def record_tool_call(self, tool_name: str, success: bool, latency: float):
        if tool_name not in self.metrics["tool_success"]:
            self.metrics["tool_success"][tool_name] = {"success": 0, "failure": 0, "latency": []}
        if success:
            self.metrics["tool_success"][tool_name]["success"] += 1
        else:
            self.metrics["tool_success"][tool_name]["failure"] += 1
        self.metrics["tool_success"][tool_name]["latency"].append(latency)
        self.metrics["tool_calls"] += 1
    
    def record_model_call(self, input_tokens: int, output_tokens: int):
        self.metrics["token_usage"]["input"] += input_tokens
        self.metrics["token_usage"]["output"] += output_tokens
        self.metrics["model_calls"] += 1
    
    def record_recovery(self, success: bool):
        self.metrics["recovery_attempts"] += 1
        if success:
            self.metrics["recovery_success"] += 1
    
    def finalize(self):
        total = len(self.metrics["task_success"])
        if total > 0:
            self.metrics["task_success_rate"] = sum(self.metrics["task_success"]) / total
            self.metrics["first_attempt_rate"] = sum(self.metrics["first_attempt_success"]) / total
            self.metrics["avg_latency"] = sum(self.metrics["latency"]) / total
        else:
            self.metrics["task_success_rate"] = 0
            self.metrics["first_attempt_rate"] = 0
            self.metrics["avg_latency"] = 0
        
        self.metrics["failure_rate"] = 1 - self.metrics["task_success_rate"]
        
        # Tool success rates
        for tool, data in self.metrics["tool_success"].items():
            total_calls = data["success"] + data["failure"]
            if total_calls > 0:
                data["success_rate"] = data["success"] / total_calls
                data["avg_latency"] = sum(data["latency"]) / len(data["latency"])
            del data["latency"]  # Remove raw latencies from summary
        
        return self.metrics


async def benchmark_simple_task():
    """Benchmark: Simple file creation task"""
    from unittest.mock import Mock, AsyncMock, patch
    
    metrics = {}
    start = time.time()
    
    try:
        mock_llm = Mock()
        mock_llm.complete = AsyncMock(return_value={
            "content": "Created file successfully",
            "usage": {"input_tokens": 50, "output_tokens": 30},
        })
        mock_llm.complete_with_retry = mock_llm.complete
        mock_llm.stream = AsyncMock(return_value=iter(["test"]))
        
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm):
            agent = Agent()
            agent.llm = mock_llm
            
            mock_llm.complete_with_retry = AsyncMock(return_value={
                "content": "Task completed",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            })
            
            result = await agent.execute("Create a test file", max_turns=1)
            
            metrics = {
                "success": result is not None,
                "first_attempt": True,
                "latency": time.time() - start,
                "model_calls": 1,
                "tool_calls": 0,
            }
    except Exception as e:
        metrics = {
            "success": False,
            "first_attempt": False,
            "latency": time.time() - start,
            "error": str(e),
        }
    
    return metrics


async def benchmark_tool_execution():
    """Benchmark: Individual tool execution"""
    from rann_agent.tools.terminal import TerminalTool
    from rann_agent.tools.files import FileReadTool, FileWriteTool
    
    results = {}
    config = Config()
    
    # Terminal tool
    tool = TerminalTool(config)
    start = time.time()
    try:
        result = await tool.execute(command="echo 'test'")
        results["terminal"] = {
            "success": result.get("success", False),
            "latency": time.time() - start,
        }
    except Exception as e:
        results["terminal"] = {"success": False, "error": str(e), "latency": time.time() - start}
    
    # Read file tool
    tool = FileReadTool(config)
    start = time.time()
    try:
        result = await tool.execute(path="/etc/hostname")
        results["read_file"] = {
            "success": result.get("success", False),
            "latency": time.time() - start,
        }
    except Exception as e:
        results["read_file"] = {"success": False, "error": str(e), "latency": time.time() - start}
    
    return results


async def run_baseline_benchmark():
    """Run full baseline benchmark suite"""
    print("=" * 60)
    print("RANN AGENT BASELINE BENCHMARK")
    print("=" * 60)
    
    benchmark = BenchmarkMetrics()
    results = {
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "python_version": sys.version,
            "platform": sys.platform,
        },
        "simple_task": None,
        "tool_execution": {},
        "summary": {},
    }
    
    # 1. Simple task benchmark
    print("\n[1/3] Running simple task benchmark...")
    task_result = await benchmark_simple_task()
    results["simple_task"] = task_result
    benchmark.record_task(task_result["success"], task_result["first_attempt"], task_result["latency"])
    
    # 2. Tool execution benchmark
    print("[2/3] Running tool execution benchmarks...")
    tool_results = await benchmark_tool_execution()
    results["tool_execution"] = tool_results
    for tool_name, data in tool_results.items():
        benchmark.record_tool_call(tool_name, data["success"], data.get("latency", 0))
    
    # 3. Test suite
    print("[3/3] Running test suite...")
    import subprocess
    test_result = subprocess.run(
        ["python", "-m", "pytest", "tests/", "-v", "--tb=no", "-q"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )
    results["test_suite"] = {
        "exit_code": test_result.returncode,
        "passed": test_result.stdout.count(" passed"),
    }
    
    # Finalize
    summary = benchmark.finalize()
    results["summary"] = summary
    
    # Save results
    output_dir = Path(__file__).parent
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / "baseline_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    with open(output_dir / "baseline_summary.txt", "w") as f:
        f.write("RANN AGENT BASELINE BENCHMARK SUMMARY\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Timestamp: {summary['timestamp']}\n")
        f.write(f"Task Success Rate: {summary.get('task_success_rate', 0):.1%}\n")
        f.write(f"First Attempt Rate: {summary.get('first_attempt_rate', 0):.1%}\n")
        f.write(f"Average Latency: {summary.get('avg_latency', 0):.2f}s\n")
        f.write(f"Model Calls: {summary['model_calls']}\n")
        f.write(f"Tool Calls: {summary['tool_calls']}\n")
        f.write(f"Token Usage: {summary['token_usage']}\n")
        f.write(f"Failure Rate: {summary.get('failure_rate', 0):.1%}\n\n")
        f.write("Tool Success Rates:\n")
        for tool, data in summary.get("tool_success", {}).items():
            f.write(f"  {tool}: {data.get('success_rate', 0):.1%} ({data.get('success', 0)}/{data.get('success', 0) + data.get('failure', 0)})\n")
    
    print(f"\nResults saved to {output_dir}/")
    print("\n" + "=" * 60)
    print("BASELINE SUMMARY")
    print("=" * 60)
    print(f"Task Success Rate: {summary.get('task_success_rate', 0):.1%}")
    print(f"First Attempt Rate: {summary.get('first_attempt_rate', 0):.1%}")
    print(f"Average Latency: {summary.get('avg_latency', 0):.2f}s")
    print(f"Tool Calls: {summary['tool_calls']}")
    print(f"Failure Rate: {summary.get('failure_rate', 0):.1%}")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_baseline_benchmark())