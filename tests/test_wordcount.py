"""Tests for wordcount.py. Small functions first, then the Beam steps, then a full run."""
import csv
import subprocess
import sys
from pathlib import Path

import apache_beam as beam
import pytest
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

from wordcount import FindWords, check_input, find_words, load_stopwords, rank, to_csv

ROOT = Path(__file__).resolve().parent.parent


# --- find_words -----------------------------------------------------------------------------

def test_find_words_lowercases():
    assert find_words('The KING Lear') == ['the', 'king', 'lear']


def test_find_words_keeps_an_apostrophe_inside_a_word():
    assert find_words("don't o'er") == ["don't", "o'er"]


def test_find_words_drops_edge_apostrophes():
    assert find_words("'tis daughters' ") == ['tis', 'daughters']


def test_find_words_ignores_a_lone_quote_mark_digits_and_punctuation():
    assert find_words("' 42 -- , ;") == []


def test_find_words_on_an_empty_line():
    assert find_words('') == []


# --- rank, to_csv, load_stopwords, check_input -----------------------------------------------

def test_rank_sorts_by_count_then_word():
    pairs = [('b', 2), ('a', 2), ('c', 5), ('d', 1)]
    assert rank(pairs) == [('c', 5), ('a', 2), ('b', 2), ('d', 1)]


def test_rank_top_n_cuts_and_zero_keeps_all():
    pairs = [('b', 2), ('a', 2), ('c', 5)]
    assert rank(pairs, 2) == [('c', 5), ('a', 2)]
    assert rank(pairs, 0) == [('c', 5), ('a', 2), ('b', 2)]


def test_rank_breaks_a_tie_at_the_cut_by_word():
    assert rank([('z', 1), ('a', 1), ('m', 1)], 1) == [('a', 1)]


def test_to_csv_makes_one_line_per_pair():
    assert to_csv([('the', 9), ('of', 4)]) == 'the,9\nof,4'


def test_load_stopwords_ignores_blank_lines_and_case(tmp_path):
    path = tmp_path / 'stop.txt'
    path.write_text('The\n\nAND\n  of \n')
    assert load_stopwords(str(path)) == {'the', 'and', 'of'}


def test_check_input_accepts_a_real_file(tmp_path):
    (tmp_path / 'a.txt').write_text('hello\n')
    check_input(str(tmp_path / '*.txt'))


def test_check_input_rejects_no_match(tmp_path):
    with pytest.raises(ValueError, match='no file matches'):
        check_input(str(tmp_path / 'nothing*.txt'))


def test_check_input_rejects_only_empty_files(tmp_path):
    (tmp_path / 'a.txt').write_text('')
    with pytest.raises(ValueError, match='empty'):
        check_input(str(tmp_path / '*.txt'))


# --- the Beam steps, run on a tiny pipeline --------------------------------------------------

def test_find_words_step_emits_one_element_per_word():
    with TestPipeline() as pipeline:
        words = pipeline | beam.Create(['The cat', '', 'the DOG']) | beam.ParDo(FindWords())
        assert_that(words, equal_to(['the', 'cat', 'the', 'dog']))


def test_count_step_adds_up_the_same_word():
    with TestPipeline() as pipeline:
        counts = (
            pipeline
            | beam.Create(['The cat', 'the dog'])
            | beam.ParDo(FindWords())
            | beam.Map(lambda word: (word, 1))
            | beam.CombinePerKey(sum)
        )
        assert_that(counts, equal_to([('the', 2), ('cat', 1), ('dog', 1)]))


# --- a full run through the command line -----------------------------------------------------

def run_cli(tmp_path, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / 'wordcount.py'), '--output', str(tmp_path / 'out'), *args],
        capture_output=True, text=True, cwd=ROOT)


def test_full_run_writes_a_sorted_csv_with_header_and_counters(tmp_path):
    source = tmp_path / 'in'
    source.mkdir()
    (source / 'a.txt').write_text("The cat and the dog\n\nthe END, the 'end'\n")
    done = run_cli(tmp_path, '--input', str(source / '*.txt'), '--top-n', '3')
    assert done.returncode == 0, done.stderr[-500:]
    rows = list(csv.reader((tmp_path / 'out.csv').open()))
    assert rows == [['word', 'count'], ['the', '4'], ['end', '2'], ['and', '1']]
    assert 'lines 3, lines_without_words 1, words 9' in done.stdout


def test_full_run_with_stopwords_drops_them(tmp_path):
    source = tmp_path / 'a.txt'
    source.write_text('the king the king the lear\n')
    stop = tmp_path / 'stop.txt'
    stop.write_text('the\n')
    done = run_cli(tmp_path, '--input', str(source), '--stopwords', str(stop))
    assert done.returncode == 0, done.stderr[-500:]
    rows = list(csv.reader((tmp_path / 'out.csv').open()))
    assert rows == [['word', 'count'], ['king', '2'], ['lear', '1']]


def test_bad_input_exits_with_a_message_and_writes_nothing(tmp_path):
    done = run_cli(tmp_path, '--input', str(tmp_path / 'nothing*.txt'))
    assert done.returncode == 1
    assert 'no file matches' in done.stderr
    assert not (tmp_path / 'out.csv').exists()


def test_the_real_lab_data_gives_the_numbers_the_readme_states(tmp_path):
    done = run_cli(tmp_path, '--top-n', '0')
    assert done.returncode == 0, done.stderr[-500:]
    rows = list(csv.reader((tmp_path / 'out.csv').open()))[1:]
    assert len(rows) == 4176
    assert sum(int(count) for _, count in rows) == 27986
    assert rows[0] == ['the', '910']
