"""Bounded processing settings based on the resources actually allocated."""
import math
import os
from pathlib import Path


def cpu_budget():
    try:
        count = len(os.sched_getaffinity(0))
    except AttributeError:
        count = os.cpu_count() or 1
    # A Pod can see all host CPUs while its cgroup allows only a small fraction.
    limits = [count]
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota != 'max':
            limits.append(max(1, math.floor(int(quota) / int(period))))
    except (OSError, ValueError, ZeroDivisionError):
        pass
    for directory in ('/sys/fs/cgroup/cpu', '/sys/fs/cgroup/cpu,cpuacct'):
        try:
            quota = int(Path(directory, 'cpu.cfs_quota_us').read_text())
            period = int(Path(directory, 'cpu.cfs_period_us').read_text())
            if quota > 0:
                limits.append(max(1, math.floor(quota / period)))
        except (OSError, ValueError, ZeroDivisionError):
            pass
    return max(1, min(limits))


def bounded_setting(name, default, minimum, maximum, multiple=1):
    raw = os.environ.get(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError:
        raise ValueError(f'{name} must be a whole number.') from None
    if not minimum <= value <= maximum or value % multiple:
        raise ValueError(f'{name} must be between {minimum} and {maximum}, in steps of {multiple}.')
    return value


def encoder_threads():
    budget = cpu_budget()
    default = min(16, max(1, budget - min(4, budget // 2)))
    return min(budget, bounded_setting('WATERMARK_ENCODER_THREADS', default, 1, 64))


def frame_batch():
    # More VRAM does not imply a faster full-resolution batch: 2 outperformed
    # 8/16/32 on the H200 synthetic benchmark. Preserve even step_size=2 alignment.
    return bounded_setting('WATERMARK_BATCH_FRAMES', 2, 2, 64, multiple=2)
