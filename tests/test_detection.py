"""A fixed sampling phase must not discard the stronger watermark evidence."""
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import torch

from app.engine import Engine
from app.payload import encode, assess_frames
from app.records import new_register


class DetectionTests(unittest.TestCase):
    def test_native_detection_recovers_temporally_uneven_signal(self):
        state = new_register('ab' * 32, 1, 'Neutral', dict(width=256, height=256, fps='24'))
        token = next(iter(state['copy_tokens'].values()))
        key = bytes.fromhex(state['key_hex'])
        strong = encode(token, key, state['source_sha256']).astype(np.float32) * 16 - 8
        weak = strong.copy()
        weak[:28] *= -1
        # A 6 fps phase can repeatedly select the same weak frame of each four.
        sampled = np.tile(weak, (72, 1))
        self.assertEqual(assess_frames(sampled, key, state['source_sha256'], {token})['status'], 'inconclusive')

        class Detector:
            def detect(self, x, **kwargs):
                phases = (x[:, 0, 0, 0] * 255).round().int().tolist()
                scores = np.stack([weak if phase == 2 else strong for phase in phases])
                preds = np.concatenate([np.zeros((len(scores), 1)), scores], axis=1)
                return {'preds': torch.tensor(preds[:, :, None, None])}

        def frames(path, width, height, fps, start, seconds, batch):
            indices = range(288) if fps is None else range(2, 288, 4)
            values = [np.full((2, 2, 3), i % 4, dtype=np.uint8) for i in indices]
            for i in range(0, len(values), batch):
                yield np.stack(values[i:i + batch])

        engine = Engine.__new__(Engine)
        engine.device, engine.batch, engine.model = 'cpu', 2, Detector()
        with patch('app.engine.media.frames', frames):
            result = engine.detect(Path('neutral.mp4'), state, 0, 12)
        self.assertEqual(result['status'], 'registered_copy_recovered')
        self.assertEqual(result['frames'], 288)
        self.assertEqual(result['aggregate']['copy_label'], 'Neutral 001')
        self.assertTrue(all(x['copy_label'] == 'Neutral 001' for x in result['disjoint_halves']))
        self.assertEqual(result['frame_sampling'], 'all_native_frames')
