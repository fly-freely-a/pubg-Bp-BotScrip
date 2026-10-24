from pathlib import Path
import ast
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import cv2
import numpy as np

from core.interaction import InteractionPromptMatcher


class InteractionPromptTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'image' / 'F.png'
        self.template = cv2.imread(str(path))
        self.assertIsNotNone(self.template)

    def test_prompt_at_different_sizes(self):
        matcher = InteractionPromptMatcher(self.template)
        for scale in (0.75, 1.0, 1.5, 2.0):
            with self.subTest(scale=scale):
                icon = cv2.resize(self.template, None, fx=scale, fy=scale)
                frame = np.random.default_rng(42).integers(
                    0, 80, (300, 500, 3), dtype=np.uint8)
                h, w = icon.shape[:2]
                frame[140:140+h, 270:270+w] = icon
                score, box, matched_scale = matcher.match(frame)
                self.assertGreater(score, 0.72)
                self.assertEqual(box, (270, 140, w, h))
                self.assertEqual(matched_scale, scale)

    def test_absent_prompt_does_not_match(self):
        frame = np.random.default_rng(42).integers(
            0, 255, (300, 500, 3), dtype=np.uint8)
        score, _, _ = InteractionPromptMatcher(self.template).match(frame)
        self.assertLess(score, 0.72)

    def test_empty_frame(self):
        self.assertEqual(InteractionPromptMatcher(self.template).match(None),
                         (0.0, None, None))

    def test_missing_template_fails_explicitly(self):
        with self.assertRaises(ValueError):
            InteractionPromptMatcher(None)

    def test_real_interaction_gate_stops_before_verification(self):
        source = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                        and n.name == 'start_auto_run')
        gate = next(n for n in ast.walk(function) if isinstance(n, ast.If)
                    and any(isinstance(a, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == 'ignore_f'
                                    for t in a.targets) for a in n.body))
        # Execute the actual loop gate, including its continue, without Windows.
        loop = ast.For(target=ast.Name(id='_', ctx=ast.Store()),
                       iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                       body=[gate], orelse=[])
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        for score, door_age, expected in ((0.95, 0.1, True),
                                         (0.95, 2.0, False),
                                         (0.38, 0.1, False)):
            with self.subTest(score=score, door_age=door_age):
                stop = Mock()
                namespace = dict(bot_state='APPROACH_DOOR',
                                 time=SimpleNamespace(time=lambda: 100.0),
                                 global_last_door_time=100.0-door_age,
                                 has_aligned_door=False, current_f_score=score,
                                 last_entry_alignment=None,
                                 f_threshold=0.72, last_prompt_log=100.0,
                                 self=SimpleNamespace(door_height_reached=False),
                                 stop_all=stop)
                exec(compile(module, str(source), 'exec'), namespace)
                self.assertEqual(namespace['bot_state'] == 'VERIFY_DOOR', expected)
                self.assertEqual(stop.called, expected)


if __name__ == '__main__':
    unittest.main()
