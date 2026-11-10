"""Allocation limits and unchanged frame normalization for the GPU path."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import torch

from app.engine import Engine
from app.performance import cpu_budget, encoder_threads, frame_batch


class PerformanceTests(unittest.TestCase):
    def test_container_quota_beats_host_cpu_count(self):
        def read(path, *args, **kwargs):
            values = {'/sys/fs/cgroup/cpu.max': '2040000 100000'}
            if path.as_posix() in values:
                return values[path.as_posix()]
            raise FileNotFoundError
        with patch('os.sched_getaffinity', return_value=set(range(192)), create=True), patch.object(Path, 'read_text', read):
            self.assertEqual(cpu_budget(), 20)
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(encoder_threads(), 16)

    def test_v1_quota_and_small_allocations(self):
        def read(path, *args, **kwargs):
            values = {'/sys/fs/cgroup/cpu/cpu.cfs_quota_us': '250000',
                      '/sys/fs/cgroup/cpu/cpu.cfs_period_us': '100000'}
            if path.as_posix() in values:
                return values[path.as_posix()]
            raise FileNotFoundError
        with patch('os.sched_getaffinity', return_value=set(range(64)), create=True), patch.object(Path, 'read_text', read):
            self.assertEqual(cpu_budget(), 2)
            with patch.dict(os.environ, {'WATERMARK_ENCODER_THREADS': '16'}, clear=True):
                self.assertEqual(encoder_threads(), 2)

    def test_batches_keep_even_frame_boundaries(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(frame_batch(), 2)
        with patch.dict(os.environ, {'WATERMARK_BATCH_FRAMES': '16'}):
            self.assertEqual(frame_batch(), 16)
        for invalid in ('0', '3', '66', '2.5', 'nan'):
            with patch.dict(os.environ, {'WATERMARK_BATCH_FRAMES': invalid}), self.assertRaises(ValueError):
                frame_batch()

    def test_normalization_keeps_pixels_and_order(self):
        arr = np.random.default_rng(7).integers(0, 256, (5, 8, 10, 3), dtype=np.uint8)
        engine = Engine.__new__(Engine)
        engine.device = 'cpu'
        expected = torch.from_numpy(arr).permute(0, 3, 1, 2).float() / 255
        self.assertTrue(torch.equal(engine.tensor(arr), expected))


if __name__ == '__main__':
    unittest.main()
