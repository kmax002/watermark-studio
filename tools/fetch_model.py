"""Explicit setup download of public code/weights only; never invoked by a job."""
import hashlib
import os
from pathlib import Path
import subprocess
import urllib.request

COMMIT = '870ca7fb33578b90f14c602016b6c2788096226e'
HASH = '0c5665cff20eb6ce1b5aaa7d91c19dafb418bfee32d02dd3344e4ed60d9d75bd'
repo = Path(os.environ.get('VIDEOSEAL_REPO', '/opt/videoseal'))
if not repo.exists():
    subprocess.run(['git', 'clone', 'https://github.com/facebookresearch/videoseal.git', str(repo)], check=True)
    subprocess.run(['git', '-C', str(repo), 'checkout', COMMIT], check=True)
actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
if actual != COMMIT:
    raise SystemExit('Model repository has a different revision. Choose a new empty model directory.')
target = repo / 'ckpts/pixelseal_checkpoint.pth'
target.parent.mkdir(exist_ok=True)
if not target.exists():
    temp = target.with_suffix('.download')
    urllib.request.urlretrieve('https://dl.fbaipublicfiles.com/videoseal/pixelseal/checkpoint.pth', temp)
    if hashlib.file_digest(temp.open('rb'), 'sha256').hexdigest() != HASH:
        temp.unlink()
        raise SystemExit('Model download failed fingerprint verification.')
    temp.replace(target)
with target.open('rb') as f:
    if hashlib.file_digest(f, 'sha256').hexdigest() != HASH:
        raise SystemExit('Existing model is damaged. It was not replaced.')
print('Pinned PixelSeal model verified.')
