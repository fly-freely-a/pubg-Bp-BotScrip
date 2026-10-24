import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class VisualRecoveryTests(unittest.TestCase):
    def replay(self, state, started=99.0):
        path = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'start_auto_run')
        branch = next(n for n in ast.walk(method) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == f'bot_state == {state!r}')
        branch = ast.If(test=branch.test, body=branch.body, orelse=[])
        loop = ast.For(target=ast.Name(id='_', ctx=ast.Store()),
                       iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                       body=[branch], orelse=[])
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        namespace = dict(bot_state=state, toilet_box=None, valid_door_box=None,
                         time=SimpleNamespace(time=lambda: 100.0, sleep=Mock()), stop_all=Mock(),
                         visual_search_started=started, last_visual_target_x=300,
                         center_x=960, dist_history=[22.0, 28.0],
                         global_last_seen_time=99.0, h=1080, last_action_log='',
                         set_key=Mock(), is_sprinting=False, keys_pressed={'ctrl': False},
                         self=SimpleNamespace(rotate_mouse_raw=Mock(), last_known_toilet_h=200))
        exec(compile(module, str(path), 'exec'), namespace)
        return namespace

    def test_lost_target_while_circling_searches_locally(self):
        namespace = self.replay('CIRCLING')
        self.assertEqual(namespace['bot_state'], 'SEARCH_TARGET')
        namespace['stop_all'].assert_called_once()

    def test_brief_detection_loss_stops_instead_of_blind_running(self):
        namespace = self.replay('RUNNING')
        namespace['stop_all'].assert_called_once()
        namespace['set_key'].assert_not_called()

    def test_local_search_does_not_move_toward_marker(self):
        namespace = self.replay('SEARCH_TARGET')
        self.assertEqual(namespace['bot_state'], 'SEARCH_TARGET')
        namespace['stop_all'].assert_called_once()
        namespace['self'].rotate_mouse_raw.assert_called_once_with(-120, 0)

    def test_local_search_is_bounded_before_navigation_fallback(self):
        namespace = self.replay('SEARCH_TARGET', started=90.0)
        self.assertEqual(namespace['bot_state'], 'COMPASS_RUSH')
        self.assertEqual(namespace['dist_history'], [])
