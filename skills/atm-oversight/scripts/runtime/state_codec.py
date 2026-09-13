"""Allowlisted frozen records and tagged tuples; JSON never becomes mutable state."""
from dataclasses import fields, is_dataclass
import math
import types
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints


class CodecError(ValueError):
    pass


def encode(value, registry):
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, tuple):
        return {'__tuple__': [encode(x, registry) for x in value]}
    if is_dataclass(value) and type(value) in registry and type(value).__dataclass_params__.frozen:
        return {'__type__': registry[type(value)],
                **{f.name: encode(getattr(value, f.name), registry) for f in fields(value)}}
    raise CodecError('Non-frozen, mutable, nonfinite or unregistered state value')


def decode(value, typ, registry):
    origin, args = get_origin(typ), get_args(typ)
    if origin in (Union, types.UnionType):
        for candidate in args:
            try:
                return decode(value, candidate, registry)
            except CodecError:
                pass
        raise CodecError('Union mismatch')
    dynamic = typ in (Any, object) or isinstance(typ, TypeVar)
    if dynamic:
        if isinstance(value, dict) and '__type__' in value:
            matches = [t for t, name in registry.items() if name == value['__type__']]
            if len(matches) != 1:
                raise CodecError('Unknown state record')
            return decode(value, matches[0], registry)
        if isinstance(value, dict) and '__tuple__' in value:
            return decode(value, tuple[Any, ...], registry)
        if value is None or type(value) in (str, int, float, bool):
            return decode(value, type(value), registry)
        raise CodecError('Untagged mutable value')
    if value is None:
        if typ is type(None):
            return None
        raise CodecError('Required value is null')
    if origin is tuple or typ is tuple:
        if not isinstance(value, dict) or set(value) != {'__tuple__'} or not isinstance(value['__tuple__'], list):
            raise CodecError('Tagged tuple required')
        items = value['__tuple__']
        if args and len(args) == 2 and args[1] is Ellipsis:
            args = args[:1] * len(items)
        if args and len(args) != len(items):
            raise CodecError('Tuple length mismatch')
        return tuple(decode(v, args[i] if args else Any, registry) for i, v in enumerate(items))
    if isinstance(typ, type) and is_dataclass(typ):
        if typ not in registry or not typ.__dataclass_params__.frozen:
            raise CodecError('Unregistered or mutable record')
        declared = fields(typ)
        if not isinstance(value, dict) or set(value) != {'__type__', *(f.name for f in declared)}:
            raise CodecError('Record fields mismatch')
        if value['__type__'] != registry[typ]:
            raise CodecError('Record type mismatch')
        hints = get_type_hints(typ)
        values = {f.name: decode(value[f.name], hints[f.name], registry) for f in declared}
        instance = typ(**{f.name: values[f.name] for f in declared if f.init})
        if any(getattr(instance, f.name) != values[f.name] for f in declared if not f.init):
            raise CodecError('Discriminator mismatch')
        return instance
    if type(value) is typ and typ in (str, int, float, bool):
        if typ is float and not math.isfinite(value):
            raise CodecError('Nonfinite number')
        return value
    raise CodecError('Invalid primitive or unsupported type')
