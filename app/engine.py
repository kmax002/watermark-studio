"""PixelSeal engine. Fresh keys per batch; exact pinned checkpoint only."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
import torch

from . import media
from .payload import encode, assess_frames
from .records import CHECKPOINT, new_register, validate_register, sha256, save, verification_windows, bitrate_for_limit


class Engine:
    def __init__(self):
        repo = Path(os.environ.get('VIDEOSEAL_REPO', '/opt/videoseal')).resolve()
        checkpoint = repo / 'ckpts/pixelseal_checkpoint.pth'
        if not checkpoint.is_file() or sha256(checkpoint) != CHECKPOINT:
            raise ValueError('The pinned PixelSeal model is missing or damaged. Rebuild the container.')
        self.device = os.environ.get('WATERMARK_DEVICE', 'cuda')
        if self.device not in ('cuda', 'cpu'):
            raise ValueError('Unsupported processing device.')
        if self.device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('No CUDA GPU is available. Start this template on an NVIDIA GPU Pod.')
        sys.path.insert(0, str(repo))
        from omegaconf import OmegaConf
        from videoseal.utils.cfg import setup_model
        before = Path.cwd()
        try:
            os.chdir(repo)
            torch.set_num_threads(4)
            self.model = setup_model(OmegaConf.load(repo / 'videoseal/cards/pixelseal.yaml'), checkpoint).eval().to(self.device)
        finally:
            os.chdir(before)
        self.model.step_size = 2
        self.model.blender.scaling_w = .2
        self.batch = 2

    def detect(self, path, state, start=0, seconds=30):
        values = []
        s = state['settings']
        for arr in media.frames(path, s['width'], s['height'], 6, start, seconds, self.batch):
            media.check_stop()
            x = torch.from_numpy(arr).permute(0, 3, 1, 2).float().to(self.device) / 255
            with torch.inference_mode():
                prediction = self.model.detect(x, is_video=True)['preds'].float().cpu().numpy()
            values.append(prediction.reshape(len(arr), 257, -1).mean(-1)[:, 1:])
        if not values:
            raise ValueError('No frames were available at that starting time.')
        result = assess_frames(np.concatenate(values), bytes.fromhex(state['key_hex']), state['source_sha256'], set(state['copy_tokens'].values()))
        reverse = {v: k for k, v in state['copy_tokens'].items()}
        for item in [result.get('aggregate', {}), *result.get('disjoint_halves', [])]:
            if 'copy_token' in item:
                item['copy_label'] = reverse[item.pop('copy_token')]
        return result

    def render(self, source, target, state, label, info, rate, progress):
        msg = torch.tensor(encode(state['copy_tokens'][label], bytes.fromhex(state['key_hex']), state['source_sha256']),
                           dtype=torch.float32, device=self.device).unsqueeze(0)
        w, h = info['width'], info['height']
        args = ['ffmpeg', '-v', 'error', '-n', '-filter_threads', '2', '-thread_queue_size', '16',
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-video_size', f'{w}x{h}', '-framerate', info['fps'], '-i', 'pipe:0']
        args += media.input_args(source)
        args += ['-t', str(info['duration']), '-map', '0:v:0', '-map', '1:a:0?', '-map_metadata', '-1', '-map_chapters', '-1',
            '-vf', 'scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p',
            '-c:v', 'libx264', '-preset', 'medium', '-threads', '4', '-crf', '18',
            '-maxrate', str(rate), '-bufsize', str(rate * 2), '-color_range', 'tv', '-colorspace', 'bt709',
            '-color_trc', 'bt709', '-color_primaries', 'bt709', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(target)]
        p = media.spawn(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        count = 0
        last = 0
        iterator = media.frames(source, w, h, info['fps'], seconds=info['duration'], batch=self.batch)
        try:
            for arr in iterator:
                media.check_stop()
                x = torch.from_numpy(arr).permute(0, 3, 1, 2).float().to(self.device) / 255
                with torch.inference_mode():
                    y = self.model.embed(x, msgs=msg, is_video=True, lowres_attenuation=False)['imgs_w']
                    raw = y.mul(255).round().clamp(0, 255).byte().permute(0, 2, 3, 1).contiguous().cpu().numpy().tobytes()
                p.stdin.write(raw)
                count += len(arr)
                if time.monotonic() - last > 1:
                    progress(f'Watermarking {label}', frames=count, total_frames=info['frames'])
                    last = time.monotonic()
            p.stdin.close()
            if p.wait(timeout=180):
                raise ValueError('Encoding did not finish. Check free disk space.')
            if abs(count - info['frames']) > 2:
                raise ValueError('Decoded duration does not match the source. Export a constant-frame-rate source.')
        finally:
            iterator.close()
            if not p.stdin.closed:
                p.stdin.close()
            media.dispose(p)


def create_copies(engine, source, dest, options, progress, publish):
    info = media.probe(source)
    source_hash = sha256(source)
    rate = bitrate_for_limit(options['max_gb'], info['duration'], info['audio'])
    required = options['max_gb'] * 1e9 * (options['copies'] + 1) + 2e9
    if shutil.disk_usage(dest).free < required:
        raise ValueError('Not enough free disk space for this batch and its size limit. Use fewer copies or more storage.')
    state = new_register(source_hash, options['copies'], options['label'], info)
    recovery = dest / 'PRIVATE-recovery.json'
    save(recovery, state)
    publish(recovery.name, 'Private recovery file', 'private')
    with (dest / 'PRIVATE-recipients.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Copy', 'Recipient', 'Date sent', 'Notes'])
        writer.writerows([label, '', '', ''] for label in state['copy_tokens'])
    publish('PRIVATE-recipients.csv', 'Private recipient log', 'private')
    reports = []
    progress('Checking the unmarked source', copy=0, total=options['copies'])
    control = engine.detect(source, state, 0, min(12, info['duration']))
    if control['status'] != 'inconclusive':
        raise ValueError('Source control unexpectedly matched. This batch was stopped.')
    for index, label in enumerate(state['copy_tokens'], 1):
        media.check_stop()
        progress(f'Starting {label}', copy=index, total=options['copies'])
        target = dest / f'{label}.pending.mp4'
        final = dest / f'{label}.mp4'
        try:
            engine.render(source, target, state, label, info, rate, progress)
            progress(f'Checking the complete video: {label}', frames=0, total_frames=0)
            if target.stat().st_size > options['max_gb'] * 1e9:
                raise ValueError('Encoded copy exceeds the size limit and was withheld. Try a larger limit.')
            output = media.probe(target)
            if (output['input_width'], output['input_height']) != (info['width'], info['height']) or abs(output['duration'] - info['duration']) > max(.25, 2 / float(__import__('fractions').Fraction(info['fps']))):
                raise ValueError('Output dimensions or duration changed unexpectedly.')
            if output['audio'] != info['audio']:
                raise ValueError('Expected audio track is missing.')
            media.run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '2'] + media.input_args(target) + ['-f', 'null', '-'], timeout=max(120, info['duration'] * 3))
            windows = []
            for start, seconds in verification_windows(info['duration']):
                progress(f'Checking watermark: {label}', checked_windows=len(windows), total_windows=len(verification_windows(info['duration'])))
                result = engine.detect(target, state, start, seconds)
                windows.append(dict(start=start, seconds=seconds, result=result))
                if result['status'] != 'registered_copy_recovered' or result['aggregate']['copy_label'] != label:
                    save(dest / 'verification-failed.json', dict(copy=label, windows=windows))
                    raise ValueError('A copy did not pass watermark recovery and was withheld. Try a higher size limit or another source.')
            if sha256(source) != source_hash:
                raise ValueError('Source changed during processing.')
            report = dict(copy=label, sha256=sha256(target), bytes=target.stat().st_size, windows=windows,
                          full_decode_passed=True, audio='First track converted to AAC 192 kbps' if info['audio'] else 'No source audio')
            target.rename(final)
            reports.append(report)
            save(dest / 'verification.json', dict(complete=False, copies=reports, source_sha256=source_hash))
            publish(final.name, label, 'video')
        finally:
            target.unlink(missing_ok=True)
    save(dest / 'verification.json', dict(complete=True, copies=reports, source_sha256=source_hash,
        limits='Sampled recovery checks do not prove resistance to every recording, crop or compression. A copy ID is not a person.'))
    publish('verification.json', 'Verification report', 'report')
    return dict(copies=len(reports), message='Every released copy passed its recovery checks.')


def check_leak(engine, source, recovery, dest, options, progress, publish):
    state = validate_register(json.loads(recovery.read_text(encoding='utf8')))
    source_hash, key_hash = sha256(source), sha256(recovery)
    info = media.probe(source)
    if options['start'] + options['seconds'] > info['duration'] + .05:
        raise ValueError('That window extends beyond the video. Choose an earlier time or a shorter window.')
    progress('Reading the watermark from the selected window')
    result = engine.detect(source, state, options['start'], options['seconds'])
    if sha256(source) != source_hash or sha256(recovery) != key_hash:
        raise ValueError('The evidence changed during the check.')
    save(dest / 'leak-report.json', dict(candidate_sha256=source_hash, recovery_sha256=key_hash,
        start=options['start'], seconds=options['seconds'], result=result,
        limits='Identifies an issued payload, not a person. Inconclusive does not establish absence.'))
    publish('leak-report.json', 'Download check report', 'report')
    return result
