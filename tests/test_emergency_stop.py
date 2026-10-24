"""Isolate the emergency handler so checks run without Windows or game input."""
import ast
import contextlib
import io
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call


class EmergencyStopTests(unittest.TestCase):
    def test_corner_check_disabled_after_emergency_hotkeys_are_registered(self):
        from config import Config
        source = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        bot = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == 'PUBGSmartMarkerV9')
        init = next(n for n in bot.body if isinstance(n, ast.FunctionDef)
                    and n.name == '__init__')
        inputs = SimpleNamespace(FAILSAFE=True)
        keyboard = SimpleNamespace(add_hotkey=Mock())
        namespace = dict(Config=Config, os=os, glob=SimpleNamespace(glob=lambda _: []),
                         pydirectinput=inputs, keyboard=keyboard)
        exec(compile(ast.Module(body=[init], type_ignores=[]), str(source), 'exec'), namespace)
        controller = SimpleNamespace(_load_img=Mock(return_value=None),
                                     toggle_pause=Mock(), emergency_stop=Mock())
        with contextlib.redirect_stdout(io.StringIO()):
            namespace['__init__'](controller)
        self.assertFalse(inputs.FAILSAFE)
        keyboard.add_hotkey.assert_any_call('end', controller.emergency_stop)
        keyboard.add_hotkey.assert_any_call('ctrl+shift+f12', controller.emergency_stop)

    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'logic' / 'bot.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        bot = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'PUBGSmartMarkerV9')
        handler = next(node for node in bot.body if isinstance(node, ast.FunctionDef)
                       and node.name == 'emergency_stop')
        self.inputs = SimpleNamespace(
            FAILSAFE=True, KEYBOARD_MAPPING={'w': 17, 'shift': 42},
            keyUp=Mock(), mouseUp=Mock())
        self.exit = Mock(side_effect=SystemExit)
        namespace = {'pydirectinput': self.inputs,
                     'os': SimpleNamespace(_exit=self.exit)}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), 'exec'),
             namespace)
        self.handler = namespace['emergency_stop']
        self.controller = SimpleNamespace(
            running=True, is_paused=False, toggle_desktop_icons=Mock())

    def test_stop_releases_inputs_restores_desktop_and_exits(self):
        with self.assertRaises(SystemExit):
            self.handler(self.controller)
        self.assertFalse(self.controller.running)
        self.assertTrue(self.controller.is_paused)
        self.assertFalse(self.inputs.FAILSAFE)
        self.assertEqual(self.inputs.keyUp.call_args_list,
                         [call('w', _pause=False), call('shift', _pause=False)])
        self.assertEqual(self.inputs.mouseUp.call_args_list,
                         [call(button=b, _pause=False)
                          for b in ('left', 'right', 'middle')])
        self.controller.toggle_desktop_icons.assert_called_once_with(show=True)
        self.exit.assert_called_once_with(0)

    def test_release_failure_does_not_skip_remaining_inputs(self):
        self.inputs.keyUp.side_effect = [RuntimeError('release failed'), None]
        self.inputs.mouseUp.side_effect = [RuntimeError('release failed'), None, None]
        with self.assertRaises(SystemExit):
            self.handler(self.controller)
        self.assertEqual(self.inputs.keyUp.call_count, 2)
        self.assertEqual(self.inputs.mouseUp.call_count, 3)
        self.exit.assert_called_once_with(0)

    def test_desktop_failure_still_exits(self):
        self.controller.toggle_desktop_icons.side_effect = RuntimeError('restore failed')
        with self.assertRaises(SystemExit):
            self.handler(self.controller)
        self.exit.assert_called_once_with(0)


if __name__ == '__main__':
    unittest.main()
