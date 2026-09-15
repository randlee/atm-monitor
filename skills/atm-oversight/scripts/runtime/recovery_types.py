"""Immutable records for query recovery and scheduler evidence."""
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class QueryReceipt:
    query: str; scope: str; attempted_at: str | None = None
    succeeded_at: str | None = None; checkpoint: str | None = None
    coverage: str = 'unknown'; problem: Any = None
    retry_after: float | None = None; attempts: int = 0

@dataclass(frozen=True)
class SchedulerRun:
    job_id: str; execution_id: str; status: str; claimed_at: str
    started_at: str | None = None; finished_at: str | None = None
    error: str | None = None; registered: bool = False; completed: bool = False
