"""Real FFmpeg checks for bounded frame prefetch, ordering and early close."""
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import numpy as np

from app import media


class FrameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / 'neutral.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=256x256:rate=7:duration=1', '-c:v', 'libx264', '-threads', '1',
            '-pix_fmt', 'yuv420p', str(self.source)], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_batched_prefetch_preserves_order_and_short_final_batch(self):
        small = list(media.frames(self.source, 256, 256, 7, batch=2))
        large = list(media.frames(self.source, 256, 256, 7, batch=4))
        self.assertEqual([len(x) for x in large], [4, 3])
        self.assertTrue(np.array_equal(np.concatenate(small), np.concatenate(large)))
        self.assertFalse(media.PROCESSES)

    def test_early_close_stops_decoder_and_reader(self):
        frames = media.frames(self.source, 256, 256, 7, batch=2)
        self.assertEqual(len(next(frames)), 2)
        frames.close()
        self.assertFalse(media.PROCESSES)
        self.assertFalse(any(t.name == 'watermark-frame-reader' for t in threading.enumerate()))

    def test_native_frames_are_not_dropped_or_duplicated(self):
        native = np.concatenate(list(media.frames(self.source, 256, 256, None, batch=2)))
        expected = np.concatenate(list(media.frames(self.source, 256, 256, 7, batch=2)))
        sampled = np.concatenate(list(media.frames(self.source, 256, 256, 6, batch=2)))
        self.assertEqual(len(native), 7)
        self.assertEqual(len(sampled), 6)
        self.assertTrue(np.array_equal(native, expected))
        # Native 1 fps remains four real frames, not 24 resampled duplicates.
        slow = Path(self.temp.name) / 'slow.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=256x256:rate=1:duration=4', '-c:v', 'libx264', '-threads', '1',
            '-pix_fmt', 'yuv420p', str(slow)], check=True)
        self.assertEqual(sum(len(x) for x in media.frames(slow, 256, 256, None, batch=2)), 4)

    def test_decoder_failure_reaches_consumer(self):
        self.source.write_bytes(b'not a video')
        with self.assertRaisesRegex(ValueError, 'Video decoding failed'):
            list(media.frames(self.source, 256, 256, 7, batch=2))
        self.assertFalse(media.PROCESSES)
