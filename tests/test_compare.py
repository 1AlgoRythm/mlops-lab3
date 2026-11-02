"""Tests for compare.py: small functions, a tiny corpus worked out by hand, and the real plays
checked against a plain-Python recount that uses no Beam."""
import csv
from collections import Counter
from pathlib import Path

import pytest

from compare import PlayStats, find_genres, genre_rows, pick_extremes, play_key, rows_to_csv, run_compare
from wordcount import find_words

ROOT = Path(__file__).resolve().parent.parent


def read_csv(path):
    return list(csv.reader(Path(path).open()))



# --- small functions ------------------------------------------------------------------------

def test_play_key_reads_genre_and_play_from_the_path():
    assert play_key('plays/tragedies/hamlet.txt') == ('tragedies', 'hamlet')


def make_play(root, genre, play, text='word\n'):
    folder = root / genre
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (play + '.txt')).write_text(text)


def test_find_genres_returns_the_two_folder_names_sorted(tmp_path):
    make_play(tmp_path, 'tragedies', 'a')
    make_play(tmp_path, 'comedies', 'b')
    assert find_genres(str(tmp_path / '*/*.txt')) == ('comedies', 'tragedies')


@pytest.mark.parametrize('genres', [['only'], ['a', 'b', 'c']])
def test_find_genres_needs_exactly_two(tmp_path, genres):
    for genre in genres:
        make_play(tmp_path, genre, 'play')
    with pytest.raises(ValueError, match='exactly 2 genre folders'):
        find_genres(str(tmp_path / '*/*.txt'))


def test_play_stats_folds_counts_into_words_and_distinct():
    fn = PlayStats()
    accumulator = fn.create_accumulator()
    for count in (5, 2, 1):
        accumulator = fn.add_input(accumulator, count)
    assert fn.extract_output(accumulator) == (8, 3)


def test_play_stats_merges_partial_results():
    fn = PlayStats()
    assert fn.merge_accumulators([(8, 3), (4, 2), (0, 0)]) == (12, 5)


def test_genre_rows_worked_example():
    # per 10,000 words, with 0.5 added: a = 10.5/1000, b = 40.5/2000
    rows = genre_rows('word', [('a', 10, 2), ('b', 40, 3)], {'a': 1000, 'b': 2000}, ('a', 'b'), 1, 1)
    assert rows == [('word', 'b', 10, 40, 105.0, 202.5, 1.929, 5)]


def test_genre_rows_counts_a_missing_genre_as_zero():
    rows = genre_rows('word', [('b', 30, 3)], {'a': 1000, 'b': 1000}, ('a', 'b'), 1, 1)
    assert rows[0][2:4] == (0, 30) and rows[0][1] == 'b'


def test_genre_rows_drops_words_in_too_few_plays_or_said_too_few_times():
    totals = {'a': 1000, 'b': 1000}
    assert genre_rows('word', [('a', 50, 2)], totals, ('a', 'b'), 3, 1) == []
    assert genre_rows('word', [('a', 5, 3)], totals, ('a', 'b'), 1, 30) == []


def test_genre_rows_ignores_one_letter_tokens():
    assert genre_rows('t', [('a', 99, 5)], {'a': 1000, 'b': 1000}, ('a', 'b'), 1, 1) == []


def test_pick_extremes_keeps_top_n_on_each_side():
    rows = [('w1', 'b', 0, 0, 0, 0, 3.0, 1), ('w2', 'b', 0, 0, 0, 0, 2.0, 1),
            ('w3', 'a', 0, 0, 0, 0, 0.5, 1), ('w4', 'a', 0, 0, 0, 0, 0.25, 1)]
    assert [row[0] for row in pick_extremes(rows, 1)] == ['w1', 'w4']
    assert [row[0] for row in pick_extremes(rows, 5)] == ['w1', 'w2', 'w4', 'w3']


def test_rows_to_csv():
    assert rows_to_csv([('a', 1, 2.5), ('b', 3, 4.0)]) == 'a,1,2.5\nb,3,4.0'


# --- a tiny corpus, worked out by hand ------------------------------------------------------

