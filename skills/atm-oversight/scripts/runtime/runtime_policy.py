"""Validated deployment policy; thresholds are explicit configuration."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    command_timeout: int
    freshness_seconds: int
    idle_grace_seconds: int
    ci_start_seconds: int
    ci_queue_seconds: int
    ci_run_seconds: int
    retry_seconds: int
    retries: int
    overlap_seconds: int
    window_seconds: int
    page_size: int
    repo_workers: int
    watchdog_seconds: int
    followup_seconds: int
    policy_refresh_seconds: int
    detail_budget: int
    repo_timeout_seconds: int
    query_workers: int = 4
    github_page_budget: int = 3


def read_policy(value):
    expected = set(Policy.__dataclass_fields__)
    if set(value) != expected:
        raise ValueError('Policy must specify exactly: ' + ', '.join(sorted(expected)))
    if any(type(x) is not int or x <= 0 for x in value.values()):
        raise ValueError('Policy values must be positive integers')
    policy = Policy(**value)
    if policy.page_size > 100 or policy.repo_workers > 16:
        raise ValueError('page_size <= 100 and repo_workers <= 16 are required')
    if policy.query_workers > 4 or policy.github_page_budget > 10:
        raise ValueError('query_workers <= 4 and github_page_budget <= 10 are required')
    if policy.overlap_seconds >= policy.window_seconds:
        raise ValueError('Window must exceed its overlap')
    return policy
