"""Immutable query results; payload records contain no behavior or I/O."""
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar('T')


@dataclass(frozen=True)
class Problem:
    kind: str
    message: str
    command: tuple[str, ...] = ()
    exit_code: int | None = None
    diagnostics: str = ''
    retryable: bool = False
    retry_after: float | None = None
    repair: str = 'Inspect this query and repair its input or adapter.'
    owner: str = 'amon@atm-monitor'


@dataclass(frozen=True)
class Ok(Generic[T]):
    query: str
    source: str
    scope: str
    data: tuple[T, ...]
    observed_at: str
    status: str = field(default='ok', init=False)


@dataclass(frozen=True)
class Partial(Generic[T]):
    query: str
    source: str
    scope: str
    data: tuple[T, ...]
    observed_at: str
    problems: tuple[Problem, ...]
    cursor: str | None = None
    status: str = field(default='partial', init=False)


@dataclass(frozen=True)
class Error:
    query: str
    source: str
    scope: str
    observed_at: str
    problem: Problem
    status: str = field(default='error', init=False)


QueryResult = Ok[T] | Partial[T] | Error
