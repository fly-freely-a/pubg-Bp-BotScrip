import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class NearTargetMovementTests(unittest.TestCase):
    def test_near_zone_blocks_sprint_but_allows_walking_and_release(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        method = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == 'set_key')
        inputs = SimpleNamespace(keyDown=Mock(), keyUp=Mock())
        keys = dict(shift=False, w=False)
        namespace = dict(pydirectinput=inputs, keys_pressed=keys, entered_target_zone=True)
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<set_key>', 'exec'), namespace)
        set_key = namespace['set_key']
        set_key('shift', True)
        inputs.keyDown.assert_not_called()
        set_key('w', True)
        inputs.keyDown.assert_called_once_with('w')
        keys['shift'] = True
        set_key('shift', False)
        inputs.keyUp.assert_called_once_with('shift')
        namespace['entered_target_zone'] = False
        set_key('shift', True)
        self.assertTrue(keys['shift'])
        self.assertEqual(inputs.keyDown.call_args.args, ('shift',))

    def test_lost_toilet_stops_instead_of_blind_movement(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and isinstance(n.test, ast.Compare)
                      and ast.unparse(n.test) == 'time.time() - global_last_seen_time > 3.0')
        # Execute the real short-loss branch without its enclosing loop's continue.
        statements = branch.orelse[:-1]
        stop = Mock()
        namespace = dict(last_action_log='', stop_all=stop, print=Mock())
        exec(compile(ast.Module(body=statements, type_ignores=[]), '<lost_toilet>', 'exec'), namespace)
        stop.assert_called_once_with()
        self.assertEqual(namespace['last_action_log'], 'LOST_TOILET_STOP')
