"""Frozen GitHub source observations used by the independent adapters."""
from dataclasses import dataclass

@dataclass(frozen=True)
class PR:
    node_id: str
    number: int
    updated_at: str
    state: str
    head: str
    head_sha: str
    base: str
    base_sha: str
    draft: bool | None = None
    mergeable: str | None = None
    merge_state: str | None = None
    queued: bool | None = None
    stack_id: str | None = None
    stack_number: int | None = None
    stack_position: int | None = None
    rollup_state: str | None = None
    rollup_sha: str | None = None

@dataclass(frozen=True)
class Check:
    pr_number: int
    head_sha: str
    name: str
    status: str
    conclusion: str | None = None
    required: str = 'unknown'
    attempt: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    url: str | None = None
    draft: bool | None = None

@dataclass(frozen=True)
class Stack:
    node_id: str
    number: int | None
    base: str | None
    members: tuple[PR, ...] = ()

@dataclass(frozen=True)
class StackView:
    trunk: str | None
    branches: tuple[str, ...]
    base: str | None
    heads: tuple[tuple[str, str], ...] = ()
    prs: tuple[tuple[str, int], ...] = ()
    merged: tuple[str, ...] = ()
    queued: tuple[str, ...] = ()
    needs_rebase: tuple[str, ...] = ()

@dataclass(frozen=True)
class Requirement:
    name: str
    state: str
    event: str | None = None
    workflow: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    url: str | None = None

@dataclass(frozen=True)
class QAReport:
    pr_number: int
    reviewed_sha: str
    verdict: str
    findings: tuple[tuple[str, str], ...] = ()
    report_id: str | None = None

@dataclass(frozen=True)
class Ancestry:
    repo_path: str
    base_sha: str
    head_sha: str
    included: bool
