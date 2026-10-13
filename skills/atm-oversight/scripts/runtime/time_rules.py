"""Pure timing and freshness; clocks are supplied by cron."""
from datetime import datetime, timezone


def timestamp(value):
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return date.timestamp() if date.tzinfo is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def elapsed(now, since, skew=30):
    start = timestamp(since)
    if start is None or start > now + skew:
        return None
    return max(0, now - start)


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def fresh(observed_at, now, max_age, skew=30):
    age = elapsed(now, observed_at, skew)
    return age is not None and age <= max_age
