"""Tests for section 6: speeches per character, and word lengths per genre."""
import csv
import re
from collections import Counter
from pathlib import Path

import pytest

from compare import play_key
from speakers import (count_spoken, length_row, parse_speeches, run_speakers, run_word_lengths,
                      top_speakers)
from wordcount import find_words

ROOT = Path(__file__).resolve().parent.parent

# A tiny play. Worked out by hand: Alice says 7 words (a stage direction is not counted), then Bob 1,
# Alice 1, Bob 2, and Carol 1 (her stage direction runs over two lines).
TINY = (
    "CAST\tcast list entry\n"
    "ACT I\n"
    "SCENE I\tA road.\n"
    "ALICE\tHello there, friend. [Aside] hush\n"
    "\tHow are you?\n"
    "\t[Exit]\n"
    "BOB\tFine.\n"
    "Alice\tGood.\n"
    "ACT II\n"
    "\tstray indented line is ignored\n"
    "BOB\tYes indeed\n"
    "CAROL:\t[Enter] Hi [Exit\n"
    "\ttwo lines]\n"
)


def read_csv(path):
    return list(csv.reader(Path(path).open()))


def write_play(root, genre, play, text):
    folder = root / genre
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (play + '.txt')).write_text(text)


# --- the parser -----------------------------------------------------------------------------

def test_parse_speeches_worked_example():
    assert parse_speeches(TINY) == [('Alice', 7), ('Bob', 1), ('Alice', 1), ('Bob', 2), ('Carol', 1)]


def test_a_text_with_no_first_act_has_no_speeches():
    assert parse_speeches('CAST\tcast list entry\nBOB\tFine.\n') == []


def test_count_spoken_drops_stage_directions_even_over_two_lines():
    assert count_spoken('Hi [Exit\n two lines] there') == 2


def test_a_scene_line_is_not_a_speaker():
    assert parse_speeches('ACT I\nSCENE I\tA desert place.\n\tstray\nBOB\thi\n') == [('Bob', 1)]


def test_top_speakers_breaks_ties_by_words_then_name():
    speakers = [('Zed', 2, 5), ('Amy', 2, 5), ('Bo', 2, 9), ('Cy', 1, 99)]
    rows = top_speakers(('x', 'p'), speakers, 3)
    assert [row[3] for row in rows] == ['Bo', 'Amy', 'Zed'] and [row[2] for row in rows] == [1, 2, 3]


def test_length_row_gives_the_percent_of_the_genre():
    assert length_row((('x', 3), 1), {'x': 4}) == ('x', 3, 1, 25.0)


# --- the speaker pipeline, worked by hand ---------------------------------------------------

def test_tiny_corpus_speakers(tmp_path):
    plays = tmp_path / 'plays'
    write_play(plays, 'x', 'p1', TINY)
    write_play(plays, 'y', 'p2', 'CAST\tx\nACT I\nZED\tone two three\nZED\tfour\n')
    run_speakers(str(plays / '*/*.txt'), str(tmp_path / 'out'), top_n=2)
    assert read_csv(tmp_path / 'out' / 'speakers.csv') == [
        ['genre', 'play', 'rank', 'speaker', 'speeches', 'words'],
        ['x', 'p1', '1', 'Alice', '2', '8'], ['x', 'p1', '2', 'Bob', '2', '3'],
        ['y', 'p2', '1', 'Zed', '2', '4']]


def test_bad_speaker_input_is_refused(tmp_path):
    with pytest.raises(ValueError, match='no file matches'):
        run_speakers(str(tmp_path / 'nothing*.txt'), str(tmp_path / 'out'))
    with pytest.raises(ValueError, match='top_n must be 1 or more'):
        run_speakers(str(ROOT / 'plays/*/*.txt'), str(tmp_path / 'out'), top_n=0)
    assert not (tmp_path / 'out' / 'speakers.csv').exists()


# --- the real plays, checked against a second method ----------------------------------------

