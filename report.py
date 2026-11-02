"""Turn the three CSV files of compare.py into one self-contained HTML report (a small dashboard).

Standard library only. The charts are inline SVG, so the file needs no network and no JavaScript.
"""
import argparse
import csv
import html
import math
import os
import sys

WIDTH, LEFT, RIGHT = 720, 204, 60
PLOT = WIDTH - LEFT - RIGHT

STYLE = """
:root {
  color-scheme: light dark;
  --surface: #fcfcfb; --text: #0b0b0b; --text-2: #52514e; --grid: #e6e5e1;
  --series-1: #2a78d6; --series-2: #eb6834;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface: #1a1a19; --text: #f0efec; --text-2: #c3c2b7; --grid: #2f2f2d;
    --series-1: #3987e5; --series-2: #d95926;
  }
}
html, body { margin: 0; background: var(--surface); }
.viz-root { max-width: 760px; margin: 0 auto; padding: 24px 20px 48px; color: var(--text);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
h1 { font-size: 26px; margin: 0 0 4px; } h2 { font-size: 18px; margin: 36px 0 4px; }
p { margin: 4px 0 10px; } .sub { color: var(--text-2); }
.legend { display: flex; gap: 18px; margin: 8px 0 4px; color: var(--text-2); font-size: 13px; }
.legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; margin-right: 6px;
  border-radius: 2px; background: var(--c); }
svg { width: 100%; height: auto; display: block; }
svg text { font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; fill: var(--text-2); }
svg text.value { fill: var(--text); } svg text.word { fill: var(--text); font-size: 13px; }
svg .grid { stroke: var(--grid); stroke-width: 1; }
.s1 { fill: var(--series-1); } .s2 { fill: var(--series-2); }
.s1.key { --c: var(--series-1); } .s2.key { --c: var(--series-2); }
table { border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 8px; }
th, td { text-align: left; padding: 4px 10px 4px 0; border-bottom: 1px solid var(--grid); }
th { color: var(--text-2); font-weight: 600; } td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
details { margin-top: 6px; } summary { cursor: pointer; color: var(--text-2); font-size: 13px; }
.note { color: var(--text-2); font-size: 13px; }
"""


TITLES = {
    'asyoulikeit': 'As You Like It', 'hamlet': 'Hamlet', 'kinglear': 'King Lear', 'macbeth': 'Macbeth',
    'midsummersnightsdream': "A Midsummer Night's Dream", 'muchadoaboutnothing': 'Much Ado About Nothing',
    'othello': 'Othello', 'twelfthnight': 'Twelfth Night',
}


def title_of(play):
    """The play's title, or the file name if the play is not one of the eight known ones."""
    return TITLES.get(play, play)


def read_rows(path):
    with open(path, newline='') as handle:
        return list(csv.DictReader(handle))


def nice_ticks(maximum):
    """Return (axis maximum, tick values): a clean step of 1, 2 or 5 times a power of ten, 5 ticks at most."""
    step = 10 ** math.floor(math.log10(maximum / 4))
    for factor in (1, 2, 5, 10):
        if maximum / (step * factor) <= 5:
            step *= factor
            break
    top = math.ceil(maximum / step) * step
    return top, [i * step for i in range(int(round(top / step)) + 1)]


def tick_label(value):
    return '{:g}'.format(value) if value < 1000 else '{:.0f}K'.format(value / 1000)


def bar_path(x, y, width, height, radius=4):
    """A bar that is square at its baseline (left) and rounded at its data end (right)."""
    radius = min(radius, width / 2, height / 2)
    return ('M{x:.1f},{y:.1f} H{xr:.1f} A{r:.1f},{r:.1f} 0 0 1 {x2:.1f},{yr:.1f} V{yb:.1f} '
            'A{r:.1f},{r:.1f} 0 0 1 {xr:.1f},{y2:.1f} H{x:.1f} Z').format(
        x=x, y=y, xr=x + width - radius, r=radius, x2=x + width, yr=y + radius, yb=y + height - radius,
        y2=y + height)


