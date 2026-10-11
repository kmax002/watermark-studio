"""Experimental authenticated 256-bit payload with BCH error correction.

The 32-bit copy token is unique inside the private film register; an eight-byte
HMAC binds it to that film's source hash. This authenticates an issued payload,
not the identity of a person or the provenance of a leaked recording.
"""
import hashlib
import hmac
import itertools
import bchlib
import numpy as np


def encode(token, key, source_hash):
    token_bytes = bytes.fromhex(token)
    if len(token_bytes) != 4 or len(key) != 32 or len(source_hash) != 64:
        raise ValueError('Expected 32-bit token, 256-bit key, and source SHA-256.')
    tag = hmac.new(key, b'film-watermark-v1\0' + bytes.fromhex(source_hash) + token_bytes, hashlib.sha256).digest()[:8]
    data = token_bytes + tag
    codec = bchlib.BCH(20, m=8)
    codeword = data + codec.encode(data)
    assert len(codeword) == 32
    return np.unpackbits(np.frombuffer(codeword, np.uint8))


def decode(logits, key, source_hash, issued_tokens):
    logits = np.asarray(logits, dtype=np.float64)
    if logits.shape != (256,) or not np.isfinite(logits).all():
        raise ValueError('Expected 256 finite bit logits.')
    # BCH(255) shortened to 96 data bits plus 140 parity bits. The last 20
    # bits are library padding and must not be counted as independent evidence.
    bits = (logits > 0).astype(np.uint8)
    weak = np.argsort(np.abs(logits[:236]))[:4]
    candidates = {}
    # Fixed bounded Chase search: up to two flips among the four weakest bits.
    for count in range(3):
        for flips in itertools.combinations(weak.tolist(), count):
            proposal = bits.copy()
            proposal[list(flips)] ^= 1
            raw = np.packbits(proposal).tobytes()
            data, ecc = bytearray(raw[:12]), bytearray(raw[12:])
            codec = bchlib.BCH(20, m=8)
            errors = codec.decode(data, ecc)
            if errors < 0:
                continue
            codec.correct(data, ecc)
            token = bytes(data[:4]).hex()
            expected_tag = hmac.new(key, b'film-watermark-v1\0' + bytes.fromhex(source_hash) + bytes(data[:4]), hashlib.sha256).digest()[:8]
            if token not in issued_tokens or not hmac.compare_digest(bytes(data[4:]), expected_tag):
                continue
            result = {'copy_token': token, 'corrected_bits': int(errors), 'soft_flips': len(flips)}
            if token not in candidates or errors + len(flips) < candidates[token]['corrected_bits'] + candidates[token]['soft_flips']:
                candidates[token] = result
    if len(candidates) != 1:
        return {'status': 'inconclusive', 'reason': 'no_unique_authenticated_registered_payload'}
    return {'status': 'authenticated_registered_payload', **next(iter(candidates.values()))}


def assess_frames(logits, key, source_hash, issued_tokens, aggregation='uniform'):
    logits = np.asarray(logits)
    if logits.ndim != 2 or logits.shape[1] != 256 or not np.isfinite(logits).all():
        raise ValueError('Expected finite frame-by-bit logits.')
    if len(logits) < 24:
        return {'status': 'inconclusive', 'reason': 'insufficient_frames'}
    if aggregation not in ['uniform', 'l1']:
        raise ValueError('Unsupported temporal aggregation.')
    def pool(values):
        if aggregation == 'uniform':
            return values.mean(0)
        # Reliability weights use all meaningful logits, never a target ID.
        weights = np.mean(np.abs(values[:, :236]), axis=1)
        weights = np.minimum(weights, 3 * max(float(np.median(weights)), 1e-8))
        return np.average(values, axis=0, weights=np.maximum(weights, 1e-8))
    aggregate = decode(pool(logits), key, source_hash, issued_tokens)
    halves = [decode(pool(x), key, source_hash, issued_tokens) for x in np.array_split(logits, 2)]
    all_results = [aggregate, *halves]
    tokens = {x.get('copy_token') for x in all_results}
    passed = all(x['status'] == 'authenticated_registered_payload' for x in all_results) and len(tokens) == 1
    return {'status': 'registered_copy_recovered' if passed else 'inconclusive',
            'aggregate': aggregate, 'disjoint_halves': halves,
            'frames': len(logits), 'aggregation': aggregation,
            'attribution_limit': 'Identifies an issued payload, not a person or leak provenance.'}
