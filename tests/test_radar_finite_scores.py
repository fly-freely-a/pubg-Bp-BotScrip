import ast
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import cv2
import numpy as np


class RadarFiniteScoreTests(unittest.TestCase):
    def measure(self, results):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'get_radar_distance')
        controller = SimpleNamespace(mm_size_adjust=0, mm_offset_x=0, mm_offset_y=0,
                                     radar_templates=[dict(template=np.zeros((2, 2, 3), np.uint8), mask=None)
                                                      for _ in results])
        namespace = dict(math=math, np=np, cv2=SimpleNamespace(
            matchTemplate=Mock(side_effect=[r.copy() for r in results]),
            minMaxLoc=cv2.minMaxLoc, TM_CCOEFF_NORMED=cv2.TM_CCOEFF_NORMED))
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<radar>', 'exec'), namespace)
        distance = namespace['get_radar_distance'](controller, np.zeros((200, 200, 3), np.uint8), reject_nonfinite=True)
        return distance, controller.last_radar_diagnostic

    def test_inf_does_not_hide_valid_match_in_same_result(self):
        result = np.zeros((83, 83), np.float32)
        result[2, 2] = np.inf
        result[40, 40] = .65
        distance, diagnostic = self.measure([result])
        self.assertAlmostEqual(distance, math.sqrt(2))
        self.assertEqual(diagnostic['matched_target'], (41, 41))
        self.assertAlmostEqual(diagnostic['score'], .65, places=5)

    def test_all_nonfinite_scores_return_no_distance(self):
        for value in (np.inf, -np.inf, np.nan):
            with self.subTest(value=value):
                distance, diagnostic = self.measure([np.full((83, 83), value, np.float32)])
                self.assertIsNone(distance)
                self.assertFalse(diagnostic['accepted'])
                self.assertTrue(math.isfinite(diagnostic['score']))

    def test_best_finite_match_can_come_from_another_template(self):
        invalid = np.full((83, 83), np.inf, np.float32)
        valid = np.zeros((83, 83), np.float32)
        valid[40, 40] = .8
        distance, diagnostic = self.measure([invalid, valid])
        self.assertAlmostEqual(distance, math.sqrt(2))
        self.assertAlmostEqual(diagnostic['score'], .8, places=5)
