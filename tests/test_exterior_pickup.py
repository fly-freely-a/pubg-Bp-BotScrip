import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class ExteriorPickupTests(unittest.TestCase):
    def body(self, state):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        return next(n.body for n in ast.walk(tree) if isinstance(n, ast.If)
                    and ast.unparse(n.test) == f"bot_state == '{state}'")

    def verify(self, close_score, open_score=.95):
        inputs = Mock()
        namespace = dict(time=SimpleNamespace(time=lambda: 100, sleep=Mock()), game_img=object(),
                         f_tmpl=.99, open_door_templates=[open_score], close_door_tmpl=close_score,
                         cv2=SimpleNamespace(matchTemplate=lambda image, template, mode: template,
                                             minMaxLoc=lambda score: (0, score, None, None), TM_CCOEFF_NORMED=1),
                         win32api=SimpleNamespace(keybd_event=inputs),
                         win32con=SimpleNamespace(KEYEVENTF_KEYUP=2), verify_count=1,
                         bot_state='VERIFY_DOOR', print=Mock())
        exec(compile(ast.Module(body=self.body('VERIFY_DOOR'), type_ignores=[]), '<verify>', 'exec'), namespace)
        return namespace, inputs

    def test_close_prompt_wins_over_shared_door_character_and_sends_f(self):
        namespace, inputs = self.verify(.95)
        self.assertEqual(namespace['bot_state'], 'EXTERIOR_PICKUP')
        self.assertEqual([call.args for call in inputs.call_args_list], [(0x46, 0, 0, 0), (0x46, 0, 2, 0)])

    def test_normal_door_keeps_existing_entry(self):
        namespace, _ = self.verify(.3)
        self.assertEqual(namespace['bot_state'], 'ITEM_PICKUP')

    def test_normal_item_keeps_existing_compass_return(self):
        namespace, _ = self.verify(.3, open_score=.3)
        self.assertEqual(namespace['bot_state'], 'COMPASS_RUSH')

    def test_exterior_sequence_moves_left_back_and_loots_without_forward(self):
        events = []
        info = object()
        namespace = dict(time=SimpleNamespace(time=lambda:100, sleep=lambda seconds:events.append(('wait', seconds))),
                         stop_all=lambda:events.append(('stop',)),
                         set_key=lambda key,state:events.append((key,state)),
                         pydirectinput=SimpleNamespace(press=lambda key:events.append(('press',key))),
                         self=SimpleNamespace(pickup_all_items_in_tab=lambda window:events.append(('pickup',window))),
                         current_window_info=info, print=Mock(), dist_history=[20, 25],
                         has_aligned_door=True, is_skew_locked=True, last_aspect_ratio=.6)
        exec(compile(ast.Module(body=self.body('EXTERIOR_PICKUP'), type_ignores=[]), '<pickup>', 'exec'), namespace)
        self.assertEqual(events, [('stop',), ('a', True), ('wait', .8), ('a', False),
                                  ('s', True), ('wait', .7), ('s', False),
                                  ('press','tab'), ('wait',1.), ('pickup',info),
                                  ('press','tab'), ('wait',.5)])
        self.assertEqual(namespace['bot_state'], 'COMPASS_RUSH')
        self.assertFalse(namespace['has_aligned_door'])
        self.assertFalse(namespace['is_skew_locked'])
        self.assertEqual(namespace['last_aspect_ratio'], 0.0)
        self.assertEqual(namespace['dist_history'], [])