def test_tiny_corpus_gives_the_numbers_worked_out_by_hand(tmp_path):
    plays = tmp_path / 'plays'
    make_play(plays, 'x', 'p1', 'alpha alpha beta\n')
    make_play(plays, 'x', 'p2', 'alpha gamma\n')
    make_play(plays, 'y', 'p3', 'alpha beta beta\n')
    make_play(plays, 'y', 'p4', 'beta delta\n')
    stop = tmp_path / 'stop.txt'
    stop.write_text('\n')
    out = tmp_path / 'out'
    run_compare(str(plays / '*/*.txt'), str(out), str(stop), min_plays=1, min_count=1)

    assert read_csv(out / 'play_stats.csv') == [
        ['genre', 'play', 'words', 'distinct_words', 'distinct_per_word'],
        ['x', 'p1', '3', '2', '0.6667'], ['x', 'p2', '2', '2', '1.0'],
        ['y', 'p3', '3', '2', '0.6667'], ['y', 'p4', '2', '2', '1.0']]

    assert read_csv(out / 'play_top_words.csv') == [
        ['genre', 'play', 'rank', 'word', 'count'],
        ['x', 'p1', '1', 'alpha', '2'], ['x', 'p1', '2', 'beta', '1'],
        ['x', 'p2', '1', 'alpha', '1'], ['x', 'p2', '2', 'gamma', '1'],
        ['y', 'p3', '1', 'beta', '2'], ['y', 'p3', '2', 'alpha', '1'],
        ['y', 'p4', '1', 'beta', '1'], ['y', 'p4', '2', 'delta', '1']]

    assert read_csv(out / 'genre_words.csv') == [
        ['word', 'favours', 'x_count', 'y_count', 'x_per_10k', 'y_per_10k', 'ratio_y_over_x', 'plays'],
        ['delta', 'y', '0', '1', '1000.0', '3000.0', '3.0', '1'],
        ['beta', 'y', '1', '3', '3000.0', '7000.0', '2.333', '3'],
        ['gamma', 'x', '1', '0', '3000.0', '1000.0', '0.333', '1'],
        ['alpha', 'x', '3', '1', '7000.0', '3000.0', '0.429', '3']]


def test_one_genre_raises_a_clear_error_and_writes_nothing(tmp_path):
    plays = tmp_path / 'plays'
    make_play(plays, 'only', 'p1')
    out = tmp_path / 'out'
    with pytest.raises(ValueError, match='exactly 2 genre folders'):
        run_compare(str(plays / '*/*.txt'), str(out), str(ROOT / 'stopwords.txt'))
    assert not (out / 'play_stats.csv').exists()


def test_a_threshold_below_one_is_refused(tmp_path):
    plays = tmp_path / 'plays'
    make_play(plays, 'x', 'p1')
    make_play(plays, 'y', 'p2')
    with pytest.raises(ValueError, match='must be 1 or more'):
        run_compare(str(plays / '*/*.txt'), str(tmp_path / 'out'), str(ROOT / 'stopwords.txt'), min_plays=0)


# --- the real plays, checked against a plain-Python recount ---------------------------------

@pytest.fixture(scope='module')
def recount():
    """Count every play with collections.Counter. No Beam is used here."""
    plays = {}
    for path in sorted((ROOT / 'plays').glob('*/*.txt')):
        counter = Counter()
        for line in path.read_text().splitlines():
            counter.update(find_words(line))
        plays[(path.parent.name, path.stem)] = counter
    return plays


def test_real_play_stats_match_the_recount(real_run, recount):
    rows = read_csv(real_run / 'play_stats.csv')[1:]
    assert len(rows) == 8
    for genre, play, words, distinct, variety in rows:
        counter = recount[(genre, play)]
        assert int(words) == sum(counter.values())
        assert int(distinct) == len(counter)
        assert float(variety) == round(len(counter) / sum(counter.values()), 4)


def test_real_king_lear_matches_the_lab_numbers(real_run):
    rows = {play: (int(words), int(distinct)) for _, play, words, distinct, _ in
            read_csv(real_run / 'play_stats.csv')[1:]}
    assert rows['kinglear'] == (27986, 4176)  # the same numbers wordcount.py gives for data/


def test_real_top_words_match_the_recount(real_run, recount):
    stopwords = {line.strip() for line in (ROOT / 'stopwords.txt').read_text().split() if line.strip()}
    expected = {}
    for key, counter in recount.items():
        kept = [(word, count) for word, count in counter.items() if word not in stopwords]
        kept.sort(key=lambda pair: (-pair[1], pair[0]))
        expected[key] = kept[:10]
    got = {}
    for genre, play, rank, word, count in read_csv(real_run / 'play_top_words.csv')[1:]:
        got.setdefault((genre, play), []).append((word, int(count)))
    assert got == expected


def test_real_genre_words_match_the_recount(real_run, recount):
    totals, genre_counts, genre_plays = Counter(), {}, {}
    for (genre, _), counter in recount.items():
        totals[genre] += sum(counter.values())
        for word, count in counter.items():
            genre_counts.setdefault(word, Counter())[genre] += count
            genre_plays.setdefault(word, Counter())[genre] += 1
    rows = []
    for word, counts in genre_counts.items():
        plays = sum(genre_plays[word].values())
        if len(word) == 1 or plays < 3 or sum(counts.values()) < 30:
            continue
        rate = {g: (counts[g] + 0.5) / totals[g] * 10000 for g in ('comedies', 'tragedies')}
        rows.append((word, rate['tragedies'] / rate['comedies']))
    tragic = sorted((r for r in rows if r[1] > 1), key=lambda r: (-r[1], r[0]))[:15]
    comic = sorted((r for r in rows if r[1] <= 1), key=lambda r: (r[1], r[0]))[:15]
    got = [(row[0], float(row[6])) for row in read_csv(real_run / 'genre_words.csv')[1:]]
    assert [w for w, _ in got] == [w for w, _ in tragic + comic]
    for (_, got_ratio), (_, want_ratio) in zip(got, tragic + comic):
        assert got_ratio == pytest.approx(want_ratio, abs=0.001)
