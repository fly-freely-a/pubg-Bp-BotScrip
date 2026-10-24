import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class NearTargetSearchTests(unittest.TestCase):
    def test_visual_zone_does_not_toggle_with_boundary_noise(self):
        path = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        zone = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                    and ast.unparse(n.test) == 'dist <= 15.0')
        loop = ast.For(target=ast.Name(id='_', ctx=ast.Store()),
                       iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                       body=[zone], orelse=[])
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        code = compile(module, str(path), 'exec')
        namespace = dict(entered_target_zone=False, target_zone_exit_count=0,
                         bot_state='COMPASS_RUSH', stop_all=Mock(), dist_history=[],
                         time=SimpleNamespace(time=lambda: 100.0))
        for distance, expected in ((15.1, False), (15.0, True), (23.4, True),
                                    (16.3, True), (31.0, True), (20.0, True),
                                    (31.0, True), (31.0, True), (31.0, False)):
            with self.subTest(distance=distance):
                namespace['dist'] = distance
                exec(code, namespace)
                self.assertEqual(namespace['entered_target_zone'], expected)
        namespace['stop_all'].assert_called_once()

    def replay(self, distance):
        path = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                        and n.name == 'start_auto_run')
        branch = next(n for n in ast.walk(function) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "bot_state == 'COMPASS_RUSH'"
                      and any(isinstance(a, ast.Assign)
                              and any(isinstance(t, ast.Name) and t.id == 'tx_compass'
                                      for t in a.targets) for a in n.body))
        branch = ast.If(test=branch.test, body=branch.body, orelse=[])
        loop = ast.For(target=ast.Name(id='_', ctx=ast.Store()),
                       iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                       body=[branch], orelse=[])
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        controller = SimpleNamespace(find_target_on_compass=Mock(return_value=960),
                                     rotate_mouse_raw=Mock(), last_scrape_time=0,
                                     near_target_search_distance=8.0)
        inputs = SimpleNamespace(press=Mock())
        set_key = Mock()
        stop = Mock()
        namespace = dict(bot_state='COMPASS_RUSH', entered_target_zone=True,
                         dist=distance, self=controller, game_img=None,
                         time=SimpleNamespace(time=lambda: 100.0, sleep=Mock()),
                         center_x=960, is_sprinting=False, keys_pressed={'w': False, 'a': False, 'd': False},
                         set_key=set_key, stop_all=stop, pydirectinput=inputs,
                         random=SimpleNamespace(choice=lambda _: 'a'),
                         last_target_search_log=100.0,
                         last_target_search_snapshot=100.0)
        exec(compile(module, str(path), 'exec'), namespace)
        return controller, inputs, set_key, stop

    def test_near_marker_without_visual_target_scans_instead_of_running_or_jumping(self):
        controller, inputs, set_key, stop = self.replay(8.0)
        stop.assert_called_once()
        controller.rotate_mouse_raw.assert_called_once()
        set_key.assert_not_called()
        inputs.press.assert_not_called()

    def test_15_pixels_keeps_approaching_instead_of_stopping_to_search(self):
        controller, _, set_key, stop = self.replay(15.3)
        stop.assert_not_called()
        controller.rotate_mouse_raw.assert_not_called()
        set_key.assert_any_call('w', True)

    def test_search_starts_at_configured_boundary(self):
        _, _, _, stop = self.replay(8.0)
        stop.assert_called_once()

    def test_above_eight_pixels_keeps_approaching(self):
        _, _, set_key, stop = self.replay(8.1)
        stop.assert_not_called()
        set_key.assert_any_call('w', True)


if __name__ == '__main__':
    unittest.main()
