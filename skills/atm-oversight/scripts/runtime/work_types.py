"""Small immutable records emitted by source queries."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Task:
    task_id: str
    sprint: str | None = None
    assignee: str | None = None
    status: str = 'unknown'
    assigned_at: str | None = None
    started_at: str | None = None
    queue_position: int | None = None
    dependency: str | None = None
    description: str | None = None
    assignment_evidence: str | None = None

@dataclass(frozen=True)
class WorkflowEvent:
    event_id: str
    sprint: str | None
    stage: str | None
    task_id: str | None
    actor: str | None
    revision: str | None
    occurred_at: str | None
    metadata_ok: bool = True
    recipient: str | None = None
    mailbox: str | None = None
    report_id: str | None = None
    template_type: str | None = None
    workflow_state: str | None = None
    iteration: str | None = None

@dataclass(frozen=True)
class Agent:
    agent_id: str
    state: str = 'unknown'
    observed_at: str | None = None
    task_id: str | None = None
    background: str | None = None
    team: str | None = None
    cwd: str | None = None
    background_evidence: str | None = None
    state_since: str | None = None

@dataclass(frozen=True)
class Member:
    agent_id: str
    state: str = 'unknown'
    observed_at: str | None = None

@dataclass(frozen=True)
class Sprint:
    phase: str
    sprint: str
    branch: str | None = None
    order: int | None = None
    integration_branch: str | None = None
    status: str | None = None

@dataclass(frozen=True)
class Report:
    report_id: str
    revision: str | None
    round: str | None
    verdict: str | None
    findings: tuple[tuple[str, str, str], ...] = ()
    aggregate: tuple[tuple[str, int], ...] = ()
    review_id: str | None = None
