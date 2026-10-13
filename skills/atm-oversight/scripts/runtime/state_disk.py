"""Atomic per-repository persistence with a recoverable last-valid copy."""
import json, os, tempfile, sys, shutil
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'cron'))
from state_store import locked
try: from .state_codec import encode, decode, CodecError
except ImportError: from state_codec import encode, decode, CodecError
class StateError(ValueError): pass

def _write(path, value):
    fd,name=tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf8') as f: json.dump(value,f,separators=(',',':')); f.flush(); os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def save(directory, state, typ, registry):
    d=Path(directory); d.mkdir(parents=True,exist_ok=True); payload=encode(state,registry)
    decode(payload, typ, registry)
    with locked(d):
        p=d/'state.json'; b=d/'state.last-valid.json'
        if p.exists():
            try:
                old=json.loads(p.read_text(encoding='utf8'))
                if old.get('schema_version') == 1 and 'state' in old:
                    decode(old['state'], typ, registry)
                    _write(b, old)
            except (OSError, ValueError, AttributeError, TypeError):
                shutil.copy2(p, d / ('state.corrupt-' + uuid.uuid4().hex + '.json'))
        _write(p, {'schema_version':1,'state':payload})
    return p

def load(directory, typ, registry):
    d=Path(directory)
    errors=[]; found=False
    for p in (d/'state.json', d/'state.last-valid.json'):
        try:
            if not p.exists(): continue
            found=True
            raw=json.loads(p.read_text());
            if raw.get('schema_version') != 1: raise CodecError('unsupported schema')
            return decode(raw['state'],typ,registry), p
        except (OSError, ValueError, KeyError, TypeError, CodecError) as exc:
            errors.append({'file':p.name,'error':str(exc)})
    if not found: return None, None
    raise StateError('; '.join(f"{x['file']}: {x['error']}" for x in errors))
