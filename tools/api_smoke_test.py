"""Check the actual HTTP upload/worker/download path using neutral local files."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import httpx

base, video, report = sys.argv[1:]
client = httpx.Client(base_url=base, timeout=60, headers={'X-Watermark-Request':'1'})
def call(method, path, **kw):
    r = client.request(method, path, **kw)
    r.raise_for_status()
    return r.json()
call('POST','/api/login',json={'password':os.environ['APP_PASSWORD']})
source = Path(video)
ident = call('POST','/api/uploads',json=dict(name=source.name,size=source.stat().st_size,kind='video'))['id']
with source.open('rb') as f:
    offset=0
    for data in iter(lambda:f.read(8*1024*1024), b''):
        offset=call('PUT',f'/api/uploads/{ident}/chunks',content=data,headers={'X-Upload-Offset':str(offset)})['offset']
call('POST',f'/api/uploads/{ident}/finish')
job=call('POST','/api/jobs',json=dict(kind='create',video=ident,copies=1,label='API test',max_gb=.05))
deadline=time.monotonic()+300
while time.monotonic()<deadline:
    saved=next(j for j in call('GET','/api/state')['jobs'] if j['id']==job['id'])
    if saved['status']!='running':break
    time.sleep(2)
assert saved['status']=='complete',saved
assert len([f for f in saved['files'] if f['kind']=='video'])==1
key=client.get(f"/api/jobs/{job['id']}/files/PRIVATE-recovery.json").json()
assert key['key_hex'] not in client.get('/api/state').text
video_row=next(f for f in saved['files'] if f['kind']=='video')
video_response=client.get(f"/api/jobs/{job['id']}/files/{video_row['name']}")
video_response.raise_for_status()
verification=client.get(f"/api/jobs/{job['id']}/files/verification.json").json()
assert hashlib.sha256(video_response.content).hexdigest()==verification['copies'][0]['sha256']
# Start another job and stop it: cancellation must settle without releasing a video.
second=call('POST','/api/jobs',json=dict(kind='create',video=ident,copies=1,label='Cancel test',max_gb=.05))
collision=client.post('/api/jobs',json=dict(kind='create',video=ident))
assert collision.status_code==409
call('POST',f"/api/jobs/{second['id']}/cancel")
deadline=time.monotonic()+60
while time.monotonic()<deadline:
    stopped=next(j for j in call('GET','/api/state')['jobs'] if j['id']==second['id'])
    if stopped['status']!='running':break
    time.sleep(.5)
assert stopped['status']=='cancelled',stopped
assert not any(f['kind']=='video' for f in stopped['files'])
result=dict(passed=True,upload='chunked',actual_worker=True,download_hash_matches=True,
            secrets_excluded_from_state=True,concurrent_job_rejected=True,cancelled_without_video=True)
Path(report).write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result))
