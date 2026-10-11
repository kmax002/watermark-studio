"""Bounded local media processing, with no remote input protocols."""
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import subprocess
import threading
import time

STOP = threading.Event()
PROCESSES = set()
GUARD = threading.Lock()


class Cancelled(Exception):
    pass


def check_stop():
    if STOP.is_set():
        raise Cancelled('Stopped. Already verified downloads are preserved.')


def stop_all():
    STOP.set()
    with GUARD:
        for p in list(PROCESSES):
            if p.poll() is None:
                p.terminate()


def spawn(args, **kwargs):
    check_stop()
    with GUARD:
        check_stop()
        p = subprocess.Popen(args, **kwargs)
        PROCESSES.add(p)
    return p


def dispose(p):
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
    with GUARD:
        PROCESSES.discard(p)


def run(args, timeout=120):
    p = spawn(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(timeout=timeout)
        check_stop()
        if p.returncode:
            raise ValueError('Video processing failed. Check the file format and available disk space.')
        return out
    finally:
        dispose(p)


def input_args(path):
    # file/pipe only: uploaded playlists cannot request HTTP, TCP, crypto, etc.
    return ['-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,matroska,webm,avi,mpegts', '-i', str(Path(path).resolve())]


def probe(path):
    data = json.loads(run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,matroska,webm,avi,mpegts',
        '-show_streams', '-show_format', '-of', 'json', str(path)]))
    streams = [s for s in data['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if len(streams) != 1:
        raise ValueError('Choose a file with one video track.')
    v = streams[0]
    if v.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
        raise ValueError('Export an SDR version first. HDR is not supported in this version.')
    if any(abs(float(s.get('rotation', 0))) % 360 for s in v.get('side_data_list', [])):
        raise ValueError('Export with rotation applied to the pixels first.')
    if v.get('sample_aspect_ratio', '1:1') not in ('1:1', '0:1', 'N/A'):
        raise ValueError('Export square pixels first.')
    w, h = int(v['width']), int(v['height'])
    duration = float(v.get('duration') or data['format'].get('duration', 0))
    try:
        fps = Fraction(v.get('avg_frame_rate') or v['r_frame_rate'])
    except (ValueError, ZeroDivisionError):
        raise ValueError('The frame rate could not be read.') from None
    if not math.isfinite(duration) or not 4 <= duration <= 14400 or not 1 <= fps <= 120:
        raise ValueError('Use a video from 4 seconds to 4 hours, at 1 to 120 fps.')
    if not (256 <= w <= 3840 and 256 <= h <= 3840) or w % 2 or h % 2:
        raise ValueError('Use even frame dimensions, from 256 to 3840 pixels.')
    scale = min(1, 1920 / max(w, h))
    return dict(width=int(w * scale) // 2 * 2, height=int(h * scale) // 2 * 2,
        input_width=w, input_height=h, duration=duration, fps=str(fps),
        frames=round(duration * float(fps)), audio=any(s['codec_type'] == 'audio' for s in data['streams']))


def read_exact(stream, n):
    parts = bytearray()
    while len(parts) < n:
        check_stop()
        chunk = stream.read(n - len(parts))
        if not chunk:
            break
        parts.extend(chunk)
    return bytes(parts)


def frames(path, width, height, fps, start=0, seconds=None, batch=2):
    import numpy as np
    args = ['ffmpeg', '-v', 'error', '-nostdin', '-threads', '2', '-filter_threads', '2', '-ss', str(start)] + input_args(path)
    if seconds is not None:
        args += ['-t', str(seconds)]
    args += ['-map', '0:v:0', '-an', '-sn', '-dn', '-vf', f'fps={fps},scale={width}:{height}:flags=bicubic',
             '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1']
    p = spawn(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    timer = threading.Timer(max(120, (seconds or 14400) * 20), p.terminate)
    timer.start()
    try:
        size = width * height * 3
        while True:
            raw = read_exact(p.stdout, size * batch)
            if not raw:
                break
            if len(raw) % size:
                raise ValueError('An incomplete video frame was decoded.')
            yield np.frombuffer(raw, 'uint8').reshape(-1, height, width, 3).copy()
        if p.wait(timeout=30):
            check_stop()
            raise ValueError('Video decoding failed or timed out.')
    finally:
        timer.cancel()
        p.stdout.close()
        dispose(p)

