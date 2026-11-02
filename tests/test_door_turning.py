import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class DoorTurningTests(unittest.TestCase):
    def turn(self, offset):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'smooth_glide_mouse')
        # Preserve the real closure, including its nonlocal diagnostic timestamp.
        factory = 'def build():\n    last_turn_diagnostic = 0.0\n'
        factory += '\n'.join('    ' + line for line in ast.unparse(method).splitlines())
        factory += '\n    return smooth_glide_mouse\n'
        movements = []
        namespace = dict(win32api=SimpleNamespace(mouse_event=lambda flags, x, *args: movements.append(x)),
                         win32con=SimpleNamespace(MOUSEEVENTF_MOVE=1),
                         time=SimpleNamespace(perf_counter=lambda: 2.0), print=Mock())
        exec(factory, namespace)
        namespace['build']()(offset)
        return movements

    def test_actual_displacement_matches_capped_calculation_in_both_directions(self):
        for offset in (20, -20, 22.5, -22.5, 85.5, -112.5, 199.5, -10000, 10000):
            with self.subTest(offset=offset):
                steps = self.turn(offset)
                expected = max(-80, min(80, int(offset * .4)))
                self.assertEqual(sum(steps), expected)
                self.assertTrue(all(0 < abs(step) <= 3 for step in steps))

    def test_dead_zone_does_not_move_mouse(self):
        for offset in (0, 19.9, -19.9):
            self.assertEqual(self.turn(offset), [])

    def test_remainder_is_not_lost(self):
        steps = self.turn(85.5)  # int(85.5 * .4) == 34
        self.assertEqual(steps, [3] * 11 + [1])
