"""Tests for report.py: the helpers, the page built from small fake data, and the real report."""
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from report import bar_path, nice_ticks, read_rows, render, tick_label, title_of

ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    """Collect what the tests need to know about a page."""

    def __init__(self):
        super().__init__()
        self.tags, self.titles, self.text, self._in_title = [], [], [], False
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)
        self._in_title = tag == 'title'

    def handle_endtag(self, tag):
        self._in_title = False

    def handle_data(self, data):
        self.text.append(data)
        if self._in_title:
            self.titles.append(data)


def parse(page):
    parser = Page()
    parser.feed(page)
    return parser


PLAYS = [
    {'genre': 'comedies', 'play': 'twelfthnight', 'words': '2000', 'distinct_words': '600', 'distinct_per_word': '0.3'},
    {'genre': 'tragedies', 'play': 'hamlet', 'words': '3000', 'distinct_words': '900', 'distinct_per_word': '0.3'},
]
TOP = [{'genre': 'tragedies', 'play': 'hamlet', 'rank': '1', 'word': 'ghost', 'count': '40'},
       {'genre': 'tragedies', 'play': 'hamlet', 'rank': '6', 'word': 'sixth', 'count': '1'},
       {'genre': 'comedies', 'play': 'twelfthnight', 'rank': '1', 'word': 'toby', 'count': '30'}]


def genre_row(word, favours, comedies, tragedies):
    return {'word': word, 'favours': favours, 'comedies_count': str(round(comedies * 3)),
            'tragedies_count': str(round(tragedies * 3)),
            'comedies_per_10k': str(comedies), 'tragedies_per_10k': str(tragedies),
            'ratio_tragedies_over_comedies': '1', 'plays': '4'}


GENRE = [genre_row('castle', 'tragedies', 0.5, 4.0), genre_row('niece', 'comedies', 4.0, 0.5),
         genre_row('forest', 'comedies', 5.0, 0.25)]


# --- helpers --------------------------------------------------------------------------------

@pytest.mark.parametrize('maximum, top, ticks', [
    (32396, 40000, [0, 10000, 20000, 30000, 40000]),
    (51.05, 60, [0, 20, 40, 60]),
    (8.33, 10, [0, 2, 4, 6, 8, 10]),
    (24, 25, [0, 5, 10, 15, 20, 25]),
])
def test_nice_ticks_give_clean_numbers(maximum, top, ticks):
    assert nice_ticks(maximum) == (top, ticks)


def test_tick_label_is_compact_from_a_thousand():
    assert [tick_label(v) for v in (0, 2.5, 20, 999, 10000, 40000)] == ['0', '2.5', '20', '999', '10K', '40K']


def test_bar_path_is_square_at_the_baseline_and_rounded_at_the_tip():
    assert bar_path(10, 0, 100, 20) == 'M10.0,0.0 H106.0 A4.0,4.0 0 0 1 110.0,4.0 V16.0 A4.0,4.0 0 0 1 106.0,20.0 H10.0 Z'


def test_bar_path_shrinks_the_radius_for_a_very_short_bar():
    assert 'A1.0,1.0' in bar_path(0, 0, 2, 20)


def test_title_of_known_and_unknown_plays():
    assert title_of('midsummersnightsdream') == "A Midsummer Night's Dream"
    assert title_of('unknownplay') == 'unknownplay'


# --- the page from fake data ----------------------------------------------------------------

def test_page_has_three_charts_and_the_right_number_of_bars():
    page = parse(render(PLAYS, TOP, GENRE))
    assert page.tags.count('svg') == 3
    # 2 play bars + 2 bars for each of the 3 genre words
    assert page.tags.count('path') == 2 + 2 * 3


def test_page_has_tooltips_tables_and_a_legend():
    page = parse(render(PLAYS, TOP, GENRE))
    assert page.tags.count('details') == 3 and page.tags.count('table') == 4
    assert any('Hamlet: 3,000 words, 900 different words (tragedies)' in t for t in page.titles)
    assert any('castle: 0.5 per 10,000 words in comedies (2 times); 4 in tragedies (12 times)' in t for t in page.titles)
    assert page.attrs.count(('class', 's1 key')) == 3 and page.attrs.count(('class', 's2 key')) == 3


