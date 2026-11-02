import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class ToiletSearchTransitionTests(unittest.TestCase):
    def replay(self, height, offset=0, door=None):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and "toilet_box['h'] >= h * 0.4" in ast.unparse(n.test))
        # Run the real condition and state change in a loop so its continue remains valid.
        loop = ast.While(test=ast.Constant(True), body=[branch, ast.Break()], orelse=[])
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        # End a taken branch after one iteration, while preserving its actual transition.
        ticks = iter((10.0, 10.0, 10.0))
        namespace = dict(toilet_box={'h': height}, h=1080, diff_x=offset,
                         valid_door_box=door, bot_state='RUNNING', stop_all=Mock(),
                         time=SimpleNamespace(time=lambda: next(ticks)), print=Mock())
        # Replace continue with break in this isolated loop; no production statements change.
        class EndIteration(ast.NodeTransformer):
            def visit_Continue(self, node):
                return ast.copy_location(ast.Break(), node)
        exec(compile(EndIteration().visit(module), '<search_transition>', 'exec'), namespace)
        return namespace

    def test_close_centered_building_without_door_starts_circling(self):
        result = self.replay(432)
        self.assertEqual(result['bot_state'], 'CIRCLING')
        result['stop_all'].assert_called_once_with()
        self.assertEqual(result['circle_start'], 10.0)

    def test_distant_building_keeps_approaching(self):
        result = self.replay(431)
        self.assertEqual(result['bot_state'], 'RUNNING')
        result['stop_all'].assert_not_called()

    def test_off_center_building_keeps_alignment(self):
        self.assertEqual(self.replay(500, offset=101)['bot_state'], 'RUNNING')

    def test_visible_door_does_not_start_building_search(self):
        self.assertEqual(self.replay(500, door={'h': 200})['bot_state'], 'RUNNING')

    def test_building_approach_releases_ctrl_but_door_approach_keeps_it(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == 'valid_door_box'
                      and 'FORCE_BRAKE' in ast.unparse(n))
        for visible_door in (False, True):
            keys = dict(w=False, ctrl=True, shift=False)
            namespace = dict(valid_door_box={'h': 200} if visible_door else None,
                             keys_pressed=keys, is_sprinting=False, last_action_log='',
                             set_key=lambda key, state: keys.update({key: state}),
                             time=SimpleNamespace(sleep=Mock()), print=Mock())
            exec(compile(ast.Module(body=[branch], type_ignores=[]), '<approach_speed>', 'exec'), namespace)
            self.assertTrue(keys['w'])
            self.assertEqual(keys['ctrl'], visible_door)
            self.assertFalse(keys['shift'])