def regex_speeches(text):
    """A different method: one regular expression over the text after the first 'ACT I' line."""
    start = re.search(r'(?m)^[ \t]*ACT I[ \t]*$', text).end()
    return [(m.group(1).strip().rstrip(':').strip().title(),
             len(find_words(re.sub(r'\[[^\]]*\]', ' ', m.group(2)))))
            for m in re.finditer(r'(?ms)^(?!(?:ACT|SCENE)\b)([^\s][^\t\n]*)\t(.*?)(?=^\S|\Z)', text[start:])]


def test_the_parser_agrees_with_the_regex_method_on_every_real_speech():
    for path in sorted((ROOT / 'plays').glob('*/*.txt')):
        text = path.read_text()
        assert parse_speeches(text) == regex_speeches(text), path.name


def test_real_speakers_csv_matches_the_recount(real_speakers):
    expected = {}
    for path in sorted((ROOT / 'plays').glob('*/*.txt')):
        totals = {}
        for speaker, words in regex_speeches(path.read_text()):
            speeches, spoken = totals.get(speaker, (0, 0))
            totals[speaker] = (speeches + 1, spoken + words)
        ranked = sorted(totals.items(), key=lambda item: (-item[1][0], -item[1][1], item[0]))[:5]
        expected[play_key(str(path))] = [(speaker, speeches, words) for speaker, (speeches, words) in ranked]
    got = {}
    for genre, play, rank, speaker, speeches, words in read_csv(real_speakers / 'speakers.csv')[1:]:
        got.setdefault((genre, play), []).append((speaker, int(speeches), int(words)))
    assert got == expected


def test_no_real_speaker_name_has_a_comma(real_speakers):
    assert all(',' not in row[3] for row in read_csv(real_speakers / 'speakers.csv')[1:])


# --- word lengths ---------------------------------------------------------------------------

def test_tiny_corpus_word_lengths(tmp_path):
    plays = tmp_path / 'plays'
    write_play(plays, 'x', 'p1', 'a bb ccc bb\n')
    write_play(plays, 'y', 'p2', 'dddd abcdefghijklmnopqr\n')
    run_word_lengths(str(plays / '*/*.txt'), str(tmp_path / 'out'))
    assert read_csv(tmp_path / 'out' / 'word_lengths.csv') == [
        ['genre', 'length', 'words', 'percent'],
        ['x', '1', '1', '25.0'], ['x', '2', '2', '50.0'], ['x', '3', '1', '25.0'],
        ['y', '4', '1', '50.0'], ['y', '15', '1', '50.0']]  # the 18-letter word is pooled at 15


def test_a_longest_below_one_is_refused(tmp_path):
    with pytest.raises(ValueError, match='longest must be 1 or more'):
        run_word_lengths(str(ROOT / 'plays/*/*.txt'), str(tmp_path / 'out'), longest=0)


def test_real_word_lengths_match_a_recount(real_lengths):
    expected = Counter()
    for path in (ROOT / 'plays').glob('*/*.txt'):
        for line in path.read_text().splitlines():
            for word in find_words(line):
                expected[(play_key(str(path))[0], min(len(word), 15))] += 1
    got = {(genre, int(length)): int(words) for genre, length, words, _ in
           read_csv(real_lengths / 'word_lengths.csv')[1:]}
    assert got == dict(expected)


def test_real_word_length_percents_add_up_to_100_for_each_genre(real_lengths):
    rows = read_csv(real_lengths / 'word_lengths.csv')[1:]
    for genre in ('comedies', 'tragedies'):
        assert sum(float(row[3]) for row in rows if row[0] == genre) == pytest.approx(100, abs=0.1)


def test_word_lengths_agree_with_the_play_stats_of_the_comparison(real_lengths, real_run):
    stats = read_csv(real_run / 'play_stats.csv')[1:]
    lengths = read_csv(real_lengths / 'word_lengths.csv')[1:]
    for genre in ('comedies', 'tragedies'):
        assert (sum(int(row[2]) for row in stats if row[0] == genre)
                == sum(int(row[2]) for row in lengths if row[0] == genre))
