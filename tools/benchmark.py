"""Opt-in synthetic GPU/CPU benchmark; never takes a user movie as input."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import Engine, create_copies, check_leak
from app.records import save, sha256

parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path, help='A new directory for synthetic test media')
parser.add_argument('--seconds', type=int, default=12, choices=range(4, 61))
args = parser.parse_args()
folder = args.output.resolve()
folder.mkdir(parents=True, exist_ok=False)
source = folder / 'synthetic.mp4'
subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'lavfi', '-i',
    f'testsrc2=size=1920x1080:rate=24:duration={args.seconds}', '-f', 'lavfi', '-i',
    f'sine=frequency=440:duration={args.seconds}', '-c:v', 'libx264', '-threads', '4',
    '-preset', 'fast', '-crf', '15', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(source)], check=True)
original_hash = sha256(source)
engine = Engine()
render = engine.render
render_seconds = []


def timed_render(*values, **kwargs):
    start = time.monotonic()
    result = render(*values, **kwargs)
    render_seconds.append(time.monotonic() - start)
    return result


engine.render = timed_render
start = time.monotonic()
create_copies(engine, source, folder, dict(copies=1, label='Benchmark', start_number=16, max_gb=.1),
    lambda phase, **detail: print(json.dumps(dict(phase=phase, **detail)), flush=True), lambda *a: None)
create_seconds = time.monotonic() - start
register = json.loads((folder / 'PRIVATE-recovery.json').read_text())
label = next(iter(register['copy_tokens']))
recompressed = folder / 'recompressed.mp4'
subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-i', str(folder / (label + '.mp4')),
    '-c:v', 'libx264', '-threads', '4', '-preset', 'fast', '-crf', '24', '-c:a', 'copy', str(recompressed)], check=True)
result = check_leak(engine, recompressed, folder / 'PRIVATE-recovery.json', folder,
    dict(start=0, seconds=min(12, args.seconds)), lambda *a, **kw: None, lambda *a: None)
assert result['status'] == 'registered_copy_recovered' and result['aggregate']['copy_label'] == label
assert sha256(source) == original_hash
summary = dict(device=engine.device, batch_frames=engine.batch, encoder_threads=getattr(engine, 'encoder_threads', 4),
    duration=args.seconds, frames=args.seconds * 24, render_seconds=render_seconds[0],
    render_fps=args.seconds * 24 / render_seconds[0], create_and_verify_seconds=create_seconds,
    recompressed_recovered=True, source_unchanged=True,
    limits='Synthetic 1080p test only. Not a predicted speedup or visual-quality assessment for other videos.')
save(folder / 'benchmark-result.json', summary)
print(json.dumps(summary), flush=True)
