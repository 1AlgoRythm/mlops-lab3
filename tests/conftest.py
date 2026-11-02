"""Shared fixtures."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope='session')
def real_run(tmp_path_factory):
    """Run compare.py once on the real plays and return the output folder."""
    out = tmp_path_factory.mktemp('real')
    done = subprocess.run([sys.executable, str(ROOT / 'compare.py'), '--output-dir', str(out)],
                          capture_output=True, text=True, cwd=ROOT)
    assert done.returncode == 0, done.stderr[-600:]
    return out
