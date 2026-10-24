import json
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from core.door_diagnostics import DoorDiagnosticRecorder


class DoorDiagnosticTests(unittest.TestCase):
    def test_same_timestamp_does_not_overwrite_and_metadata_matches_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = DoorDiagnosticRecorder(directory)
            frame = np.zeros((20, 30, 3), dtype=np.uint8)
            metadata = dict(captured_at=1792843570.123456, f_score=0.38)
            self.assertTrue(recorder.submit(frame, metadata))
            frame[:] = 255  # 保存任务必须使用提交时的画面副本。
            recorder.pending.result(timeout=5)
            self.assertTrue(recorder.submit(frame, dict(metadata, f_score=0.8)))
            recorder.close()
            paths = list(Path(directory).glob('*.json'))
            self.assertEqual(len(paths), 2)
            self.assertEqual(len(list(Path(directory).glob('*.png'))), 2)
            for path in paths:
                self.assertRegex(path.stem, r'^\d{8}_\d{6}_\d{6}_[0-9a-f]{8}$')
                saved = json.loads(path.read_text())
                image = cv2.imread(str(Path(directory) / saved['image_file']))
                expected = 0 if saved['f_score'] == 0.38 else 255
                self.assertTrue(np.all(image == expected))

    def test_busy_writer_skips_frames_instead_of_building_backlog(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = DoorDiagnosticRecorder(directory)
            release = Event()
            try:
                with patch.object(recorder, '_save', side_effect=lambda *_: release.wait(2)):
                    frame = np.zeros((10, 10, 3), dtype=np.uint8)
                    self.assertTrue(recorder.submit(frame, {'captured_at': 1}))
                    self.assertFalse(recorder.submit(frame, {'captured_at': 2}))
                    release.set()
            finally:
                release.set()
                recorder.close()
