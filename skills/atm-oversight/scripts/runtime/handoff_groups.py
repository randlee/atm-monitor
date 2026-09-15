"""One shared-service repair wake carries every affected receipt target."""


def group(events):
    output, shared = [], {}
    for event in events:
        result = event.get('query_result', {})
        if event.get('kind') == 'query-repair' and result.get('query') == 'herdr_agents':
            identity = result.get('problem', {}).get('kind', 'partial')
            if identity not in shared:
                shared[identity] = dict(event, receipt_targets=[])
                output.append(shared[identity])
            shared[identity]['receipt_targets'].append({
                'state_dir': event['state_dir'], 'incident_key': event['incident_key']})
        else:
            output.append(event)
    return output
