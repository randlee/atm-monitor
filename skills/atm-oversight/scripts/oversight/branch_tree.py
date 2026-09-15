"""Build a deterministic branch hierarchy from PR and stack observations.

GitHub supplies branch names for a PR's base, while ``gh stack view`` supplies
an ordered stack and commit IDs for its bases.  The latter cannot be joined to
PRs by its ``base`` field, so ordered stack membership is retained as separate
parent evidence.
"""

import json
import re


BLOCKING_MERGE_STATES = {"BLOCKED", "BEHIND", "DIRTY", "UNSTABLE"}


def _natural_key(value):
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r"(\d+)", value)]


def _payloads(stacks):
    """Yield distinct stack payloads from source records or raw payloads."""
    if not stacks:
        return
    if isinstance(stacks, dict):
        stacks = stacks.values()
    seen = set()
    for source in stacks:
        if not isinstance(source, dict):
            continue
        payload = source.get("data") if "data" in source else source
        if not isinstance(payload, dict) or not isinstance(payload.get("trunk"), str):
            continue
        branches = payload.get("branches")
        if not isinstance(branches, list):
            continue
        # Ignore source metadata (worktree and observation time) when deciding
        # whether two worktree observations are the same stack.
        signature = json.dumps(
            {"trunk": payload["trunk"], "branches": branches},
            sort_keys=True, separators=(",", ":"), default=str)
        if signature in seen:
            continue
        seen.add(signature)
        yield payload


def _pr_number(pr):
    number = pr.get("number")
    return number if isinstance(number, int) else -1


def _status(pr, stack_rows):
    if pr:
        state = str(pr.get("state") or "UNKNOWN")
        if pr.get("isDraft") and state == "OPEN":
            state = "DRAFT"
    elif stack_rows:
        states = {str(row.get("pr", {}).get("state")) for row in stack_rows
                  if isinstance(row.get("pr"), dict) and row["pr"].get("state")}
        state = sorted(states)[0] if states else (
            "MERGED" if all(row.get("isMerged") is True for row in stack_rows) else "STACK")
    else:
        state = "BASE"
    flags = []
    active = state not in {"MERGED", "CLOSED"}
    if active and any(row.get("needsRebase") is True for row in stack_rows):
        flags.append("needs-rebase")
    return "; ".join([state, *flags])


def _actions(pr, stack_rows, parent, explicit_parent, stack_parents, conflict, cycle):
    actions = []
    state = str(pr.get("state")) if pr else ""
    if not pr and stack_rows and all(row.get("isMerged") is True for row in stack_rows):
        state = "MERGED"
    if not pr:
        states = {str(row.get("pr", {}).get("state")) for row in stack_rows
                  if isinstance(row.get("pr"), dict) and row["pr"].get("state")}
        if states and states <= {"MERGED", "CLOSED"}:
            state = sorted(states)[0]
    active = state not in {"MERGED", "CLOSED"}
    if active and any(row.get("needsRebase") is True for row in stack_rows):
        actions.append("rebase required")
    if active and stack_rows and any("head" not in row or row.get("head") in (None, "")
                          for row in stack_rows if not row.get("isMerged")):
        actions.append("stack head unknown")
    if active and pr:
        merge_state = pr.get("mergeStateStatus")
        mergeable = pr.get("mergeable")
        if merge_state in BLOCKING_MERGE_STATES:
            actions.append("merge state: " + str(merge_state))
        if mergeable == "CONFLICTING":
            actions.append("conflict=CONFLICTING")
    if conflict:
        actions.append("parent conflict: " + ", ".join(conflict))
    elif explicit_parent and stack_parents and parent != explicit_parent:
        # Keep the named PR base visible when ordered stack evidence supplies
        # the hierarchy displayed in the first column.
        actions.append("PR base=" + explicit_parent)
    elif not pr and not stack_rows:
        return "—"
    elif explicit_parent is None and parent is None:
        actions.append("parent unknown")
    if cycle:
        actions.append("cycle detected: " + " -> ".join(cycle))
    return "; ".join(actions) or "—"


