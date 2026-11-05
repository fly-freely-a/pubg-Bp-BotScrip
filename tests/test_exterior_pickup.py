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

    def verify(self, open_score=.95, aligned=True, door=None, since_f=5.0):
        inputs = Mock()
        namespace = dict(time=SimpleNamespace(time=lambda:100, perf_counter=lambda:100, sleep=Mock()),
                         game_img=object(), current_window_info=object(),
                         current_f_score=.99, open_door_templates=[open_score],
                         cv2=SimpleNamespace(matchTemplate=lambda image, template, mode: template,
                                             minMaxLoc=lambda score: (0, score, None, None), TM_CCOEFF_NORMED=1),
                         win32api=SimpleNamespace(keybd_event=inputs),
                         win32con=SimpleNamespace(KEYEVENTF_KEYUP=2),
                         bot_state='APPROACH_DOOR', print=Mock(), has_aligned_door=aligned,
                         stop_all=Mock(), last_generic_f_at=100-since_f, last_door_diagnostic=0,
                         frame_captured_at=99, generic_f_recorder=SimpleNamespace(submit=Mock(return_value=True)),
                         dist=20, ground_started_at=0, loop_started_at=99)
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        if door is not None:
            update = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                          and ast.unparse(n.test) == 'valid_door_box' and 'door_was_aligned' in ast.unparse(n))
            namespace.update(valid_door_box=door, center_x=960, global_last_door_time=99)
            exec(compile(ast.Module(body=[update], type_ignores=[]), '<update>', 'exec'), namespace)
        interceptor = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                           and n.body and ast.unparse(n.body[0]) == 'push_started_at = time.perf_counter()')
        exec(compile(ast.Module(body=[interceptor], type_ignores=[]), '<interceptor>', 'exec'), namespace)
        if namespace['bot_state'] == 'VERIFY_DOOR':
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

    def test_new_visible_misalignment_prevents_entry_despite_old_true_flag(self):
        namespace, inputs = self.verify(.95, aligned=True, door=dict(x=960, w=90, h=300))
        self.assertFalse(namespace['has_aligned_door'])
        self.assertEqual(namespace['bot_state'], 'APPROACH_DOOR')
        inputs.assert_not_called()

    def test_generic_f_cooldown_blocks_exterior_sequence_until_five_seconds(self):
        namespace, inputs = self.verify(.3, since_f=4.99)
        self.assertEqual(namespace['bot_state'], 'APPROACH_DOOR')
        inputs.assert_not_called()
        namespace, inputs = self.verify(.3, since_f=5.0)
        self.assertEqual(namespace['bot_state'], 'EXTERIOR_PICKUP')
        self.assertEqual(inputs.call_count, 2)

    def test_push_door_is_independent_of_generic_f_cooldown(self):
        namespace, inputs = self.verify(.95, since_f=0.1)
        self.assertEqual(namespace['bot_state'], 'ITEM_PICKUP')
        self.assertEqual(inputs.call_count, 2)
