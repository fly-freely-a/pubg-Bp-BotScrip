import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class CompassTurningTests(unittest.TestCase):
    def replay(self, target_x, dist=20, in_zone=True, sprinting=False):
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
        keys = dict(w=True, a=True, d=False, shift=sprinting, ctrl=False)
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
                         time=SimpleNamespace(time=lambda: 100), center_x=960, dist=dist,
                         entered_target_zone=in_zone,
                         keys_pressed=keys, stop_all=stop, set_key=set_key,
                         last_valid_tx_time=99.5, is_sprinting=sprinting, last_w_refresh=100,
                         pydirectinput=inputs, print=Mock())
        exec(compile(module, '<compass>', 'exec'), namespace)
        return namespace, keys, events, inputs

    def test_turn_is_sent_before_releasing_forward(self):
        _, keys, events, _ = self.replay(1100)
        self.assertEqual(events[0][0], 'turn')
        self.assertEqual(events[1], ('w', False))
        self.assertFalse(keys['w'])

    def test_missing_distance_cancels_sprint_even_outside_the_zone(self):
        for target_x in (960, None):
            with self.subTest(target_x=target_x):
                namespace, keys, _, _ = self.replay(target_x, dist=None, in_zone=False, sprinting=True)
                self.assertFalse(keys['shift'])
                self.assertTrue(keys['w'])
                self.assertFalse(namespace['is_sprinting'])

    def test_valid_distance_outside_the_zone_allows_sprint(self):
        namespace, keys, _, _ = self.replay(960, dist=31, in_zone=False)
        self.assertTrue(keys['shift'])
        self.assertTrue(namespace['is_sprinting'])
