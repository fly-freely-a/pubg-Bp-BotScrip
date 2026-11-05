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

    def verify(self, open_score=.95, aligned=True):
        inputs = Mock()
        namespace = dict(time=SimpleNamespace(time=lambda: 100, sleep=Mock()), game_img=object(),
                         f_tmpl=.99, open_door_templates=[open_score],
                         cv2=SimpleNamespace(matchTemplate=lambda image, template, mode: template,
                                             minMaxLoc=lambda score: (0, score, None, None), TM_CCOEFF_NORMED=1),
                         win32api=SimpleNamespace(keybd_event=inputs),
                         win32con=SimpleNamespace(KEYEVENTF_KEYUP=2), verify_count=1,
                         bot_state='VERIFY_DOOR', print=Mock(), has_aligned_door=aligned, stop_all=Mock())
        exec(compile(ast.Module(body=self.body('VERIFY_DOOR'), type_ignores=[]), '<verify>', 'exec'), namespace)
        return namespace, inputs

    def test_generic_f_without_push_prompt_sends_f_and_loots_exterior(self):
        namespace, inputs = self.verify(.3)
        self.assertEqual(namespace['bot_state'], 'EXTERIOR_PICKUP')
        self.assertEqual([call.args for call in inputs.call_args_list], [(0x46, 0, 0, 0), (0x46, 0, 2, 0)])

    def test_normal_door_keeps_existing_entry(self):
        namespace, _ = self.verify(.95)
        self.assertEqual(namespace['bot_state'], 'ITEM_PICKUP')

    def test_generic_pickup_does_not_require_close_door_template(self):
        source = (Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text()
        self.assertNotIn('door2.png', source)
        self.assertNotIn('door3.png', source)

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

    def test_push_prompt_does_not_enter_or_press_f_when_unaligned(self):
        namespace, inputs = self.verify(.95, aligned=False)
        self.assertEqual(namespace['bot_state'], 'APPROACH_DOOR')
        inputs.assert_not_called()

    def test_generic_pickup_is_allowed_when_unaligned(self):
        namespace, inputs = self.verify(.3, aligned=False)
        self.assertEqual(namespace['bot_state'], 'EXTERIOR_PICKUP')
        self.assertEqual(inputs.call_count, 2)
