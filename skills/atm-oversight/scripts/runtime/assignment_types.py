"""Decision-relevant assignment and agent state, without poll timestamps."""
from dataclasses import dataclass


@dataclass(frozen=True)
class AssignmentState:
    task_id: str
    sprint: str | None
    assignee: str | None
    status: str
    assigned_at: str | None
    started_at: str | None
    position: int | None
    dependency: str | None
    freshness: str


@dataclass(frozen=True)
class AgentState:
    agent_id: str
    status: str
    background: str | None
    freshness: str