def axis(top, ticks, plot_height, label):
    """Hairline vertical gridlines with tick labels below, and an axis title."""
    parts = []
    for tick in ticks:
        x = LEFT + tick / top * PLOT
        parts.append('<line class="grid" x1="{0:.1f}" x2="{0:.1f}" y1="0" y2="{1}"/>'.format(x, plot_height))
        parts.append('<text x="{0:.1f}" y="{1}" text-anchor="middle">{2}</text>'.format(
            x, plot_height + 16, tick_label(tick)))
    parts.append('<text x="{0}" y="{1}" text-anchor="end">{2}</text>'.format(
        LEFT + PLOT, plot_height + 34, html.escape(label)))
    return ''.join(parts)


def svg(height, body, label):
    return '<svg viewBox="0 0 {} {}" role="img" aria-label="{}">{}</svg>'.format(
        WIDTH, height, html.escape(label), body)


def legend(genres):
    return '<div class="legend">{}</div>'.format(''.join(
        '<span class="s{} key">{}</span>'.format(i + 1, html.escape(genre)) for i, genre in enumerate(genres)))


def play_chart(plays, genres):
    """One bar per play: its number of words, coloured by genre."""
    ordered = sorted(plays, key=lambda row: -int(row['words']))
    pitch, bar = 30, 18
    top, ticks = nice_ticks(max(int(row['words']) for row in ordered))
    height = pitch * len(ordered)
    parts = [axis(top, ticks, height, 'words in the play')]
    for i, row in enumerate(ordered):
        y = i * pitch + (pitch - bar) / 2
        words = int(row['words'])
        series = genres.index(row['genre']) + 1
        parts.append('<g><title>{}: {:,} words, {:,} different words ({})</title>'.format(
            html.escape(title_of(row['play'])), words, int(row['distinct_words']), html.escape(row['genre'])))
        parts.append('<text class="word" x="{}" y="{:.1f}" text-anchor="end">{}</text>'.format(
            LEFT - 8, y + bar / 2 + 4, html.escape(title_of(row['play']))))
        width = words / top * PLOT
        parts.append('<path class="s{}" d="{}"/>'.format(series, bar_path(LEFT, y, width, bar)))
        parts.append('<text class="value" x="{:.1f}" y="{:.1f}">{:,}</text></g>'.format(
            LEFT + width + 6, y + bar / 2 + 4, words))
    return svg(height + 44, ''.join(parts), 'Words per play, one bar per play, coloured by genre')


def genre_chart(rows, genres, label):
    """Per word, two thin bars (one per genre): how often each genre says it per 10,000 words."""
    first, second = genres
    bar, gap, pitch = 9, 2, 30
    top, ticks = nice_ticks(max(max(float(r[first + '_per_10k']), float(r[second + '_per_10k'])) for r in rows))
    height = pitch * len(rows)
    parts = [axis(top, ticks, height, 'times per 10,000 words')]
    for i, row in enumerate(rows):
        y0 = i * pitch + (pitch - (2 * bar + gap)) / 2
        rates = [float(row[first + '_per_10k']), float(row[second + '_per_10k'])]
        counts = [int(row[first + '_count']), int(row[second + '_count'])]
        parts.append('<g><title>{}: {:g} per 10,000 words in {} ({} times); {:g} in {} ({} times)</title>'.format(
            html.escape(row['word']), rates[0], html.escape(first), counts[0], rates[1], html.escape(second),
            counts[1]))
        parts.append('<text class="word" x="{}" y="{:.1f}" text-anchor="end">{}</text>'.format(
            LEFT - 8, y0 + bar + 2, html.escape(row['word'])))
        for k, rate in enumerate(rates):
            y = y0 + k * (bar + gap)
            width = max(rate / top * PLOT, 1.5)
            parts.append('<path class="s{}" d="{}"/>'.format(k + 1, bar_path(LEFT, y, width, bar, 3)))
        larger = 0 if rates[0] >= rates[1] else 1  # label only the favoured side, so the chart stays calm
        parts.append('<text class="value" x="{:.1f}" y="{:.1f}">{:.2f}</text></g>'.format(
            LEFT + max(rates[larger] / top * PLOT, 1.5) + 6, y0 + larger * (bar + gap) + bar - 1, rates[larger]))
    return svg(height + 44, ''.join(parts), label)


def table(headers, rows, numeric=()):
    head = ''.join('<th{}>{}</th>'.format(' class="num"' if i in numeric else '', html.escape(h))
                   for i, h in enumerate(headers))
    body = ''.join('<tr>{}</tr>'.format(''.join(
        '<td{}>{}</td>'.format(' class="num"' if i in numeric else '', html.escape(str(cell)))
        for i, cell in enumerate(row))) for row in rows)
    return '<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>'.format(head, body)


