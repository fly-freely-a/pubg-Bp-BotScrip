"""Isolate the emergency handler so checks run without Windows or game input."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call


class EmergencyStopTests(unittest.TestCase):
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
