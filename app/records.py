"""Portable recovery format. Private payloads never enter public job summaries."""
import hashlib
import json
import math
from pathlib import Path
import re
import secrets

CHECKPOINT = '0c5665cff20eb6ce1b5aaa7d91c19dafb418bfee32d02dd3344e4ed60d9d75bd'
COMMIT = '870ca7fb33578b90f14c602016b6c2788096226e'
SCHEMA = 'watermark-studio-v1'


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf8')
    temp.replace(path)


def validate_register(value):
    if not isinstance(value, dict) or value.get('schema') not in (SCHEMA, 'film-issued-copies-v1'):
        raise ValueError('Choose a Watermark Studio or compatible PixelSeal recovery JSON.')
    for field, size in [('key_hex', 64), ('source_sha256', 64)]:
        if not isinstance(value.get(field), str) or not re.fullmatch('[0-9a-f]{' + str(size) + '}', value[field]):
            raise ValueError('Recovery file contains an invalid key or source fingerprint.')
    if value.get('checkpoint_sha256') != CHECKPOINT:
        raise ValueError('This recovery file requires a different model.')
    tokens = value.get('copy_tokens')
    if not isinstance(tokens, dict) or not 1 <= len(tokens) <= 100:
        raise ValueError('Recovery file must contain 1 to 100 copy IDs.')
    if any(not isinstance(k, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}', k)
           or not isinstance(v, str) or not re.fullmatch('[0-9a-f]{8}', v) for k, v in tokens.items()):
        raise ValueError('Recovery labels or IDs are invalid.')
    if len(set(tokens.values())) != len(tokens):
        raise ValueError('Recovery file contains duplicate IDs.')
    settings = value.get('settings', {})
    if settings.get('model') != 'pixelseal' or settings.get('strength') != .2 or settings.get('step_size') != 2:
        raise ValueError('Unsupported watermark settings.')
    for dim in ('width', 'height'):
        n = settings.get(dim)
        if type(n) is not int or not 256 <= n <= 3840:
            raise ValueError('Invalid recovery frame size.')
    return value


def new_register(source_hash, copies, label, media):
    if type(copies) is not int or not 1 <= copies <= 100:
        raise ValueError('Choose 1 to 100 copies.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,39}', label):
        raise ValueError('Use a short label with letters, numbers, spaces or hyphens.')
    tokens = {}
    for i in range(1, copies + 1):
        token = secrets.token_hex(4)
        while token in tokens.values():
            token = secrets.token_hex(4)
        tokens[f'{label} {i:03d}'] = token
    return validate_register(dict(schema=SCHEMA, source_sha256=source_hash,
        key_hex=secrets.token_hex(32), copy_tokens=tokens, checkpoint_sha256=CHECKPOINT,
        repository_commit=COMMIT, settings=dict(model='pixelseal', strength=.2, step_size=2,
            width=media['width'], height=media['height'], fps=media['fps']),
        note='Keep private. Identifies an issued copy, not a person. Back up before ending your Pod.'))


def verification_windows(duration):
    seconds = min(12., duration)
    return [(round((duration - seconds) * i / 6, 3), seconds) for i in range(7)] if duration > 24 else [(0., seconds)]


def bitrate_for_limit(max_gb, duration, audio):
    if not math.isfinite(max_gb) or not .01 <= max_gb <= 100:
        raise ValueError('Maximum size must be between 0.01 and 100 GB.')
    # Decimal GB. Leave 10% for muxing, encoder variation, and audio overhead.
    rate = int(max_gb * 1_000_000_000 * .9 * 8 / duration) - (192_000 if audio else 0)
    if rate < 500_000:
        raise ValueError('That size is too small for this duration. Increase the file-size limit.')
    return rate

