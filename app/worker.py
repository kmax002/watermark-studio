"""One isolated worker per job. Parent exit or cancellation stops owned processes."""
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
import psutil

from . import media
from .records import save


def main(folder):
    folder = Path(folder).resolve()
    job = json.loads((folder / 'request.json').read_text(encoding='utf8'))
    status = json.loads((folder / 'status.json').read_text(encoding='utf8'))
    def progress(phase, **extra):
        media.check_stop()
        status.update(phase=phase, updated=time.time(), **extra)
        save(folder / 'status.json', status)
    def publish(filename, label, kind):
        media.check_stop()
        status['files'].append(dict(name=filename, label=label, kind=kind))
        save(folder / 'status.json', status)
    def watch():
        began = time.monotonic()
        while not media.STOP.wait(.5):
            try:
                owner = psutil.Process(job['owner_pid'])
                owner_alive = owner.is_running() and owner.create_time() == job['owner_created']
            except psutil.Error:
                owner_alive = False
            if not owner_alive or (folder / 'cancel').exists() or time.monotonic() - began > 86400:
                media.stop_all()
    threading.Thread(target=watch, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: media.stop_all())
    try:
        progress('Loading PixelSeal')
        from .engine import Engine, create_copies, check_leak
        engine = Engine()
        if job['kind'] == 'create':
            result = create_copies(engine, Path(job['video']), folder, job['options'], progress, publish)
        else:
            result = check_leak(engine, Path(job['video']), Path(job['recovery']), folder, job['options'], progress, publish)
        media.check_stop()
        status.update(status='complete', phase='Finished', result=result)
    except media.Cancelled:
        status.update(status='cancelled', phase='Stopped', error='Already verified downloads are preserved. Start a new batch to process again.')
    except ValueError as exc:
        status.update(status='cancelled' if media.STOP.is_set() else 'failed', phase='Stopped',
                      error='Processing was stopped. Verified downloads are preserved.' if media.STOP.is_set() else str(exc))
    except Exception:
        status.update(status='cancelled' if media.STOP.is_set() else 'failed', phase='Stopped',
                      error='Processing was stopped. Verified downloads are preserved.' if media.STOP.is_set() else 'Processing failed. Check GPU memory, dependencies and free storage. No automatic retry was made.')
    finally:
        media.stop_all()
        status['updated'] = time.time()
        save(folder / 'status.json', status)


if __name__ == '__main__':
    main(sys.argv[1])

