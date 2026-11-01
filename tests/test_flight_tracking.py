import ast
import contextlib
import io
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


class Frame:
    def __getitem__(self, key):
        return self


class FlightTrackingTests(unittest.TestCase):
    def replay(self, seats, plane, duration=12):
        tree = ast.parse((ROOT / 'logic/bot.py').read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'wait_for_jump')
        clock = SimpleNamespace(now=100.0)
        inputs = SimpleNamespace(keyDown=Mock(), keyUp=Mock())
        api = SimpleNamespace(SetCursorPos=Mock(), mouse_event=Mock())
        constants = SimpleNamespace(MOUSEEVENTF_LEFTDOWN=1, MOUSEEVENTF_LEFTUP=2)
        controller = SimpleNamespace(running=True, is_paused=False, MAP_SIZE=1050,
                                     best_jump_point_coords=(100, 100), is_waiting_for_jump=True)
        def sleep(seconds):
            clock.now += seconds
            if clock.now >= 100 + duration:
                controller.running = False
        info = dict(game_size=(1920,1080), screen_pos=(0,0), border=(0,0), map_offset=(435,15))
        controller.capture_game_screen = lambda: (Frame(), info)
        controller.find_image = lambda frame, name: (True, 1.0, (0,0)) if name == 'naozhong' else (False, 0., None)
        controller.handle_endgame = lambda *args: False
        controller.find_plane_seats = Mock(side_effect=lambda frame: (seats(clock.now) if callable(seats) else seats, 1.0))
        controller.find_flight_plane = Mock(return_value=(plane, .99 if plane else .3, (112,100) if plane else None))
        controller.execute_ai_bot_behavior = Mock()
        namespace = dict(time=SimpleNamespace(time=lambda:clock.now,sleep=sleep), math=math,
                         win32api=api, win32con=constants,pydirectinput=inputs)
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<flight>', 'exec'), namespace)
        with contextlib.redirect_stdout(io.StringIO()):
            namespace['wait_for_jump'](controller, info, 12.5)
        return inputs, controller

    def test_no_seats_never_jumps_even_if_position_is_near_target(self):
        inputs, controller = self.replay(False, True)
        self.assertNotIn(('f',), [call.args for call in inputs.keyDown.call_args_list])
        controller.find_flight_plane.assert_not_called()
        controller.execute_ai_bot_behavior.assert_not_called()

    def test_boarded_but_plane_outside_map_does_not_timeout_jump(self):
        inputs, controller = self.replay(True, False, duration=18)
        self.assertNotIn(('f',), [call.args for call in inputs.keyDown.call_args_list])
        controller.execute_ai_bot_behavior.assert_not_called()

    def test_confirmed_boarding_and_plane_can_jump(self):
        inputs, controller = self.replay(True, True)
        self.assertIn(('f',), [call.args for call in inputs.keyDown.call_args_list])
        controller.execute_ai_bot_behavior.assert_called_once()

    def test_single_seat_false_positive_does_not_confirm_boarding(self):
        inputs, controller = self.replay(lambda now: now < 102.1, True)
        controller.find_flight_plane.assert_not_called()
        controller.execute_ai_bot_behavior.assert_not_called()

