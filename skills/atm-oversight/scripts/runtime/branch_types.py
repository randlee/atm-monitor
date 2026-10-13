"""Ordered branch topology in the phase report."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BranchRow:
    stack: str
    branch: str
    parent: str
    pr: str
    head: str
    status: str
    maintenance: str
