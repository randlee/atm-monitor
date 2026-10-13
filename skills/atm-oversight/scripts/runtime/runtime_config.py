"""Validate deployment identity and query scope before launching workers."""
from pathlib import Path
import re
from runtime_policy import read_policy
from time_rules import timestamp


def validate(config):
    if config.get('schema_version') != 2:
        raise ValueError('Expected runtime configuration schema_version 2')
    read_policy(config['policy'])
    repos = config['repos']
    if not isinstance(repos, list) or not repos:
        raise ValueError('Configure at least one repository')
    seen = set()
    for repo in repos:
        slug = repo['slug']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', slug) or slug in seen:
            raise ValueError('Repository slugs must be unique owner/repository identifiers')
        seen.add(slug)
        for key in ('path', 'team', 'actor'):
            if not isinstance(repo[key], str) or not repo[key]:
                raise ValueError('Missing repository ' + key)
        if not Path(repo['path']).is_absolute() or timestamp(repo['since']) is None:
            raise ValueError('Use an absolute repository path and explicit since timestamp')
        if not repo['branch_prefixes'] or any(not p for p in repo['branch_prefixes']):
            raise ValueError('Explicit nonempty monitored branch prefixes are required')
        phases = set()
        for phase in repo['phases']:
            if phase['phase'] in phases or not re.fullmatch('[0-9a-f]{40,64}', phase['revision']):
                raise ValueError('Use unique phase identities and pinned plan revisions')
            phases.add(phase['phase'])
            if type(phase['expected_sprints']) is not int or phase['expected_sprints'] < 1:
                raise ValueError('Expected sprint count must be positive')
            if Path(phase['plan']).is_absolute() or '..' in Path(phase['plan']).parts:
                raise ValueError('Plan path must be repository-relative')
        for key in ('branch_patterns', 'scope_patterns'):
            for patterns in repo.get(key, {}).values():
                for pattern in patterns:
                    re.compile(pattern)
    return config
