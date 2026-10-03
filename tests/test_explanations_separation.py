"""Isolated regression checks for explanatory content (no Telegram/network)."""
import ast
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1].joinpath('manager_82.py').read_text()
manager = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Manager')
names = {'hub_sections', 'hub_default_items', 'hub_defaults_all', 'hub_made_keys',
         'hub_defaults_on', 'hub_default_text', 'hub_view', 'hub_intro', 'hub_page_size',
         'hub_default_row', 'hub_pages'}
body = [n for n in manager.body if isinstance(n, ast.FunctionDef) and n.name in names
        or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'HUB_DEFAULTS' for t in n.targets)]
module = ast.Module(body=[ast.ClassDef(name='Hub', bases=[], keywords=[], body=body, decorator_list=[])], type_ignores=[])
ns = {'B': lambda label, data, *args: (label, data), 'back_btn': lambda data: [('back', data)], '_fa_digits': str}
exec(compile(ast.fix_missing_locations(module), '<hub>', 'exec'), ns)

class ExplanationsTests(unittest.TestCase):
    def setUp(self):
        self.h = ns['Hub']()
        self.h.cfg = {}
        self.h.LINE = '---'
        self.sections = []
        self.h.tut_sections = lambda on_only=False: [s for s in self.sections if not on_only or s['on']]

    def test_legacy_tutorials_do_not_replace_explanations(self):
        self.sections.append(dict(id=1, preset='wallet', in_hub=True, on=True))
        self.assertEqual(self.h.hub_sections(), [])
        keys = {d[0] for d in self.h.hub_default_items()}
        self.assertTrue({'start', 'phone', 'verify', 'panel'} <= keys)
        _, rows = self.h.hub_view()
        self.assertNotIn('m:tut', [b[1] for row in rows for b in row])

    def test_converted_explanation_replaces_only_its_default(self):
        self.sections.append(dict(id=2, preset='hub:start', in_hub=True, on=True))
        self.assertEqual(len(self.h.hub_sections()), 1)
        keys = {d[0] for d in self.h.hub_default_items()}
        self.assertNotIn('start', keys)
        self.assertIn('phone', keys)
        self.sections[0]['in_hub'] = False
        self.assertEqual(self.h.hub_sections(), [])

    def test_content_explains_instead_of_teaching_steps(self):
        for key, *_ in self.h.HUB_DEFAULTS:
            text = self.h.hub_default_text(key)
            self.assertTrue(text, key)
            self.assertNotIn('<b>قدم', text, key)
        self.assertIn('شماره', self.h.hub_default_text('phone'))
        self.assertIn('نشست', self.h.hub_default_text('verify'))
        self.assertIn('محدودیت', self.h.hub_default_text('start'))

    def test_pagination_counts_defaults(self):
        self.h.cfg['hub_page_size'] = 4
        self.assertEqual(self.h.hub_pages(), 4)

if __name__ == '__main__':
    unittest.main()
