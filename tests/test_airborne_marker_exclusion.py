import ast
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

import cv2
import numpy as np


class AirborneMarkerExclusionTests(unittest.TestCase):
    def locate(self, circles, exclude=None):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'core/mixins.py').read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'find_user_on_map')
        namespace = dict(cv2=cv2, np=np, math=math)
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<map_vision>', 'exec'), namespace)
        frame = np.zeros((1050, 1050, 3), dtype=np.uint8)
        for position in circles:
            cv2.circle(frame, position, 7, (0, 255, 255), -1)
        controller = SimpleNamespace(find_image_in_map=lambda *args: (False, .1, None))
        return namespace['find_user_on_map'](controller, frame, exclude_position=exclude)

    def test_reported_marker_offset_cannot_be_used_as_plane(self):
        found, position, _, source = self.locate([(625, 521)], (625, 533))
        self.assertFalse(found)
        self.assertIsNone(position)
        self.assertEqual(source, 'excluded_target')

    def test_skips_marker_and_continues_searching_for_plane(self):
        found, position, _, source = self.locate([(625, 521), (986, 300)], (625, 533))
        self.assertTrue(found)
        self.assertEqual(position, (986, 300))
        self.assertEqual(source, 'color_logic')

    def test_without_exclusion_original_behavior_is_preserved(self):
        found, position, _, _ = self.locate([(625, 521)])
        self.assertTrue(found)
        self.assertEqual(position, (625, 521))

    def test_distant_plane_is_not_excluded(self):
        found, position, _, _ = self.locate([(725, 566)], (625, 533))
        self.assertTrue(found)
        self.assertEqual(position, (725, 566))
