"""Reserve space for one output at a time, plus temporary space and headroom."""
import math
import shutil

RESERVE_BYTES = 2_000_000_000
TEMPORARY_COPIES = 1


def copy_space_bytes(max_gb):
    if not math.isfinite(max_gb) or not .01 <= max_gb <= 100:
        raise ValueError('Maximum size must be between 0.01 and 100 GB.')
    return math.ceil(max_gb * 1_000_000_000) * (1 + TEMPORARY_COPIES) + RESERVE_BYTES


def require_copy_space(directory, max_gb, completed=0, total=None):
    required = copy_space_bytes(max_gb)
    available = shutil.disk_usage(directory).free
    if available < required:
        prefix = f'{completed} of {total} copies finished. ' if completed else ''
        action = ('Download the finished copies and PRIVATE recovery JSON before removing this batch. '
                  if completed else '')
        raise ValueError(
            f'{prefix}The next copy needs {required / 1e9:.2f} GB free '
            f'(output, temporary space and 2 GB headroom); {available / 1e9:.2f} GB is available. '
            f'{action}Free space or use a larger storage volume before starting a new batch. '
            'Finished copies are preserved; unfinished copies do not resume automatically.')
