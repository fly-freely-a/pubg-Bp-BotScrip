from pathlib import Path
import unittest

import cv2
import numpy as np

from core.matchmaking import QueuePromptMatcher


class QueuePromptTests(unittest.TestCase):
    def test_queue_label_survives_changing_timer_and_image_scale(self):
        path = Path(__file__).resolve().parents[1] / 'image' / 'start_matching.png'
        template = cv2.imread(str(path))
        self.assertIsNotNone(template)
        matcher = QueuePromptMatcher(template)
        changed = template.copy()
        h, w = changed.shape[:2]
        changed[:, :int(w * 0.25)] = 0
        changed[:, int(w * 0.70):] = 0
        for scale in (0.25, 0.5, 0.75, 1.0):
            with self.subTest(scale=scale):
                panel = cv2.resize(changed, None, fx=scale, fy=scale)
                frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
                ph, pw = panel.shape[:2]
                frame[800:800+ph, 50:50+pw] = panel
                score, _, _ = matcher.match(frame)
                self.assertGreaterEqual(score, 0.80)

    def test_missing_template_fails(self):
        with self.assertRaises(ValueError):
            QueuePromptMatcher(None)

    def test_blank_frame_is_not_queue(self):
        path = Path(__file__).resolve().parents[1] / 'image' / 'start_matching.png'
        matcher = QueuePromptMatcher(cv2.imread(str(path)))
        score, _, _ = matcher.match(np.zeros((1080, 1920, 3), dtype=np.uint8))
        self.assertLess(score, 0.80)
