import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class CompassTurningTests(unittest.TestCase):
    def replay(self, target_x, turning=False):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "bot_state == 'COMPASS_RUSH'"
                      and n.body and isinstance(n.body[0], ast.Assign)
                      and ast.unparse(n.body[0]).startswith('tx_compass ='))
        branch.orelse = []
        class EndIteration(ast.NodeTransformer):
            def visit_Continue(self, node):
                return ast.copy_location(ast.Break(), node)
        module = ast.fix_missing_locations(ast.Module(body=[ast.While(
            test=ast.Constant(True), body=[EndIteration().visit(branch), ast.Break()], orelse=[])],
            type_ignores=[]))
        events = []
        keys = dict(w=True, a=True, d=False, shift=False, ctrl=False)
        def stop():
            events.append('stop')
            for key in keys:
                keys[key] = False
        def set_key(key, pressed):
            events.append((key, pressed))
            keys[key] = pressed
        controller = SimpleNamespace(find_target_on_compass=lambda image: target_x,
                                     rotate_mouse_raw=lambda *args: events.append(('turn', args)),
                                     last_scrape_time=100)
        inputs = SimpleNamespace(press=Mock())
        namespace = dict(bot_state='COMPASS_RUSH', self=controller, game_img=object(),
                         time=SimpleNamespace(time=lambda: 100), center_x=960, dist=20,
                         entered_target_zone=True, compass_turning=turning,
                         keys_pressed=keys, stop_all=stop, set_key=set_key,
                         last_valid_tx_time=99.5, is_sprinting=False,
                         pydirectinput=inputs, print=Mock())
        exec(compile(module, '<compass>', 'exec'), namespace)
        return namespace, keys, events, inputs

    def test_stop_precedes_turn_and_prevents_other_movement(self):
        namespace, keys, events, inputs = self.replay(1100)
        self.assertEqual(events[0], 'stop')
        self.assertEqual(events[1][0], 'turn')
        self.assertFalse(any(keys.values()))
        self.assertTrue(namespace['compass_turning'])
        inputs.press.assert_not_called()

    def test_new_aligned_frame_resumes_forward(self):
        namespace, keys, _, _ = self.replay(990, turning=True)
        self.assertFalse(namespace['compass_turning'])
        self.assertTrue(keys['w'])

    def test_missing_compass_during_turn_never_uses_forward_memory(self):
        namespace, keys, events, inputs = self.replay(None, turning=True)
        self.assertEqual(events[0], 'stop')
        self.assertFalse(any(keys.values()))
        self.assertTrue(namespace['compass_turning'])
        inputs.press.assert_not_called()
