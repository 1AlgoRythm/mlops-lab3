"""The numbers in README.md must come from a real run, so a wrong number fails a test."""
import csv
import doctest
from pathlib import Path

from report import title_of
from wordcount import find_words

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / 'README.md').read_text()


def read_csv(path):
    return list(csv.DictReader(Path(path).open()))


def test_readme_table_of_plays_matches_the_real_run(real_run):
    for row in read_csv(real_run / 'play_stats.csv'):
        line = '| {} | {} | {:,} | {:,} | {} |'.format(
            title_of(row['play']), row['genre'], int(row['words']), int(row['distinct_words']),
            row['distinct_per_word'])
        assert line in README, line


def test_readme_genre_word_rates_match_the_real_run(real_run):
    rows = {row['word']: row for row in read_csv(real_run / 'genre_words.csv')}
    for word in ('castle', 'ghost', 'king', 'witch', 'doctor', 'bottom', 'niece', 'count', 'forest', 'sad'):
        tragedies = float(rows[word]['tragedies_per_10k'])
        comedies = float(rows[word]['comedies_per_10k'])
        # the README always lists the rate in tragedies first, then in comedies
        assert '`{}` ({:.2f} and {:.2f})'.format(word, tragedies, comedies) in README, word


def test_readme_says_bottom_is_mostly_one_character():
    def uses(path, word):
        return sum(find_words(line).count(word) for line in path.read_text().splitlines())

    dream = uses(ROOT / 'plays/comedies/midsummersnightsdream.txt', 'bottom')
    comedies = sum(uses(path, 'bottom') for path in (ROOT / 'plays/comedies').glob('*.txt'))
    assert 'bottom` is a character: {} of its {} uses'.format(dream, comedies) in README


def test_readme_code_examples_run():
    result = doctest.testfile(str(ROOT / 'README.md'), module_relative=False)
    assert result.attempted == 5 and result.failed == 0
