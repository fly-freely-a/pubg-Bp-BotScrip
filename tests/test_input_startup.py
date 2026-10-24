import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class InputStartupTests(unittest.TestCase):
    def test_directinput_is_configured_before_bot_import(self):
        source = Path(__file__).resolve().parents[1] / 'main.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        prefix = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == 'logic.bot':
                break
            prefix.append(node)
        direct = SimpleNamespace(FAILSAFE=True)
        auto = SimpleNamespace(FAILSAFE=True)
        with patch.dict('sys.modules', {'keyboard': SimpleNamespace(),
                                        'pyautogui': auto, 'pydirectinput': direct}):
            exec(compile(ast.Module(body=prefix, type_ignores=[]), str(source), 'exec'), {})
        self.assertFalse(direct.FAILSAFE)
        self.assertFalse(auto.FAILSAFE)
