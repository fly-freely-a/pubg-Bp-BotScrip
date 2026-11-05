import ast
from pathlib import Path
import unittest
from types import SimpleNamespace


class DoorInteractionRulesTests(unittest.TestCase):
    def decide(self, door_score, f_score, aligned, state='APPROACH_DOOR', since_f=5.0):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        names = {'found_door_prompt', 'door_ready', 'item_ready'}
        assignments = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
        assignments.sort(key=lambda n: n.lineno)
        namespace = dict(door_prompt_score=door_score, current_f_score=f_score,
                         has_aligned_door=aligned, bot_state=state,
                         time=SimpleNamespace(time=lambda: 100.0), last_generic_f_at=100.0 - since_f)
        exec(compile(ast.Module(body=assignments, type_ignores=[]), '<rules>', 'exec'), namespace)
        return namespace['door_ready'], namespace['item_ready']

    def test_aligned_door_does_not_require_f_icon(self):
        self.assertEqual(self.decide(.89, .1, True), (True, False))

    def test_unaligned_door_cannot_fall_back_to_item_pickup(self):
        self.assertEqual(self.decide(.89, .99, False), (False, False))

    def test_item_does_not_require_alignment(self):
        self.assertEqual(self.decide(.3, .99, False, 'RUNNING'), (False, True))

    def test_no_prompt_does_not_interact(self):
        self.assertEqual(self.decide(.3, .3, True), (False, False))

    def test_stale_alignment_outside_door_approach_cannot_open(self):
        self.assertEqual(self.decide(.89, .99, True, 'COMPASS_RUSH'), (False, False))

    def test_non_push_f_prompt_interacts_without_entry(self):
        self.assertEqual(self.decide(.54, .99, False), (False, True))

    def test_only_full_push_prompt_template_is_loaded(self):
        source = (Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text()
        self.assertNotIn('door3.png', source)
        self.assertNotIn('door2.png', source)
        self.assertIn('open_door_templates = [door_tmpl]', source)

    def test_generic_f_requires_five_seconds_between_interactions(self):
        self.assertEqual(self.decide(.3, .99, False, since_f=4.99), (False, False))
        self.assertEqual(self.decide(.3, .99, False, since_f=5.0), (False, True))

    def test_push_door_is_not_blocked_by_generic_f_cooldown(self):
        self.assertEqual(self.decide(.89, .99, True, since_f=0.1), (True, False))
