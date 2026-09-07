"""
Cron job scheduler for autonomous recurring tasks.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any


class JobStatus(Enum):
    """Job status states."""

    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class CronJob:
    """Represents a scheduled job."""

    job_id: str
    name: str
    schedule: str  # cron expression or interval
    task: str  # task description
    callback: Callable | None = None
    status: JobStatus = JobStatus.SCHEDULED
    last_run: str | None = None
    next_run: str | None = None
    runs_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    enabled: bool = True


class CronScheduler:
    """
    Cron job scheduler for autonomous recurring tasks.
    Agent can schedule tasks to run automatically.
    """

    def __init__(self):
        self.jobs: dict[str, CronJob] = {}
        self.running = False
        self._task = None

    async def add_job(
        self,
        job_id: str,
        name: str,
        schedule: str,
        task: str,
        callback: Callable | None = None,
    ) -> bool:
        """
        Add a new cron job.

        Args:
            job_id: Unique job identifier
            name: Human-readable name
            schedule: Cron expression (e.g., "0 9 * * *") or interval ("5m", "1h", "1d")
            task: Task description or command
            callback: Optional async function to execute
        """
        try:
            next_run = self._calculate_next_run(schedule)

            job = CronJob(
                job_id=job_id,
                name=name,
                schedule=schedule,
                task=task,
                callback=callback,
                next_run=next_run,
            )

            self.jobs[job_id] = job
            return True
        except Exception as e:
            print(f"Failed to add job: {e}")
            return False

    def _calculate_next_run(self, schedule: str) -> str:
        """Calculate next run time from schedule."""
        now = datetime.now(UTC)

        # Handle interval format (5m, 1h, 1d)
        if schedule.endswith("m"):
            minutes = int(schedule[:-1])
            next_run = now + timedelta(minutes=minutes)
        elif schedule.endswith("h"):
            hours = int(schedule[:-1])
            next_run = now + timedelta(hours=hours)
        elif schedule.endswith("d"):
            days = int(schedule[:-1])
            next_run = now + timedelta(days=days)
        else:
            # Default: 1 hour
            next_run = now + timedelta(hours=1)

        return next_run.isoformat()

    async def run_job(self, job_id: str) -> dict[str, Any]:
        """Execute a job."""
        if job_id not in self.jobs:
            return {"success": False, "error": "Job not found"}

        job = self.jobs[job_id]
        job.status = JobStatus.RUNNING
        job.runs_count += 1

        try:
            result = None
            if job.callback:
                result = await job.callback(job.task)

            job.status = JobStatus.COMPLETED
            job.success_count += 1
            job.last_run = datetime.now(UTC).isoformat()
            job.next_run = self._calculate_next_run(job.schedule)

            return {
                "success": True,
                "job_id": job_id,
                "result": result,
                "next_run": job.next_run,
            }

        except Exception as e:
            job.status = JobStatus.FAILED
            job.fail_count += 1
            job.last_run = datetime.now(UTC).isoformat()

            return {"success": False, "job_id": job_id, "error": str(e)}

    async def start(self):
        """Start the scheduler."""
        self.running = True
        self._task = asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self._task:
            self._task.cancel()

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                now = datetime.now(UTC)

                # Check each job
                for job_id, job in self.jobs.items():
                    if not job.enabled:
                        continue

                    if job.next_run and datetime.fromisoformat(job.next_run) <= now:
                        # Run job in background
                        asyncio.create_task(self.run_job(job_id))

                # Sleep for 30 seconds
                await asyncio.sleep(30)

            except Exception as e:
                print(f"Scheduler error: {e}")
                await asyncio.sleep(30)

    async def pause_job(self, job_id: str) -> bool:
        """Pause a job."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = False
            self.jobs[job_id].status = JobStatus.PAUSED
            return True
        return False

    async def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = True
            self.jobs[job_id].status = JobStatus.SCHEDULED
            return True
        return False

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        if job_id in self.jobs:
            del self.jobs[job_id]
            return True
        return False

    async def list_jobs(self) -> list[dict[str, Any]]:
        """List all jobs."""
        jobs = []
        for job in self.jobs.values():
            jobs.append(
                {
                    "job_id": job.job_id,
                    "name": job.name,
                    "schedule": job.schedule,
                    "task": job.task,
                    "status": job.status.value,
                    "enabled": job.enabled,
                    "last_run": job.last_run,
                    "next_run": job.next_run,
                    "runs_count": job.runs_count,
                    "success_count": job.success_count,
                    "fail_count": job.fail_count,
                    "success_rate": (
                        job.success_count / job.runs_count if job.runs_count > 0 else 0
                    ),
                }
            )
        return jobs

    async def get_job_stats(self, job_id: str) -> dict[str, Any] | None:
        """Get job statistics."""
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]
        return {
            "job_id": job.job_id,
            "name": job.name,
            "runs_count": job.runs_count,
            "success_count": job.success_count,
            "fail_count": job.fail_count,
            "success_rate": (job.success_count / job.runs_count if job.runs_count > 0 else 0),
            "last_run": job.last_run,
            "next_run": job.next_run,
        }
