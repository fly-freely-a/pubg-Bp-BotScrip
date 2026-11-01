import ast
from pathlib import Path
import unittest


class DoorInteractionRulesTests(unittest.TestCase):
    def decide(self, door_score, f_score, aligned, state='APPROACH_DOOR'):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'logic/bot.py').read_text())
        names = {'found_door_prompt', 'door_ready', 'item_ready'}
        assignments = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
        assignments.sort(key=lambda n: n.lineno)
        namespace = dict(door_prompt_score=door_score, current_f_score=f_score,
                         has_aligned_door=aligned, bot_state=state)
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
