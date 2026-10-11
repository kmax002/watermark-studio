"""Build a source-only ZIP from a fixed allowlist, never recursive workspace data."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
files = ['README.md','VALIDATION.md','LICENSE','THIRD_PARTY_NOTICES.md','PRODUCT.md','DESIGN.md','AGENTS.md',
         'Dockerfile','.dockerignore','.gitignore','.gitattributes','requirements.txt','start-runpod.sh','runpod-template.json',
         'examples/github-container.yml']
for directory, pattern in [('app','*.py'),('static','*.html'),('static','*.css'),('static','*.js'),('tests','*.py'),('tools','*.py')]:
    files.extend(str(p.relative_to(root)).replace('\\','/') for p in (root/directory).glob(pattern))
files = sorted(set(files))
target = Path(sys.argv[1]).resolve()
target.parent.mkdir(parents=True, exist_ok=True)
manifest = {}
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for name in files:
        path = root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RuntimeError('Unexpected source link.')
        data=path.read_bytes()
        manifest[name]=hashlib.sha256(data).hexdigest()
        z.writestr('watermark-studio/'+name,data)
    z.writestr('watermark-studio/SOURCE-MANIFEST.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(files)+1
print(json.dumps(dict(file=str(target),source_files=len(files),bytes=target.stat().st_size,
    sha256=hashlib.sha256(target.read_bytes()).hexdigest(),private_runtime_data_included=False)))
