"""Windows and Linux packages ship only neptune_engine.FILES (plus their launchers): every engine module the helper
imports must be listed, or those helpers fail to start (as 6.5.42–6.5.44 / 6.6.33–6.6.35 did without neptune_layouts)."""
import ast
from pathlib import Path
import unittest

import neptune_engine

HERE = Path(__file__).resolve().parent
# Shipped by the Windows/Linux builders from trainer-app/, not from FILES.
LAUNCHERS = {'neptune_trainer.py', 'neptune_windows_update.py', 'neptune_update_apply.py',
             'neptune_trainer_entry.py', 'neptune_trainer_pairing.py'}


def imported_modules(start):
    engine = {p.stem for p in HERE.glob('neptune_*.py') if not p.name.startswith('test_')}
    seen, todo = set(), list(start)
    while todo:
        name = todo.pop()
        if name in seen or name not in engine:
            continue
        seen.add(name)
        for node in ast.walk(ast.parse((HERE / (name + '.py')).read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            todo += [n.split('.')[0] for n in names]
    return seen


class PackageFilesTests(unittest.TestCase):
    def test_every_module_the_helper_imports_ships(self):
        files = set(neptune_engine.FILES) | LAUNCHERS
        missing = sorted(m + '.py' for m in imported_modules(['neptune_trainer', 'neptune_ui', 'neptune_telemetry'])
                         if m + '.py' not in files)
        self.assertEqual(missing, [], 'add these to neptune_engine.FILES')

    def test_listed_files_exist(self):
        self.assertEqual([f for f in neptune_engine.FILES if not (HERE / f).is_file()], [])


if __name__ == '__main__':
    unittest.main()
