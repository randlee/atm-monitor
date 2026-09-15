"""Immutable oversight answers and discrete evidence support."""
from dataclasses import dataclass
from branch_types import BranchRow
from assignment_types import AssignmentState, AgentState


@dataclass(frozen=True)
class Fact:
    value: str
    support: str = 'authoritative'
    freshness: str = 'fresh'
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class SprintRow:
    phase: str
    sprint: str
    branch: str
    parent: str
    owner: Fact
    tasks: Fact
    development: Fact
    qa: Fact
    rounds: Fact
    findings: Fact
    prs: Fact
    ci: Fact
    blocker: Fact
    next_action: str


@dataclass(frozen=True)
class Condition:
    key: str
    kind: str
    subject: str
    revision: str
    status: str
    owner: str
    detail: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainState:
    repo: str
    rows: tuple[SprintRow, ...]
    conditions: tuple[Condition, ...]
    inventory: str
    branches: tuple[BranchRow, ...] = ()
    assignments: tuple[AssignmentState, ...] = ()
    agents: tuple[AgentState, ...] = ()


@dataclass(frozen=True)
class Timer:
    key: str
    since: str


@dataclass(frozen=True)
class Incident:
    key: str
    condition: Condition
    active: bool
    delivery: str
    first_seen: str
    last_attempt: str | None = None
    receipt: str | None = None


@dataclass(frozen=True)
class QuerySlot:
    key: str
    last_good: object | None
    latest: object
    failures: int
    retry_at: str | None
    checkpoint: str | None = None


@dataclass(frozen=True)
class Envelope:
    schema_version: int
    generation: int
    state: DomainState
    slots: tuple[QuerySlot, ...]
    incidents: tuple[Incident, ...]
    timers: tuple[Timer, ...]
    observed_at: str
