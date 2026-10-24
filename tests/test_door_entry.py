import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class DoorEntryTests(unittest.TestCase):
    def test_approach_records_alignment_and_invalidates_visible_misalignment(self):
        path = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        record = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "bot_state == 'APPROACH_DOOR' and valid_door_box is not None")
        code = compile(ast.Module(body=[record], type_ignores=[]), str(path), 'exec')
        namespace = dict(bot_state='APPROACH_DOOR', h=1080, center_x=960,
                         valid_door_box=dict(x=960, w=240, h=400),
                         keys_pressed={'a': False, 'd': False},
                         entry_alignment_frames=0, last_entry_alignment=None,
                         time=SimpleNamespace(time=lambda: 100.0))
        exec(code, namespace)
        self.assertIsNone(namespace['last_entry_alignment'])
        exec(code, namespace)
        self.assertEqual(namespace['last_entry_alignment'], 100.0)
        # 贴脸导致检测框裁切，不覆盖已确认的对齐结果。
        namespace['valid_door_box'] = dict(x=1100, w=240, h=1050)
        exec(code, namespace)
        self.assertEqual(namespace['last_entry_alignment'], 100.0)
        namespace['valid_door_box'] = dict(x=1100, w=240, h=400)
        exec(code, namespace)
        self.assertIsNone(namespace['last_entry_alignment'])

    def replay(self, door, verify_count=1, last_alignment=None):
        path = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'start_auto_run')
        branch = next(n for n in ast.walk(method) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "bot_state == 'VERIFY_DOOR'")
        branch = ast.If(test=branch.test, body=branch.body, orelse=[])
        loop = ast.For(target=ast.Name(id='_', ctx=ast.Store()),
                       iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                       body=[branch], orelse=[])
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        frame = SimpleNamespace(shape=(1080, 1920, 3))
        controller = SimpleNamespace(capture_game_screen=lambda: (frame, None),
                                     _find_entry_door=Mock(return_value=door),
                                     rotate_mouse_raw=Mock())
        inputs = SimpleNamespace(press=Mock())
        namespace = dict(bot_state='VERIFY_DOOR', self=controller,
                         time=SimpleNamespace(time=lambda: 100.0, sleep=Mock()),
                         f_matcher=SimpleNamespace(match=lambda _: (0.9, None, 1.0)),
                         f_threshold=0.72, open_door_templates=[object()],
                         cv2=SimpleNamespace(matchTemplate=Mock(), TM_CCOEFF_NORMED=5,
                                             minMaxLoc=lambda _: (0, 0.9, None, None)),
                         verify_count=verify_count, verifying_door=True, entry_last_ratio=None,
                         last_entry_log=100.0,
                         last_entry_alignment=last_alignment,
                         skew_dir='a', stop_all=Mock(), set_key=Mock(),
                         pydirectinput=inputs)
        exec(compile(module, str(path), 'exec'), namespace)
        return namespace, controller, inputs

    def test_sideways_door_does_not_open_or_start_entry(self):
        namespace, controller, inputs = self.replay(dict(x=1100, y=500, w=80, h=400))
        inputs.press.assert_not_called()
        self.assertEqual(namespace['bot_state'], 'VERIFY_DOOR')
        controller.rotate_mouse_raw.assert_called_once()

    def test_centered_sideways_door_strafes_before_opening(self):
        namespace, controller, inputs = self.replay(dict(x=960, y=500, w=80, h=400))
        inputs.press.assert_not_called()
        controller.rotate_mouse_raw.assert_not_called()
        namespace['set_key'].assert_any_call('a', True)
        namespace['set_key'].assert_any_call('a', False)
        self.assertEqual(namespace['verify_count'], 0)

    def test_missing_door_without_alignment_backs_up_to_reacquire(self):
        namespace, _, inputs = self.replay(None)
        inputs.press.assert_not_called()
        self.assertEqual(namespace['verify_count'], 0)
        namespace['set_key'].assert_any_call('s', True)
        namespace['set_key'].assert_any_call('s', False)
        self.assertEqual(namespace['bot_state'], 'APPROACH_DOOR')

    def test_recent_alignment_allows_opening_when_close_door_disappears(self):
        namespace, controller, inputs = self.replay(None, last_alignment=99.0)
        inputs.press.assert_called_once_with('f')
        controller._find_entry_door.assert_not_called()
        self.assertEqual(namespace['bot_state'], 'ITEM_PICKUP')

    def test_expired_alignment_does_not_allow_blind_opening(self):
        namespace, _, inputs = self.replay(None, last_alignment=90.0)
        inputs.press.assert_not_called()
        self.assertEqual(namespace['bot_state'], 'APPROACH_DOOR')

    def test_aligned_door_requires_two_checks_before_opening(self):
        door = dict(x=960, y=500, w=240, h=400)
        first, _, inputs = self.replay(door, verify_count=0)
        inputs.press.assert_not_called()
        self.assertEqual(first['verify_count'], 1)
        second, _, inputs = self.replay(door, verify_count=first['verify_count'])
        inputs.press.assert_called_once_with('f')
        self.assertEqual(second['bot_state'], 'ITEM_PICKUP')


if __name__ == '__main__':
    unittest.main()
