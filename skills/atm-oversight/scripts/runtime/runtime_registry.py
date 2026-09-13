"""Explicit record modules permitted in persisted monitoring state."""
from dataclasses import is_dataclass
import answer_types
import query_types
import pr_types
import work_types
import recovery_types
import branch_types
import assignment_types

MODULES = (answer_types, query_types, pr_types, work_types, recovery_types, branch_types, assignment_types)
REGISTRY = {value: module.__name__ + '.' + name for module in MODULES
            for name, value in vars(module).items()
            if isinstance(value, type) and is_dataclass(value) and value.__module__ == module.__name__}