def build_tree(prs, stacks=None):
    """Return branch nodes and parent links suitable for deterministic output.

    ``prs`` may contain one or more observations for a branch; the highest PR
    number is retained.  Each node has ``parent`` (or ``None``), ``children``,
    and evidence fields used by :func:`render_tree`.
    """
    if isinstance(prs, dict):
        prs = prs.values()
    latest = {}
    for pr in prs or ():
        if not isinstance(pr, dict) or not isinstance(pr.get("headRefName"), str):
            continue
        branch = pr["headRefName"]
        if branch not in latest or _pr_number(pr) >= _pr_number(latest[branch]):
            latest[branch] = pr

    nodes = {}

    def node(branch):
        if branch not in nodes:
            nodes[branch] = {"branch": branch, "pr": latest.get(branch),
                             "stack_rows": [], "explicit_parent": None,
                             "stack_parents": set(), "stack_order": None,
                             "parent": None, "children": [], "conflict": [],
                             "cycle": None, "action": "—"}
        return nodes[branch]

    for branch in latest:
        current = node(branch)
        base = latest[branch].get("baseRefName")
        if isinstance(base, str) and base:
            current["explicit_parent"] = base
            node(base)  # Preserve a base branch even without its own PR.

    for payload in _payloads(stacks):
        trunk = payload["trunk"]
        previous = trunk
        node(trunk)
        for index, row in enumerate(payload["branches"]):
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"]:
                continue
            branch = row["name"]
            current = node(branch)
            current["stack_rows"].append(row)
            if current["pr"] is None and isinstance(row.get("pr"), dict):
                stack_pr = row["pr"]
                current["pr"] = {"number": stack_pr.get("number"),
                                  "state": stack_pr.get("state", "UNKNOWN"),
                                  "headRefName": branch}
            if current["stack_order"] is None:
                current["stack_order"] = (trunk, index)
            # A repeated branch within one stack is evidence of malformed
            # topology; keep the observation and let cycle handling report it.
            current["stack_parents"].add(previous)
            previous = branch

    # Select parent links.  Ordered stack evidence supplies the nested view;
    # PR base names remain visible whenever they differ from that parent.
    for branch, current in nodes.items():
        explicit = current["explicit_parent"]
        stack_parents = current["stack_parents"]
        if len(stack_parents) > 1:
            current["conflict"] = sorted(stack_parents, key=_natural_key)
        elif stack_parents:
            stack_parent = next(iter(stack_parents))
            if explicit and explicit != stack_parent:
                current["conflict"] = ["PR base=" + explicit, "stack=" + stack_parent]
            else:
                current["parent"] = stack_parent
        elif explicit and explicit != branch:
            current["parent"] = explicit
        elif explicit == branch:
            current["conflict"] = ["PR base=" + explicit]

    # Parent candidates from independent stack views can disagree.  Do not
    # pick one merely because it sorts first; leave the node at a visible root.
    for current in nodes.values():
        if current["conflict"]:
            current["parent"] = None

    # Break cycles before constructing children.  Every affected node remains
    # visible as a root and carries the exact cycle evidence in its Action cell.
    visited = set()
    for branch in sorted(nodes, key=_natural_key):
        path, positions = [], {}
        while branch is not None and branch not in visited:
            if branch in positions:
                members = path[positions[branch]:]
                for member in members:
                    nodes[member]["parent"] = None
                    nodes[member]["cycle"] = members + [branch]
                break
            positions[branch] = len(path)
            path.append(branch)
            branch = nodes[branch]["parent"]
        visited.update(path)

    for current in nodes.values():
        current["children"] = []
    for branch, current in nodes.items():
        parent = current["parent"]
        if parent is not None and parent in nodes:
            nodes[parent]["children"].append(branch)
    for current in nodes.values():
        current["children"].sort(key=lambda item: (
            nodes[item]["stack_order"] is None,
            nodes[item]["stack_order"] or ("", 0), _natural_key(item)))
        current["action"] = _actions(
            current["pr"], current["stack_rows"], current["parent"],
            current["explicit_parent"], current["stack_parents"],
            current["conflict"], current["cycle"])
    return nodes


def _hierarchy(branch, depth, last, ancestors):
    if depth == 0:
        return _code(branch)
    parts = []
    for ancestor_last in ancestors:
        parts.append("　　　" if ancestor_last else "　│　")
    parts.append(("　└─ " if last else "　├─ ") + branch)
    return _code("".join(parts))


def _code(value):
    runs = re.findall(r"`+", value)
    fence = "`" * (max(map(len, runs), default=0) + 1)
    return fence + (" " + value + " " if runs else value) + fence


def _cell(value):
    """Keep arbitrary branch/action evidence inside one Markdown cell."""
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_tree(prs, stacks=None):
    """Render the branch hierarchy as a compact Markdown table."""
    nodes = build_tree(prs, stacks)
    if not nodes:
        return ""
    roots = [branch for branch, current in nodes.items() if current["parent"] is None]
    roots.sort(key=_natural_key)
    lines = ["| Branch hierarchy | PR | Status | Action |",
             "|---|---|---|---|"]

    pending = [(root, 0, index == len(roots) - 1, [])
               for index, root in reversed(list(enumerate(roots)))]
    while pending:
        branch, depth, last, ancestors = pending.pop()
        current = nodes[branch]
        pr = current["pr"]
        pr_label = "#" + str(pr["number"]) if pr and isinstance(pr.get("number"), int) else "—"
        lines.append("| " + " | ".join((_cell(_hierarchy(branch, depth, last, ancestors)),
                                       _cell(pr_label), _cell(_status(pr, current["stack_rows"])),
                                       _cell(current["action"]))) + " |")
        children = current["children"]
        for index, child in reversed(list(enumerate(children))):
            pending.append((child, depth + 1, index == len(children) - 1,
                            ancestors + ([last] if depth > 0 else [])))
    return "\n".join(lines)
