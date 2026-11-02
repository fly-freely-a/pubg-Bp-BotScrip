import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class NearDoorMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        self.namespace = dict(bot_state='APPROACH_DOOR', centered_door_count=0,
                              near_door_memory=False, center_x=960, h=1080)
        self.tracking = next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                             and ast.unparse(n.test) == "bot_state != 'APPROACH_DOOR'")

    def observe(self, x=960, height=300, visible=True):
        self.namespace['valid_door_box'] = dict(x=x, h=height) if visible else None
        exec(compile(ast.Module(body=[self.tracking], type_ignores=[]), '<tracking>', 'exec'), self.namespace)

    def test_requires_three_close_centered_observations(self):
        for expected in (False, False, True):
            self.observe()
            self.assertEqual(self.namespace['near_door_memory'], expected)
        self.observe(visible=False)
        self.assertTrue(self.namespace['near_door_memory'])

    def test_off_center_or_distant_observation_clears_memory(self):
        for x, height in ((1041, 300), (960, 215)):
            for _ in range(3):
                self.observe()
            self.observe(x, height)
            self.assertFalse(self.namespace['near_door_memory'])

    def test_leaving_approach_clears_memory(self):
        for _ in range(3):
            self.observe()
        self.namespace['bot_state'] = 'COMPASS_RUSH'
        self.observe()
        self.assertFalse(self.namespace['near_door_memory'])

    def test_memory_forward_stops_after_each_half_second_and_limits_to_four_steps(self):
        branch = copy.deepcopy(next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                                    and ast.unparse(n.test) == 'near_door_memory and memory_forward_steps < 4'))
        branch.orelse = []
        class EndIteration(ast.NodeTransformer):
            def visit_Continue(self, node):
                return ast.copy_location(ast.Break(), node)
        module = ast.fix_missing_locations(ast.Module(body=[ast.While(
            test=ast.Constant(True), body=[EndIteration().visit(branch), ast.Break()], orelse=[])],
            type_ignores=[]))
        keys, stop, sleep = Mock(), Mock(), Mock()
        namespace = dict(near_door_memory=True, memory_forward_steps=0, set_key=keys,
                         stop_all=stop, time=SimpleNamespace(time=lambda: 10,
                         perf_counter=lambda: 0, sleep=sleep), last_action_log='', print=Mock())
        for expected in range(1, 5):
            exec(compile(module, '<memory_step>', 'exec'), namespace)
            self.assertEqual(namespace['memory_forward_steps'], expected)
            self.assertEqual(stop.call_count, expected * 2)
            sleep.assert_called_with(0.5)
        exec(compile(module, '<memory_step>', 'exec'), namespace)
        self.assertEqual(namespace['memory_forward_steps'], 4)
        self.assertEqual(sleep.call_count, 4)
        self.assertEqual(keys.call_count, 8)
