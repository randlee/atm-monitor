"""Immutable observation provenance and explicit investigation dispositions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class OwnerActivity:
    agent: str
    host: str
    observed_at: str
    message_at: str | None = None
    message_id: str | None = None


@dataclass(frozen=True)
class IdleResolution:
    incident_key: str
    outcome: str
    reason: str
    evidence: tuple[str, ...]
    recorded_at: str