def render(play_stats, top_words, genre_words):
    genres = sorted({row['genre'] for row in play_stats})
    if len(genres) != 2:
        raise ValueError('the report needs exactly 2 genres, found {}'.format(genres))
    first, second = genres
    total_words = sum(int(row['words']) for row in play_stats)

    plays_table = table(
        ['play', 'genre', 'words', 'different words', 'different words per word said'],
        [(title_of(r['play']), r['genre'], '{:,}'.format(int(r['words'])), '{:,}'.format(int(r['distinct_words'])),
          r['distinct_per_word']) for r in sorted(play_stats, key=lambda r: -int(r['words']))],
        numeric=(2, 3, 4))

    def genre_section(favoured, title, intro):
        rows = [r for r in genre_words if r['favours'] == favoured]
        if not rows:
            return '<h2>{}</h2><p class="sub">No word passed the filters described below.</p>'.format(
                html.escape(title))
        words_table = table(
            ['word', first + ' times', second + ' times', first + ' per 10,000', second + ' per 10,000',
             'plays that use it'],
            [(r['word'], r[first + '_count'], r[second + '_count'], r[first + '_per_10k'],
              r[second + '_per_10k'], r['plays']) for r in rows], numeric=(1, 2, 3, 4, 5))
        chart = genre_chart(rows, genres, '{}: bars show how often {} and {} say each word'.format(
            title, first, second))
        return '<h2>{}</h2><p class="sub">{}</p>{}{}<details><summary>Table view</summary>{}</details>'.format(
            html.escape(title), intro, legend(genres), chart, words_table)

    top_rows = []
    for play in sorted({(r['genre'], r['play']) for r in top_words}):
        words = [r for r in top_words if (r['genre'], r['play']) == play and int(r['rank']) <= 5]
        top_rows.append((title_of(play[1]), play[0], ', '.join('{} ({})'.format(w['word'], w['count']) for w in words)))

    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Word use in {n} Shakespeare plays</title><style>{style}</style></head>
<body><main class="viz-root">
<h1>Word use in {n} Shakespeare plays</h1>
<p class="sub">{words:,} words in {n} plays, counted by an Apache Beam pipeline: {a} versus {b}.</p>

<h2>How long is each play?</h2>
<p class="sub">Bars show the number of words. Colour shows the genre.</p>
{legend}{play_chart}
<details><summary>Table view</summary>{plays_table}</details>

{tragic}
{comic}

<h2>The top words in each play</h2>
<p class="sub">The five most common words, without the very common ones listed in <code>stopwords.txt</code>.</p>
{top_table}

<h2>How to read this</h2>
<p class="note">A rate is how many times a word appears in every 10,000 words of a genre. A word is shown only
if it appears in at least 3 plays and at least 30 times, so a name from one play cannot win. Words are ranked
by the ratio of the two rates, with 0.5 added to each count so a word that one genre never says does not divide
by zero. The grouping of plays into genres is a choice made for this lab. Character names can still pass the
filter when the same word is also used elsewhere: <em>bottom</em> is a character in one comedy and a plain word
in three other plays.</p>
</main></body></html>
'''.format(
        n=len(play_stats), style=STYLE, words=total_words, a=html.escape(first), b=html.escape(second),
        legend=legend(genres), play_chart=play_chart(play_stats, genres), plays_table=plays_table,
        tragic=genre_section(second, 'Words ' + second + ' use more', 'Each word is more common in ' + second + '.'),
        comic=genre_section(first, 'Words ' + first + ' use more', 'Each word is more common in ' + first + '.'),
        top_table=table(['play', 'genre', 'top words'], top_rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='outputs', help='folder that holds the CSV files of compare.py')
    args = parser.parse_args()
    try:
        files = [read_rows(os.path.join(args.output_dir, name + '.csv'))
                 for name in ('play_stats', 'play_top_words', 'genre_words')]
        page = render(*files)
    except (OSError, ValueError, KeyError) as error:
        sys.exit('report: {} (run compare.py first)'.format(error))
    path = os.path.join(args.output_dir, 'report.html')
    with open(path, 'w') as handle:
        handle.write(page)
    print('report: wrote {}'.format(path))


if __name__ == '__main__':
    main()
