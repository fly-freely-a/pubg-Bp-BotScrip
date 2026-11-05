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
                                    and ast.unparse(n.test) == 'memory_forward_steps < step_limit'))
        branch.orelse = []
        class EndIteration(ast.NodeTransformer):
            def visit_Continue(self, node):
                return ast.copy_location(ast.Break(), node)
        module = ast.fix_missing_locations(ast.Module(body=[ast.While(
            test=ast.Constant(True), body=[EndIteration().visit(branch), ast.Break()], orelse=[])],
            type_ignores=[]))
        keys, stop, sleep = Mock(), Mock(), Mock()
        namespace = dict(step_limit=4, memory_forward_steps=0, set_key=keys,
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

    def test_only_centered_last_frame_allows_one_step_without_close_history(self):
        limit = next(n for n in ast.walk(self.tree) if isinstance(n, ast.Assign)
                     and ast.unparse(n.targets[0]) == 'step_limit')
        module = compile(ast.Module(body=[limit], type_ignores=[]), '<step_limit>', 'exec')
        for x, expected in ((936, 1), (838.5, 0)):
            self.observe(x=x, height=169.5)
            self.observe(visible=False)
            exec(module, self.namespace)
            self.assertEqual(self.namespace['step_limit'], expected)

    def test_first_door_detection_reaches_approach_in_same_iteration(self):
        handoff = next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                       and n.body and '[视觉接管]' in ast.unparse(n.body[0]))
        reached = ast.Assign(targets=[ast.Name(id='reached', ctx=ast.Store())], value=ast.Constant(True))
        module = ast.fix_missing_locations(ast.Module(body=[ast.For(
            target=ast.Name(id='_', ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[handoff, reached], orelse=[])], type_ignores=[]))
        for state in ('COMPASS_RUSH', 'RUNNING', 'CIRCLING'):
            namespace = dict(bot_state=state, valid_door_box=dict(x=936, h=169.5),
                             t_name='大门', stop_all=Mock(), print=Mock(), time=Mock())
            exec(compile(module, '<handoff>', 'exec'), namespace)
            self.assertEqual(namespace['bot_state'], 'APPROACH_DOOR')
            self.assertTrue(namespace['reached'])
            namespace['stop_all'].assert_called_once_with()
