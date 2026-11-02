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

    def test_memory_slow_forward_is_time_limited_and_releases_side_keys(self):
        branch = copy.deepcopy(next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                                    and ast.unparse(n.test) == 'near_door_memory and time_since_lost < 2.0'))
        branch.orelse = []  # Isolate only the newly added branch, not the existing fallback.
        for elapsed, expected in ((1.5, True), (2.0, False)):
            keys = Mock()
            namespace = dict(near_door_memory=True, time_since_lost=elapsed, set_key=keys,
                             time=SimpleNamespace(time=lambda: 10), last_action_log='', print=Mock())
            exec(compile(ast.Module(body=[branch], type_ignores=[]), '<memory>', 'exec'), namespace)
            if expected:
                self.assertEqual([call.args for call in keys.call_args_list],
                                 [('shift', False), ('a', False), ('d', False), ('ctrl', True), ('w', True)])
            else:
                keys.assert_not_called()
