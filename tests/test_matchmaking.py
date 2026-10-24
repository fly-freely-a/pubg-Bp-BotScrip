import ast
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class SimpleNamespaceFrame:
    def __getitem__(self, key):
        return self


class MatchmakingTests(unittest.TestCase):
    def replay(self, duration, map_after=None, loading=False, start_stays_visible=False):
        path = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'run')
        clock = SimpleNamespace(now=0.0)

        def sleep(seconds):
            clock.now += seconds
            if clock.now > duration:
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
        def restart():
            controller.running = False
        controller.force_restart_pubg = Mock(side_effect=restart)
        info = dict(screen_pos=(0, 0), border=(0, 0), real_client_size=(1920, 1080), map_offset=(435, 15))
        def capture():
            if clock.now > duration:
                controller.running = False
            return SimpleNamespaceFrame(), info
        controller.capture_game_screen = capture
        def find_image(image, name):
            if name == 'start_btn' and (clock.now < 1 or start_stays_visible):
                return True, 0.95, (100, 100)
            if loading and name == 'loading' and clock.now > 1:
                return True, 0.95, (100, 100)
            if name == 'naozhong' and map_after is not None and clock.now >= map_after:
                return True, 0.95, (100, 100)
            return False, 0.0, None
        controller.find_image = find_image
        controller.MAP_SIZE = 1050
        controller.extract_flight_path_v2 = lambda _: []
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            namespace['run'](controller)
        self.assertNotIn('发生严重错误', output.getvalue())
        return clock, controller, inputs

    def test_wait_under_five_minutes_does_not_restart(self):
        _, controller, inputs = self.replay(299)
        controller.force_restart_pubg.assert_not_called()
        inputs.keyDown.assert_any_call('m')
        self.assertFalse(controller.is_paused)

    def test_no_map_for_five_minutes_restarts(self):
        clock, controller, _ = self.replay(310)
        controller.force_restart_pubg.assert_called_once()
        self.assertGreaterEqual(clock.now, 300)
        self.assertLess(clock.now, 305)

    def test_map_recognition_clears_matchmaking_timeout(self):
        _, controller, _ = self.replay(450, map_after=270)
        controller.force_restart_pubg.assert_not_called()

    def test_loading_without_map_does_not_extend_timeout(self):
        _, controller, _ = self.replay(310, loading=True)
        controller.force_restart_pubg.assert_called_once()

    def test_repeated_start_button_does_not_extend_timeout(self):
        _, controller, _ = self.replay(310, start_stays_visible=True)
        controller.force_restart_pubg.assert_called_once()


if __name__ == '__main__':
    unittest.main()
