"""Read the top-level scalar identity fields in a rendered plan.

This deliberately does not interpret the rest of YAML. Identity fields must
be simple strings; nested dependency/authority blocks remain the plan's concern.
"""

import json
import re

FIELDS = {"plan_type", "phase", "sprint", "branch", "worktree", "status",
          "canonical_path", "integration_branch", "final_integration_branch"}


def scalar(value):
    value = value.strip()
    if value.startswith('"'):
        parsed, end = json.JSONDecoder().raw_decode(value)
        remainder = value[end:].strip()
        if not isinstance(parsed, str) or (remainder and not remainder.startswith('#')):
            raise ValueError("expected a quoted scalar string")
        return parsed
    if value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
        if not match:
            raise ValueError("invalid single-quoted scalar")
        return match[1].replace("''", "'")
    value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
    if not value or value[0] in "[{&*!|>" or value in {"null", "~"}:
        raise ValueError("expected a nonempty scalar string")
    return value


def read_metadata(text):
    lines = text.lstrip('\ufeff').splitlines()
    blocks = []
    if lines and lines[0].strip() == '---':
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
        if end is None:
            raise ValueError("unterminated frontmatter")
        blocks.append(lines[1:end])
    for i, line in enumerate(lines):
        if line.strip() in {'```yaml', '```yml'}:
            end = next((j for j in range(i + 1, len(lines)) if lines[j].strip() == '```'), None)
            if end is not None:
                block = lines[i + 1:end]
                if any(re.match(r'(phase|sprint|plan_type):', row) for row in block):
                    blocks.append(block)
    candidates = []
    for block in blocks:
        result = {}
        for line in block:
            match = re.match(r'^([a-z_]+):\s*(.*)$', line)
            if not match or match[1] not in FIELDS:
                continue
            key = match[1]
            if key in result:
                raise ValueError(f"duplicate identity field: {key}")
            result[key] = scalar(match[2])
        if 'phase' in result or 'sprint' in result:
            candidates.append(result)
    if len(candidates) != 1:
        raise ValueError("expected exactly one plan identity block (frontmatter or fenced YAML)")
    return candidates[0]
