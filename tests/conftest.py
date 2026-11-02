"""Shared fixtures. The code under test lives in the notebook, not in .py files.

The notebook's code cells tagged wordcount, compare or report are run into one module. It is then
registered under those three names, so a test can say `from compare import PlayStats`.
"""
import json
import logging
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / 'Try_Apache_Beam_Python.ipynb'
EXPORTED = {'wordcount', 'compare', 'report'}


def load_lab_module():
    """Run the tagged code cells of the notebook, in order, and return the module they build."""
    module = types.ModuleType('lab')
    for cell in json.loads(NOTEBOOK.read_text())['cells']:
        if cell['cell_type'] == 'code' and EXPORTED & set(cell['metadata'].get('tags', [])):
            exec(compile(''.join(cell['source']), '<notebook cell {}>'.format(cell['metadata']['id']), 'exec'),
                 module.__dict__)
    return module


# Beam logs a line when it stops its local Prism process, at exit, after pytest has closed its output
# streams. That log call fails and prints a long, harmless traceback. This switch hides it.
logging.raiseExceptions = False

lab = load_lab_module()
for name in EXPORTED | {'lab'}:
    sys.modules[name] = lab


@pytest.fixture(scope='session')
def real_run(tmp_path_factory):
    """Run the comparison once on the real plays and return the output folder."""
    out = tmp_path_factory.mktemp('real')
    lab.run_compare(str(ROOT / 'plays/*/*.txt'), str(out), str(ROOT / 'stopwords.txt'))
    return out
