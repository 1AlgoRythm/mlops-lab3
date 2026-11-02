"""The notebook is the deliverable. Its six original cells are kept, it runs from top to bottom in a
clean copy of the repo, and its saved outputs show the results."""
import collections
import hashlib
import json
import shutil
import socket
from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / 'Try_Apache_Beam_Python.ipynb'

# sha256 of the six original cells of the course notebook (type and source), taken before any change
ORIGINAL_CELLS_SHA256 = 'e9c71c251388be21b6ce70e87a1f0b78022b393c9a905fc1e305796b303fdeb4'
GSUTIL_LINE = "run('gsutil cp gs://dataflow-samples/shakespeare/kinglear.txt data/')"

EXPECTED = [
    'different "words" in the lab output: 4784',
    'the: 786    The: 122',
    'a lone quote mark was counted 15 times',
    'different words after lowercasing: 4215',
    "counters: {'lines': 5525, 'lines_without_words': 1665, 'words': 27986}",
    'the,910',
    'king,311',
    'stopped: no file matches',
    '8 plays verified',
    'tragedies,kinglear,27986,4176',
    'castle,tragedies',
]


def cells():
    return json.loads(NOTEBOOK.read_text())['cells']


def stream_text(code_cells):
    return ''.join(''.join(output.get('text', '')) for cell in code_cells if cell['cell_type'] == 'code'
                   for output in cell.get('outputs', []) if output['output_type'] == 'stream')


def test_the_six_original_cells_are_unchanged():
    digest = hashlib.sha256(json.dumps(
        [[cell['cell_type'], ''.join(cell['source'])] for cell in cells()[:6]]).encode()).hexdigest()
    assert digest == ORIGINAL_CELLS_SHA256


def test_the_original_cells_keep_their_own_saved_outputs():
    assert cells()[4]['outputs'] and 'KING' in stream_text(cells()[4:5])


def test_the_new_cells_are_tagged_for_the_three_exported_groups():
    tags = collections.Counter(tag for cell in cells() for tag in cell['metadata'].get('tags', []))
    assert set(tags) == {'wordcount', 'compare', 'report'}
    assert all(count >= 5 for count in tags.values())


def test_the_saved_outputs_show_the_results_and_no_errors():
    saved = cells()[6:]
    text = stream_text(saved)
    for expected in EXPECTED:
        assert expected in text, expected
    outputs = [output for cell in saved if cell['cell_type'] == 'code' for output in cell.get('outputs', [])]
    assert not [o for o in outputs if o['output_type'] == 'error']
    assert not [o for o in outputs if o['output_type'] == 'stream' and o['name'] == 'stderr']
    assert any(o['output_type'] == 'display_data' and 'text/html' in o['data'] for o in outputs)


def test_the_notebook_runs_top_to_bottom_in_a_clean_copy(tmp_path):
    for name in ('data', 'plays', 'docs'):
        shutil.copytree(ROOT / name, tmp_path / name)
    (tmp_path / 'outputs').mkdir()
    shutil.copy(ROOT / 'outputs' / 'part-00000-of-00001', tmp_path / 'outputs')
    raw = json.loads(NOTEBOOK.read_text())
    setup = ''.join(raw['cells'][2]['source'])
    assert GSUTIL_LINE in setup
    # the lab downloads King Lear with gsutil; the file is already in data/, so only that line is skipped
    raw['cells'][2]['source'] = setup.replace(GSUTIL_LINE, 'pass').splitlines(True)
    notebook = nbformat.reads(json.dumps(raw), as_version=4)
    NotebookClient(notebook, timeout=900, kernel_name='python3',
                   resources={'metadata': {'path': str(tmp_path)}}).execute()  # raises if any cell fails
    text = stream_text(notebook.cells[6:])
    for expected in EXPECTED:
        assert expected in text, expected
    assert (tmp_path / 'outputs' / 'report.html').read_text().count('<svg') == 3
    # the notebook writes the stopword file itself, and it must equal the committed one
    assert (tmp_path / 'stopwords.txt').read_text() == (ROOT / 'stopwords.txt').read_text()


def online():
    try:
        socket.create_connection(('storage.googleapis.com', 443), timeout=3).close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(not online(), reason='needs the network')
def test_section_3_downloads_missing_plays_repairs_bad_ones_and_refuses_a_wrong_checksum(tmp_path, monkeypatch):
    namespace = {}
    for cell in cells():
        source = ''.join(cell['source'])
        if cell['cell_type'] == 'code' and ('PLAY_SHA256 = ' in source or 'def fetch_plays' in source):
            exec(compile(source.replace("print(fetch_plays(), 'plays verified')", ''), '<cell>', 'exec'), namespace)
    monkeypatch.chdir(tmp_path)  # an empty folder, so every play must be downloaded
    assert namespace['fetch_plays']() == 8
    assert len(list((tmp_path / 'plays').glob('*/*.txt'))) == 8
    for relative in namespace['PLAY_SHA256']:  # the same bytes as the committed copies
        assert (tmp_path / 'plays' / relative).read_bytes() == (ROOT / 'plays' / relative).read_bytes()
    (tmp_path / 'plays/tragedies/hamlet.txt').write_bytes(b'corrupt')
    namespace['fetch_plays']()
    assert (tmp_path / 'plays/tragedies/hamlet.txt').read_bytes() == (ROOT / 'plays/tragedies/hamlet.txt').read_bytes()
    namespace['PLAY_SHA256']['comedies/twelfthnight.txt'] = '0' * 64
    (tmp_path / 'plays/comedies/twelfthnight.txt').write_bytes(b'x')
    with pytest.raises(ValueError, match='checksum mismatch'):
        namespace['fetch_plays']()
