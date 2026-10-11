"""Prepare (do not submit) a Runpod template for an immutable public GitHub commit."""
import json
from pathlib import Path
import re
import sys

repo, revision, output = sys.argv[1:]
if not re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
    raise SystemExit('Use a public GitHub repository URL.')
if not re.fullmatch('[0-9a-f]{40}', revision):
    raise SystemExit('Use a full immutable Git commit SHA.')
# All interpolated values are constrained above. The version directory is unique
# to this commit, so an upgrade cannot mix sources with an older installation.
directory = '/workspace/watermark-studio-' + revision[:12]
command = (
    'set -e; test "${#APP_PASSWORD}" -ge 16 || { echo "Set APP_PASSWORD to at least 16 characters before deploying."; exit 1; }; '
    f'if [ ! -d {directory}/.git ]; then git clone {repo}.git {directory}; fi; '
    f'cd {directory}; git checkout --detach {revision}; '
    f'test "$(git rev-parse HEAD)" = {revision}; git diff --quiet; git diff --cached --quiet; exec bash start-runpod.sh'
)
spec = dict(name='Watermark Studio', category='NVIDIA', imageName='runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404',
    dockerEntrypoint=[], dockerStartCmd=['bash','-lc',command], containerDiskInGb=30,
    volumeInGb=100, volumeMountPath='/workspace', ports=['7860/http'], isServerless=False, isPublic=True,
    env={'APP_PASSWORD':'','COOKIE_SECURE':'1','WATERMARK_DEVICE':'cuda',
         'WATERMARK_DATA':'/workspace/watermark-studio-data'},
    readme='Invisible per-copy video watermarking. Set a unique APP_PASSWORD (16+ characters) before deployment. '
           'Open HTTP port 7860 after first-time setup. Download videos and back up the private recovery JSON, then terminate the Pod. '
           'Later, use a fresh Pod with only the suspected leak and saved recovery JSON to recover the copy number. '
           'Experimental: identifies an issued copy, not a person. Source: ' + repo)
with Path(output).open('x',encoding='utf8') as f:
    json.dump(spec,f,indent=2)
print('Prepared a public template with no password. No Pod was started and no account was changed.')
