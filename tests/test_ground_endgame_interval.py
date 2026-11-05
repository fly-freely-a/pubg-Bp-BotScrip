import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class GroundEndgameIntervalTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        self.branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                           and ast.unparse(n.test) == 'time.perf_counter() - last_ground_endgame_check >= 2.0')
        self.clock = SimpleNamespace(now=0.0)
        self.handler = Mock(return_value=False)
        self.namespace = dict(time=SimpleNamespace(perf_counter=lambda: self.clock.now),
                              last_ground_endgame_check=float('-inf'),
                              self=SimpleNamespace(handle_endgame=self.handler),
                              game_img=object(), current_window_info=object())

    def tick(self, now):
        self.clock.now = now
        self.namespace.update(endgame_ms=0.0, endgame_found=False, endgame_checked=False)
        exec(compile(ast.Module(body=[self.branch], type_ignores=[]), '<endgame_interval>', 'exec'), self.namespace)
        return self.namespace['endgame_checked'], self.namespace['endgame_found']

    def test_initial_check_runs_without_waiting(self):
        self.assertEqual(self.tick(0), (True, False))
        self.handler.assert_called_once()

    def test_checks_are_skipped_until_two_seconds_then_resume(self):
        self.tick(0)
        for now in (.5, 1, 1.99):
            self.assertEqual(self.tick(now), (False, False))
        self.assertEqual(self.handler.call_count, 1)
        self.assertEqual(self.tick(2), (True, False))
        self.assertEqual(self.handler.call_count, 2)

    def test_detected_endgame_still_propagates_to_existing_exit(self):
        self.handler.return_value = True
        self.assertEqual(self.tick(0), (True, True))