def test_a_genre_keeps_its_colour_in_every_chart():
    import re
    html_text = render(PLAYS, TOP, GENRE)
    # comedies are slot 1 and tragedies slot 2, in the play chart and in the word charts alike
    first_bar = lambda title: re.search(r'<title>{}.*?<path class="(s\d)"'.format(title), html_text, re.S).group(1)
    assert first_bar('Twelfth Night') == 's1' and first_bar('Hamlet') == 's2'
    castle = re.search(r'<title>castle.*?</g>', html_text, re.S).group(0)
    assert re.findall(r'<path class="(s\d)"', castle) == ['s1', 's2']  # comedies bar first, tragedies second
    page = parse(html_text)
    assert page.attrs.count(('class', 's1')) == 1 + 3 and page.attrs.count(('class', 's2')) == 1 + 3


def test_longest_play_is_listed_first():
    text = ''.join(parse(render(PLAYS, TOP, GENRE)).text)
    assert text.index('Hamlet') < text.index('Twelfth Night')


def test_only_the_top_five_words_of_a_play_are_listed():
    text = ''.join(parse(render(PLAYS, TOP, GENRE)).text)
    assert 'ghost (40)' in text and 'sixth' not in text


def test_the_page_is_self_contained():
    page = render(PLAYS, TOP, GENRE)
    assert 'http://' not in page and 'https://' not in page and '<script' not in page
    assert 'prefers-color-scheme: dark' in page


def test_text_from_the_data_is_escaped():
    evil = [dict(PLAYS[0], play='<b>x</b>')] + PLAYS[1:]
    page = render(evil, TOP, GENRE)
    assert '<b>x</b>' not in page and '&lt;b&gt;x&lt;/b&gt;' in page


def test_the_report_needs_exactly_two_genres():
    with pytest.raises(ValueError, match='exactly 2 genres'):
        render(PLAYS[:1], TOP, GENRE)


def test_the_larger_bar_gets_the_value_label():
    page = render(PLAYS, TOP, [genre_row('niece', 'comedies', 4.0, 0.5), genre_row('castle', 'tragedies', 0.5, 4.5)])
    assert '>4.00</text>' in page and '>4.50</text>' in page and '>0.50</text>' not in page


def test_a_genre_with_no_words_gets_a_note_not_a_crash():
    page = parse(render(PLAYS, TOP, [genre_row('niece', 'comedies', 4.0, 0.5)]))
    assert page.tags.count('svg') == 2  # the play chart and the comedies chart only
    assert 'No word passed the filters' in ''.join(page.text)


# --- the command line, and the real report --------------------------------------------------

def test_report_cli_says_what_to_do_when_the_csv_files_are_missing(tmp_path):
    done = subprocess.run([sys.executable, str(ROOT / 'report.py'), '--output-dir', str(tmp_path)],
                          capture_output=True, text=True, cwd=ROOT)
    assert done.returncode == 1 and 'run compare.py first' in done.stderr
    assert not (tmp_path / 'report.html').exists()


def test_real_report_matches_the_csv_files(real_run):
    done = subprocess.run([sys.executable, str(ROOT / 'report.py'), '--output-dir', str(real_run)],
                          capture_output=True, text=True, cwd=ROOT)
    assert done.returncode == 0, done.stderr
    text = (real_run / 'report.html').read_text()
    plays = read_rows(real_run / 'play_stats.csv')
    total = sum(int(row['words']) for row in plays)
    assert '{:,} words in 8 plays'.format(total) in text
    page = parse(text)
    genre_rows = read_rows(real_run / 'genre_words.csv')
    assert page.tags.count('path') == 8 + 2 * len(genre_rows)
    assert 'castle' in text and 'bottom' in text and 'Hamlet' in text
