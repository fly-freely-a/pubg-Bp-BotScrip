import ast
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class MatchmakingTests(unittest.TestCase):
    def replay(self, show_loading=False, show_queue=True, start_stays_visible=False):
        path = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'run')
        clock = SimpleNamespace(now=0.0)
        def sleep(seconds):
            clock.now += seconds
            if clock.now > (20 if show_loading else 180):
                controller.running = False
        keyboard = SimpleNamespace(is_pressed=lambda _: False)
        inputs = SimpleNamespace(keyDown=Mock(), keyUp=Mock(), press=Mock())
        namespace = dict(time=SimpleNamespace(time=lambda: clock.now, sleep=sleep,
                                             strftime=lambda _: '12:00:00'),
                         keyboard=keyboard, pydirectinput=inputs,
                         win32gui=SimpleNamespace(IsWindow=lambda _: True),
                         win32api=SimpleNamespace(SetCursorPos=Mock()),
                         pyautogui=SimpleNamespace(click=Mock()))
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
        controller = SimpleNamespace(
            running=True, is_paused=False, pubg_hwnd=1, is_waiting_for_jump=False,
            has_marked_this_match=False, toggle_desktop_icons=Mock(),
            bring_pubg_to_front=lambda: True, handle_endgame=Mock(return_value=False),
            stop_all_movement=Mock())
        controller.queue_matcher = SimpleNamespace(match=lambda _: (
            (0.95, None, 0.5) if show_queue and clock.now > 1
            and (not show_loading or clock.now < 10) else (0.0, None, None)))
        def restart():
            controller.running = False
        controller.force_restart_pubg = Mock(side_effect=restart)
        info = dict(screen_pos=(0, 0), border=(0, 0), real_client_size=(1920, 1080))
        def capture():
            if clock.now > (20 if show_loading else 180):
                controller.running = False
            return object(), info
        controller.capture_game_screen = capture
        def find_image(image, name):
            if name == 'start_btn' and (clock.now < 1 or start_stays_visible):
                return True, 0.95, (100, 100)
            if show_loading and name == 'loading' and 10 < clock.now < 14:
                return True, 0.95, (100, 100)
            return False, 0.0, None
        controller.find_image = find_image
        with contextlib.redirect_stdout(io.StringIO()):
            namespace['run'](controller)
        return clock, controller, inputs

    def test_queue_longer_than_watchdog_never_presses_map_or_restarts(self):
        clock, controller, inputs = self.replay()
        self.assertGreater(clock.now, 180)
        controller.force_restart_pubg.assert_not_called()
        inputs.keyDown.assert_not_called()
        inputs.press.assert_not_called()
        # 初次大厅检查后，确认排队的画面直接等待，不交给通用取消按钮处理。
        self.assertEqual(controller.handle_endgame.call_count, 1)

    def test_loading_transition_enables_map_after_queue(self):
        _, controller, inputs = self.replay(show_loading=True)
        controller.force_restart_pubg.assert_not_called()
        inputs.keyDown.assert_any_call('m')

    def test_missing_queue_and_match_evidence_pauses_without_map_or_restart(self):
        _, controller, inputs = self.replay(show_queue=False)
        self.assertTrue(controller.is_paused)
        controller.force_restart_pubg.assert_not_called()
        inputs.keyDown.assert_not_called()

    def test_start_button_still_visible_retries_without_map(self):
        _, controller, inputs = self.replay(show_queue=False, start_stays_visible=True)
        controller.force_restart_pubg.assert_not_called()
        inputs.keyDown.assert_not_called()


if __name__ == '__main__':
    unittest.main()
