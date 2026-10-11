"""Opt-in real model test on neutral synthetic video. No paid/cloud requests."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import Engine, create_copies, check_leak
from app.records import save, sha256

if len(sys.argv) != 2:
    raise SystemExit('Usage: python tools/smoke_test.py NEW_OUTPUT_DIRECTORY')
folder = Path(sys.argv[1]).resolve()
folder.mkdir(parents=True, exist_ok=False)
source = folder/'neutral.mp4'
subprocess.run(['ffmpeg','-v','error','-n','-f','lavfi','-i','testsrc2=size=1280x720:rate=12:duration=8',
    '-f','lavfi','-i','sine=frequency=440:duration=8','-c:v','libx264','-crf','15','-pix_fmt','yuv420p',
    '-c:a','aac','-shortest',str(source)],check=True)
before = sha256(source)
engine = Engine()
def progress(phase, **extra):
    print(json.dumps(dict(phase=phase, **extra)), flush=True)
published = []
def publish(name,label,kind):
    published.append(dict(name=name,label=label,kind=kind))
result = create_copies(engine, source, folder, dict(copies=2,label='Neutral',max_gb=.05), progress, publish)
leak = folder/'recompressed.mp4'
subprocess.run(['ffmpeg','-v','error','-n','-i',str(folder/'Neutral 001.mp4'),'-c:v','libx264','-crf','24','-c:a','copy',str(leak)],check=True)
checked = check_leak(engine,leak,folder/'PRIVATE-recovery.json',folder,dict(start=0,seconds=8),progress,publish)
state=json.loads((folder/'PRIVATE-recovery.json').read_text())
control=engine.detect(source,state,0,8)
assert checked['status']=='registered_copy_recovered' and checked['aggregate']['copy_label']=='Neutral 001', checked
assert control['status']=='inconclusive', control
assert before==sha256(source)
summary=dict(passed=True,device=engine.device,copies=result['copies'],recompressed=checked['status'],clean_control=control['status'],source_unchanged=True,
    limits='Neutral 8-second synthetic clip only. This does not validate real films, every transformation or Runpod deployment.')
save(folder/'smoke-result.json',summary)
print(json.dumps(summary),flush=True)
