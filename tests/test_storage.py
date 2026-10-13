"""Disk-budget regression tests with a simulated renderer, not model validation."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.engine import create_copies
from app.storage import copy_space_bytes


class StorageTests(unittest.TestCase):
    def test_copy_budget_boundaries_and_invalid_values(self):
        self.assertEqual(copy_space_bytes(1.5), 5_000_000_000)
        for value in (float('nan'), float('inf'), 0, 101):
            with self.assertRaises(ValueError):
                copy_space_bytes(value)

    def test_disk_drop_preserves_verified_copy_and_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            source = dest/'source.mp4'
            source.write_bytes(b'neutral source fixture')
            rendered, published = [], []
            info = dict(duration=180, audio=False, width=1280, height=720,
                        input_width=1280, input_height=720, fps='24')

            class FixtureEngine:
                def detect(self, path, *args):
                    if path == source:
                        return dict(status='inconclusive')
                    return dict(status='registered_copy_recovered', aggregate=dict(copy_label='Test 001'))

                def render(self, source, target, state, label, *args):
                    rendered.append(label)
                    target.write_bytes(b'simulated checked output')

            free = [6_000_000_000, 6_000_000_000, 4_000_000_000]
            with patch('app.storage.shutil.disk_usage', side_effect=[SimpleNamespace(free=n) for n in free]), \
                 patch('app.engine.media.probe', return_value=info), \
                 patch('app.engine.media.run'):
                with self.assertRaisesRegex(ValueError, '1 of 50 copies finished.*5.00 GB.*4.00 GB'):
                    create_copies(FixtureEngine(), source, dest,
                        dict(copies=50, max_gb=1.5, label='Test'), lambda *a, **kw: None,
                        lambda name, *a: published.append(name))
            self.assertEqual(rendered, ['Test 001'])
            self.assertEqual((dest/'Test 001.mp4').read_bytes(), b'simulated checked output')
            self.assertEqual(source.read_bytes(), b'neutral source fixture')
            self.assertIn('Test 001.mp4', published)
            self.assertIn('PRIVATE-recovery.json', published)
            self.assertEqual(len(json.loads((dest/'PRIVATE-recovery.json').read_text())['copy_tokens']), 50)
            self.assertEqual(list(dest.glob('*.pending.mp4')), [])
            self.assertEqual(len(json.loads((dest/'verification.json').read_text())['copies']), 1)
