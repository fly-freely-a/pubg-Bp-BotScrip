import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class DoorAlignmentRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        self.update = next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                           and ast.unparse(n.test) == 'valid_door_box'
                           and 'door_was_aligned' in ast.unparse(n))
        self.intercept = next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                              and n.body and ast.unparse(n.body[0]) == 'ignore_f = False')

    def refresh(self, door, aligned, lost_for=1.0):
        namespace = dict(valid_door_box=door, has_aligned_door=aligned, center_x=960,
                         stop_all=Mock(), print=Mock(), bot_state='APPROACH_DOOR',
                         time=SimpleNamespace(time=lambda:100), global_last_door_time=100-lost_for)
        exec(compile(ast.Module(body=[self.update], type_ignores=[]), '<alignment>', 'exec'), namespace)
        return namespace

    def test_narrower_or_off_center_door_revokes_previous_alignment(self):
        for door in (dict(x=960, w=90, h=300), dict(x=1161, w=150, h=300)):
            namespace = self.refresh(door, True)
            self.assertFalse(namespace['has_aligned_door'])
            namespace['stop_all'].assert_called_once_with()

    def test_aligned_visible_door_updates_flag(self):
        self.assertTrue(self.refresh(dict(x=1000, w=150, h=300), False)['has_aligned_door'])

    def test_missing_door_keeps_recent_alignment(self):
        self.assertTrue(self.refresh(None, True)['has_aligned_door'])

    def test_push_prompt_cannot_intercept_adjustment_when_unaligned(self):
        namespace = dict(bot_state='APPROACH_DOOR', current_f_score=.99, has_aligned_door=False,
                         open_door_templates=[.95], game_img=object(), f_tmpl=object(),
                         cv2=SimpleNamespace(matchTemplate=lambda image, template, mode: template,
                                             minMaxLoc=lambda score:(0,score,None,None), TM_CCOEFF_NORMED=1),
                         time=SimpleNamespace(time=lambda:100), last_door_diagnostic=0,
                         stop_all=Mock(), print=Mock())
        exec(compile(ast.Module(body=[self.intercept], type_ignores=[]), '<intercept>', 'exec'), namespace)
        self.assertTrue(namespace['ignore_f'])
        self.assertEqual(namespace['bot_state'], 'APPROACH_DOOR')
        self.assertLess(self.update.lineno, self.intercept.lineno)

    def test_missing_door_expires_at_existing_loss_timeout(self):
        self.assertFalse(self.refresh(None, True, lost_for=2.3)['has_aligned_door'])
