"""Scheduled O1–O4 runtime with bounded, isolated repository processes."""
import argparse
import json
from pathlib import Path
import time
import herdr_agents
from repo_workers import results
from runtime_policy import read_policy
from state_disk import _write, locked
from state_store import BusyError
from runtime_failure import record
from runtime_config import validate
from handoff_groups import group


def repo_directory(root, slug):
    return Path(root) / slug.replace('/', '--')


def run(config, root, shadow=False):
    validate(config)
    policy = read_policy(config['policy'])
    now = time.time()
    agents = herdr_agents.query(timeout=policy.command_timeout)
    received = []
    for repo, payload in results(config['repos'], root, policy, now, agents, shadow,
                                 policy.repo_workers, policy.repo_timeout_seconds):
        directory = repo_directory(root, repo['slug'])
        if payload['ok']:
            received.append(payload['result'])
            record(directory, repo['slug'])
        else:
            events = record(directory, repo['slug'], payload['error'], shadow)
            received.append({'repo': repo['slug'], 'events': events, 'error': payload['error']})
    events = group([e for item in received for e in item['events']])
    receipt = {'wakeAgent': bool(events), 'events': events, 'repos': received, 'observed_at': now}
    _write(Path(root) / 'last_run.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--shadow', action='store_true')
    args = parser.parse_args()
    try:
        args.state_dir.mkdir(parents=True, exist_ok=True)
        with locked(args.state_dir / 'scheduler'):
            config = json.loads(args.config.read_text())
            result = run(config, args.state_dir, args.shadow)
            record(args.state_dir / 'global', 'scheduler')
    except BusyError:
        result = {'wakeAgent': False, 'events': [], 'status': 'busy'}
    except Exception as exc:
        events = record(args.state_dir / 'global', 'scheduler', str(exc), args.shadow)
        result = {'wakeAgent': bool(events), 'events': events, 'error': str(exc)[:2000]}
    print(json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    main()
