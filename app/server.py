"""Single-owner Pod app. Public assets only; all data routes require a session."""
import asyncio
from collections import deque
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import psutil

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .records import save, sha256, validate_register

BASE = Path(__file__).resolve().parents[1]
CHUNK = 8 * 1024 * 1024


class Upload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    size: int = Field(ge=1, le=100_000_000_000, strict=True)
    kind: str = Field(pattern='^(video|recovery)$')


class Job(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str = Field(pattern='^(create|check)$')
    video: str = Field(pattern='^[0-9a-f]{32}$')
    recovery: str | None = Field(default=None, pattern='^[0-9a-f]{32}$')
    copies: int = Field(default=1, ge=1, le=100, strict=True)
    label: str = Field(default='Copy', pattern='^[A-Za-z0-9][A-Za-z0-9 _-]{0,39}$')
    max_gb: float = Field(default=1.5, ge=.01, le=100, allow_inf_nan=False)
    start: float = Field(default=0, ge=0, le=14400, allow_inf_nan=False)
    seconds: float = Field(default=30, ge=4, le=60, allow_inf_nan=False)


def create_app(data_dir=None, password=None, launch=True):
    os.umask(0o077)
    root = Path(data_dir or os.environ.get('WATERMARK_DATA', BASE / '.data')).resolve()
    secret = password if password is not None else os.environ.get('APP_PASSWORD', '')
    if len(secret) < 16:
        raise RuntimeError('Set APP_PASSWORD to at least 16 characters before starting.')
    root.mkdir(parents=True, exist_ok=True)
    for name in ['uploads', 'jobs']:
        (root / name).mkdir(exist_ok=True)
    secure_cookie = os.environ.get('COOKIE_SECURE', '1') != '0'
    sessions = {}
    attempts = deque(maxlen=100)
    active = {}
    upload_locks = {}
    mutation_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        lock = (root / '.server.lock').open('a+b')
        lock.seek(0)
        lock.write(b'0')
        lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lock.close()
            raise RuntimeError('Another server owns this data folder. Use a single worker.') from None
        for path in (root / 'jobs').glob('*/status.json'):
            s = json.loads(path.read_text(encoding='utf8'))
            if s['status'] == 'running':
                s.update(status='interrupted', phase='Interrupted by restart', error='No automatic restart. Previously verified downloads remain available.')
                save(path, s)
        try:
            yield
        finally:
            for ident, proc in active.items():
                if proc.poll() is None:
                    (root / 'jobs' / ident / 'cancel').touch()
            for proc in active.values():
                if proc.poll() is None:
                    try:
                        await asyncio.to_thread(proc.wait, 20)
                    except subprocess.TimeoutExpired:
                        proc.terminate()
            lock.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def protect(request, call_next):
        path = request.url.path
        mutates = request.method not in ('GET', 'HEAD', 'OPTIONS')
        if mutates and request.headers.get('x-watermark-request') != '1':
            return JSONResponse({'detail': 'This request must come from Watermark Studio.'}, status_code=403)
        if path.startswith('/api/') and path not in ('/api/login', '/api/session'):
            token = request.cookies.get('wm_session', '')
            if sessions.get(token, 0) < time.time():
                return JSONResponse({'detail': 'Sign in to continue.'}, status_code=401)
        if mutates and '/chunks' not in path:
            try:
                if int(request.headers.get('content-length', '0')) > 8192:
                    return JSONResponse({'detail': 'Request is too large.'}, status_code=413)
            except ValueError:
                return JSONResponse({'detail': 'Invalid request size.'}, status_code=400)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 8192:
                    return JSONResponse({'detail': 'Request is too large.'}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.get('/api/session')
    def session(request: Request):
        return {'authenticated': sessions.get(request.cookies.get('wm_session', ''), 0) > time.time()}

    @app.post('/api/login')
    async def login(request: Request):
        now = time.time()
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, 'Too many attempts. Wait a minute.')
        attempts.append(now)
        try:
            submitted = (await request.json()).get('password', '')
        except (ValueError, AttributeError):
            submitted = ''
        if not isinstance(submitted, str) or not hmac.compare_digest(hashlib.sha256(submitted.encode()).digest(), hashlib.sha256(secret.encode()).digest()):
            raise HTTPException(401, 'Password not recognised.')
        token = secrets.token_urlsafe(32)
        sessions[token] = now + 86400
        for old in list(sessions):
            if sessions[old] < now:
                del sessions[old]
        result = JSONResponse({'authenticated': True})
        result.set_cookie('wm_session', token, httponly=True, secure=secure_cookie, samesite='strict', max_age=86400)
        return result

    @app.post('/api/logout')
    def logout(request: Request):
        sessions.pop(request.cookies.get('wm_session', ''), None)
        result = JSONResponse({'ok': True})
        result.delete_cookie('wm_session')
        return result

    def folder(kind, ident):
        if not re.fullmatch('[0-9a-f]{32}', ident):
            raise HTTPException(404, 'Not found.')
        path = root / kind / ident
        if not path.is_dir():
            raise HTTPException(404, 'Not found.')
        return path

    def upload_record(ident, kind):
        path = folder('uploads', ident)
        meta = json.loads((path / 'meta.json').read_text(encoding='utf8'))
        if meta['kind'] != kind or not meta.get('complete'):
            raise HTTPException(400, 'Upload is incomplete or has the wrong type.')
        return path / 'content', meta

    def status(path):
        result = json.loads((path / 'status.json').read_text(encoding='utf8'))
        proc = active.get(path.name)
        if proc and proc.poll() is not None and result['status'] == 'running':
            result.update(status='failed', phase='Stopped', error='The worker exited before completing. No automatic retry.')
            save(path / 'status.json', result)
        return result

    def busy():
        return any(p.poll() is None for p in active.values())

    @app.get('/api/state')
    def state():
        jobs = [status(p.parent) for p in sorted((root / 'jobs').glob('*/status.json'), key=lambda p: p.stat().st_mtime, reverse=True)]
        uploads = []
        for p in (root / 'uploads').glob('*/meta.json'):
            m = json.loads(p.read_text(encoding='utf8'))
            uploads.append({k: m[k] for k in ('id', 'name', 'size', 'kind', 'complete')})
        return dict(jobs=jobs, uploads=uploads, busy=busy(), free_gb=round(shutil.disk_usage(root).free / 1e9, 1), chunk_bytes=CHUNK)

    @app.post('/api/uploads')
    async def upload_start(spec: Upload):
        if spec.kind == 'recovery' and spec.size > 1_000_000:
            raise HTTPException(400, 'Recovery file is too large.')
        if spec.kind == 'video' and Path(spec.name).suffix.lower() not in ('.mp4', '.mov', '.mkv', '.webm', '.avi', '.ts'):
            raise HTTPException(400, 'Choose an MP4, MOV, MKV, WebM, AVI or TS video.')
        async with mutation_lock:
            if busy():
                raise HTTPException(409, 'Wait for processing to finish before uploading another file.')
            pending = sum(max(0, (m := json.loads(p.read_text()))['size'] - (p.parent / 'content').stat().st_size)
                          for p in (root / 'uploads').glob('*/meta.json') if (p.parent / 'content').exists())
            if shutil.disk_usage(root).free < spec.size + pending + 1_000_000_000:
                raise HTTPException(400, 'Not enough free storage for this upload.')
            ident = secrets.token_hex(16)
            path = root / 'uploads' / ident
            path.mkdir()
            (path / 'content').touch()
            meta = dict(id=ident, name=Path(spec.name.replace('\\', '/')).name, size=spec.size, kind=spec.kind, complete=False, chunks=[])
            save(path / 'meta.json', meta)
            return dict(id=ident, offset=0)

    @app.get('/api/uploads/{ident}')
    def upload_info(ident: str):
        path = folder('uploads', ident)
        meta = json.loads((path / 'meta.json').read_text())
        current = (path / 'content').stat().st_size
        if current != sum(x['size'] for x in meta['chunks']):
            raise HTTPException(409, 'Upload was interrupted while saving. Remove it and upload again.')
        return dict(offset=current, **meta)

    @app.put('/api/uploads/{ident}/chunks')
    async def upload_chunk(ident: str, request: Request):
        path = folder('uploads', ident)
        async with upload_locks.setdefault(ident, asyncio.Lock()):
            meta = json.loads((path / 'meta.json').read_text())
            current = (path / 'content').stat().st_size
            try:
                offset = int(request.headers.get('x-upload-offset', '-1'))
            except ValueError:
                raise HTTPException(400, 'Invalid upload position.') from None
            if meta['complete'] or offset != current:
                raise HTTPException(409, 'Upload position changed. Reselect the same file to resume.')
            if busy():
                raise HTTPException(409, 'Processing is using the workspace. Resume when finished.')
            received = 0
            digest = hashlib.sha256()
            with (path / 'content').open('r+b') as stream:
                stream.seek(current)
                try:
                    async for chunk in request.stream():
                        received += len(chunk)
                        if received > CHUNK or current + received > meta['size']:
                            raise HTTPException(413, 'Upload chunk is too large.')
                        if shutil.disk_usage(root).free < len(chunk) + 256_000_000:
                            raise HTTPException(400, 'Storage is nearly full.')
                        stream.write(chunk)
                        digest.update(chunk)
                except BaseException:
                    stream.truncate(current)
                    raise
            if received:
                meta['chunks'].append(dict(offset=current, size=received, sha256=digest.hexdigest()))
                save(path / 'meta.json', meta)
            return {'offset': current + received}

    @app.post('/api/uploads/{ident}/finish')
    async def finish(ident: str):
        path = folder('uploads', ident)
        async with upload_locks.setdefault(ident, asyncio.Lock()):
            meta = json.loads((path / 'meta.json').read_text())
            if (path / 'content').stat().st_size != meta['size']:
                raise HTTPException(400, 'Upload is incomplete.')
            if meta['kind'] == 'recovery':
                try:
                    validate_register(json.loads((path / 'content').read_text(encoding='utf8')))
                except (ValueError, KeyError, TypeError):
                    raise HTTPException(400, 'This is not a compatible recovery JSON file.') from None
            meta.update(complete=True, sha256=await asyncio.to_thread(sha256, path / 'content'))
            save(path / 'meta.json', meta)
            return {k: meta[k] for k in ('id', 'name', 'complete')}

    @app.post('/api/jobs')
    async def create_job(spec: Job):
        async with mutation_lock:
            if busy():
                raise HTTPException(409, 'One job can run at a time. Wait or stop the active job.')
            video, video_meta = upload_record(spec.video, 'video')
            recovery = None
            if spec.kind == 'check':
                if not spec.recovery:
                    raise HTTPException(400, 'Choose a recovery file.')
                recovery, _ = upload_record(spec.recovery, 'recovery')
            ident = secrets.token_hex(16)
            path = root / 'jobs' / ident
            path.mkdir()
            request = dict(kind=spec.kind, video=str(video), recovery=str(recovery) if recovery else None,
                           owner_pid=os.getpid(), owner_created=psutil.Process().create_time(),
                           options=spec.model_dump(exclude={'video', 'recovery', 'kind'}))
            save(path / 'request.json', request)
            record = dict(id=ident, kind=spec.kind, title=spec.label if spec.kind == 'create' else 'Leak check',
                          source=video_meta['name'], status='running', phase='Starting', files=[], created=time.time())
            save(path / 'status.json', record)
            if launch:
                try:
                    proc = subprocess.Popen([sys.executable, '-m', 'app.worker', str(path)], cwd=BASE,
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    active[ident] = proc
                except OSError:
                    record.update(status='failed', phase='Could not start', error='The worker could not start.')
                    save(path / 'status.json', record)
            return record

    @app.post('/api/jobs/{ident}/cancel')
    def cancel(ident: str):
        path = folder('jobs', ident)
        if status(path)['status'] == 'running':
            (path / 'cancel').touch()
        return {'ok': True}

    @app.get('/api/jobs/{ident}/files/{name}')
    def download(ident: str, name: str):
        path = folder('jobs', ident)
        record = status(path)
        entry = next((x for x in record['files'] if x['name'] == name), None)
        if not entry or Path(name).name != name or '/' in name or '\\' in name or not (path / name).is_file():
            raise HTTPException(404, 'This file has not been released.')
        return FileResponse(path / name, filename=name, media_type='application/octet-stream')

    @app.delete('/api/uploads/{ident}')
    async def delete_upload(ident: str):
        async with mutation_lock:
            if busy():
                raise HTTPException(409, 'Stop the active job before removing files.')
            async with upload_locks.setdefault(ident, asyncio.Lock()):
                shutil.rmtree(folder('uploads', ident))
                return {'ok': True}

    @app.delete('/api/jobs/{ident}')
    async def delete_job(ident: str):
        async with mutation_lock:
            if busy():
                raise HTTPException(409, 'Stop the active job before removing files.')
            shutil.rmtree(folder('jobs', ident))
            return {'ok': True}

    @app.get('/')
    def index():
        return FileResponse(BASE / 'static/index.html')

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    app.mount('/static', StaticFiles(directory=BASE / 'static'), name='static')
    return app


def factory():
    return create_app()
