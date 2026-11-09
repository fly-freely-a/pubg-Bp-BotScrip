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

    def verify(self, open_score=.95, f_score=.99, first_push_seen=False, stopped_scores=None):
        inputs = Mock()
        stopped_frame = object()
        def match(image, template, mode):
            if image is stopped_frame:
                return stopped_scores[0 if template == f_score else 1]
            return template
        namespace = dict(time=SimpleNamespace(time=lambda: 100, sleep=Mock()), game_img=object(),
                         f_tmpl=f_score, door_tmpl=open_score,
                         cv2=SimpleNamespace(matchTemplate=match,
                                             minMaxLoc=lambda score: (0, score, None, None), TM_CCOEFF_NORMED=1),
                         win32api=SimpleNamespace(keybd_event=inputs),
                         win32con=SimpleNamespace(KEYEVENTF_KEYUP=2), verify_count=1,
                         bot_state='VERIFY_DOOR', first_push_seen=first_push_seen,
                         recheck_moving_door_f=stopped_scores is not None,
                         self=SimpleNamespace(capture_game_screen=lambda: (stopped_frame, None)), print=Mock(), stop_all=Mock(), pydirectinput=Mock())
        block = ast.For(target=ast.Name(id='_', ctx=ast.Store()), iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                        body=self.body('VERIFY_DOOR'), orelse=[])
        module = ast.fix_missing_locations(ast.Module(body=[block], type_ignores=[]))
        exec(compile(module, '<verify>', 'exec'), namespace)
        return namespace, inputs

    def test_generic_f_without_push_prompt_sends_f_and_loots_exterior(self):
        namespace, inputs = self.verify(.3)
        self.assertEqual(namespace['bot_state'], 'EXTERIOR_PICKUP')
        self.assertEqual(namespace['exterior_return_moves'], ())
        self.assertEqual([call.args for call in inputs.call_args_list], [(0x46, 0, 0, 0), (0x46, 0, 2, 0)])

    def test_moving_door_generic_f_must_still_be_present_after_stopping(self):
        for stopped_scores, expected, presses in (
            ((.45, .3), 'APPROACH_DOOR', 0),
            ((.95, .86), 'APPROACH_DOOR', 0),
            ((.95, .3), 'EXTERIOR_PICKUP', 2),
        ):
            with self.subTest(stopped_scores=stopped_scores):
                namespace, inputs = self.verify(.3, stopped_scores=stopped_scores)
                self.assertEqual(namespace['bot_state'], expected)
                self.assertEqual(inputs.call_count, presses)

    def test_normal_door_keeps_existing_entry(self):
        namespace, inputs = self.verify(.95, first_push_seen=True)
        self.assertEqual(namespace['bot_state'], 'ITEM_PICKUP')
        self.assertEqual(inputs.call_count, 2)

    def test_first_push_loots_outside_without_pressing_f(self):
        namespace, inputs = self.verify()
        self.assertEqual(namespace['bot_state'], 'EXTERIOR_PICKUP')
        self.assertEqual(namespace['exterior_moves'], (('d', 1.0), ('w', 0.8), ('a', 1.0)))
        self.assertEqual(namespace['exterior_return_moves'], (('d', 1.0), ('s', 3.5), ('a', 0.8)))
        self.assertTrue(namespace['first_push_seen'])
        inputs.assert_not_called()

    def test_generic_pickup_does_not_require_close_door_template(self):
        source = (Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text()
        self.assertNotIn('door2.png', source)
        self.assertNotIn('door3.png', source)

    def run_exterior_pickup(self, moves, return_moves):
        events = []
        info = object()
        namespace = dict(time=SimpleNamespace(time=lambda:100, sleep=lambda seconds:events.append(('wait', seconds))),
                         stop_all=lambda:events.append(('stop',)),
                         set_key=lambda key,state:events.append((key,state)),
                         pydirectinput=SimpleNamespace(press=lambda key:events.append(('press',key))),
                         self=SimpleNamespace(pickup_all_items_in_tab=lambda window:events.append(('pickup',window))),
                         current_window_info=info, print=Mock(), dist_history=[20, 25],
                         exterior_moves=moves, exterior_return_moves=return_moves,
                         push_door_aligned=True, is_skew_locked=True, last_aspect_ratio=.6)
        exec(compile(ast.Module(body=self.body('EXTERIOR_PICKUP'), type_ignores=[]), '<pickup>', 'exec'), namespace)
        self.assertEqual(namespace['bot_state'], 'COMPASS_RUSH')
        self.assertFalse(namespace['push_door_aligned'])
        self.assertFalse(namespace['is_skew_locked'])
        self.assertEqual(namespace['last_aspect_ratio'], 0.0)
        self.assertEqual(namespace['dist_history'], [])

        return events, info

    def test_exterior_sequence_moves_left_back_and_loots_without_forward(self):
        events, info = self.run_exterior_pickup((('a', .8), ('s', .7)), ())
        self.assertEqual(events, [('stop',), ('a', True), ('wait', .8), ('a', False),
                                  ('s', True), ('wait', .7), ('s', False),
                                  ('press','tab'), ('wait',1.), ('pickup',info),
                                  ('press','tab'), ('wait',.5)])

    def test_first_push_returns_after_closing_inventory(self):
        route, _ = self.verify()
        events, _ = self.run_exterior_pickup(route['exterior_moves'], route['exterior_return_moves'])
        self.assertEqual(events[-11:], [
            ('press', 'tab'), ('wait', .5),
            ('d', True), ('wait', 1.0), ('d', False),
            ('s', True), ('wait', 3.5), ('s', False),
            ('a', True), ('wait', 0.8), ('a', False),
        ])

    def test_f_at_threshold_does_not_interact(self):
        namespace, inputs = self.verify(.95, f_score=.72)
        self.assertEqual(namespace['bot_state'], 'COMPASS_RUSH')
        inputs.assert_not_called()

    def test_push_at_threshold_routes_to_exterior_and_logs_score(self):
        namespace, _ = self.verify(.70)
        self.assertEqual(namespace['bot_state'], 'EXTERIOR_PICKUP')
        self.assertIn('推门得分:0.7000', namespace['print'].call_args.args[0])

    def test_push_waits_for_recent_alignment_without_blocking_generic_f(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        branch = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                      and node.body and ast.unparse(node.body[0]) == 'ignore_f = False')
        module = compile(ast.Module(body=[branch], type_ignores=[]), '<intercept>', 'exec')
        for seen, aligned, age, after_step, push_score, expected in (
            (False, False, 0.1, False, .95, 'APPROACH_DOOR'),
            (False, True, 2.3, False, .95, 'APPROACH_DOOR'),
            (False, True, 2.3, True, .95, 'VERIFY_DOOR'),
            (False, True, 0.1, False, .95, 'VERIFY_DOOR'),
            (False, False, 0.1, False, .40, 'VERIFY_DOOR'),
            (True, False, 0.1, False, .95, 'APPROACH_DOOR'),
            (True, True, 0.1, False, .95, 'VERIFY_DOOR'),
            (True, True, 2.3, True, .95, 'VERIFY_DOOR'),
        ):
            with self.subTest(seen=seen, aligned=aligned, age=age, after_step=after_step, push_score=push_score):
                namespace = dict(bot_state='APPROACH_DOOR', current_f_score=.99, keys_pressed={'w': False},
                                 first_push_seen=seen, push_door_aligned=aligned, door_centered=True,
                                 aligned_after_step=after_step,
                                 global_last_door_time=100-age, last_door_diagnostic=100,
                                 f_tmpl=object(), game_img=object(), door_tmpl=object(),
                                 time=SimpleNamespace(time=lambda:100), stop_all=Mock(), print=Mock(),
                                 cv2=SimpleNamespace(matchTemplate=Mock(), TM_CCOEFF_NORMED=1,
                                                     minMaxLoc=lambda _: (0, push_score, None, None)))
                exec(module, namespace)
                self.assertEqual(namespace['bot_state'], expected)

    def test_only_a_complete_distant_door_frame_can_establish_alignment(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        branch = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                      and ast.unparse(node.test) == 'valid_door_box'
                      and 'door_height < near_door_height' in ast.unparse(node))
        module = compile(ast.Module(body=[branch], type_ignores=[]), '<door-alignment>', 'exec')
        namespace = dict(bot_state='APPROACH_DOOR', push_door_aligned=False, center_x=960,
                         h=1080, near_door_height=432, door_center_limit=120, time=SimpleNamespace(time=lambda: 100),
                         print=Mock())

        for height, y, width, offset, expected in (
            (1017, 540, 550, 41.2, False),  # 贴脸门框
            (300, 150, 150, 41.2, False),   # 上边缘被裁掉
            (300, 350, 150, 121, False),     # 超出居中门槛
            (300, 350, 150, 120, True),      # 远处完整门框
            (1017, 540, 400, 41.2, True),   # 贴脸后保留远处的对齐
        ):
            with self.subTest(height=height, y=y, width=width, offset=offset):
                namespace['valid_door_box'] = dict(x=960 + offset, y=y, h=height, w=width)
                exec(module, namespace)
                self.assertEqual(namespace['push_door_aligned'], expected)
