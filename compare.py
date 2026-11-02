"""Compare word use across plays and between two genres, with Apache Beam.

A second pipeline next to wordcount.py. It reads every play under plays/<genre>/<play>.txt and writes
three CSV files: statistics per play, the top words per play, and the words that one genre uses much
more than the other.
"""
import argparse
import glob
import os
import sys

import apache_beam as beam

from wordcount import check_input, find_words, load_stopwords, rank


def play_key(path):
    """Return (genre, play) from a path such as plays/tragedies/hamlet.txt."""
    return os.path.basename(os.path.dirname(path)), os.path.splitext(os.path.basename(path))[0]


def find_genres(inputs_pattern):
    """Return the sorted genre folder names that the pattern matches. A comparison needs exactly two."""
    genres = sorted({play_key(path)[0] for path in glob.glob(inputs_pattern)})
    if len(genres) != 2:
        raise ValueError("need files in exactly 2 genre folders, found {}: {}".format(len(genres), genres))
    return tuple(genres)


def words_of(path_and_line):
    """Turn one (path, line) element into one (genre, play, word) element per word."""
    path, line = path_and_line
    genre, play = play_key(path)
    for word in find_words(line):
        yield genre, play, word


class PlayStats(beam.CombineFn):
    """Fold the per-word counts of one play into (words, distinct words)."""

    def create_accumulator(self):
        return 0, 0

    def add_input(self, accumulator, count):
        return accumulator[0] + count, accumulator[1] + 1

    def merge_accumulators(self, accumulators):
        words = distinct = 0
        for part_words, part_distinct in accumulators:
            words += part_words
            distinct += part_distinct
        return words, distinct

    def extract_output(self, accumulator):
        return accumulator


def play_stat_row(key, stats):
    """One CSV row per play: genre, play, words, distinct words, distinct words per word said."""
    (genre, play), (words, distinct) = key, stats
    return genre, play, words, distinct, round(distinct / words, 4)


def add_pairs(pairs):
    """Add up (count, plays) pairs."""
    pairs = list(pairs)
    return sum(count for count, _ in pairs), sum(plays for _, plays in pairs)


def genre_rows(word, entries, totals, genres, min_plays, min_count):
    """Return a list with one row for this word, or an empty list if it is too rare to trust or one letter long.

    entries: (genre, count, plays) for each genre that uses the word. totals: {genre: words in genre}.
    The rate is per 10,000 words, with 0.5 added to each count so a missing word does not divide by zero.
    """
    if len(word) == 1:  # a one-letter token such as t, from the elision 't, is not a word to compare
        return []
    first, second = genres
    seen = {genre: (count, plays) for genre, count, plays in entries}
    count_a, plays_a = seen.get(first, (0, 0))
    count_b, plays_b = seen.get(second, (0, 0))
    if plays_a + plays_b < min_plays or count_a + count_b < min_count:
        return []
    rate_a = (count_a + 0.5) / totals[first] * 10000
    rate_b = (count_b + 0.5) / totals[second] * 10000
    ratio = rate_b / rate_a
    favours = second if ratio > 1 else first
    return [(word, favours, count_a, count_b, round(rate_a, 2), round(rate_b, 2), round(ratio, 3),
             plays_a + plays_b)]


def score_word(word_and_entries, totals, genres, min_plays, min_count):
    """Unpack one (word, entries) element for genre_rows. A side input needs a plain FlatMap."""
    word, entries = word_and_entries
    return genre_rows(word, entries, totals, genres, min_plays, min_count)


def pick_extremes(rows, top_n):
    """Keep the top_n words that favour the second genre (highest ratio) and the top_n that favour the first."""
    by_ratio = sorted(rows, key=lambda row: (-row[6], row[0]))
    favour_second = [row for row in by_ratio if row[6] > 1][:top_n]
    favour_first = sorted((row for row in rows if row[6] <= 1), key=lambda row: (row[6], row[0]))[:top_n]
    return favour_second + favour_first


def rows_to_csv(rows):
    """Make the CSV body, one line per row."""
    return '\n'.join(','.join(str(value) for value in row) for row in rows)


class WriteCsv(beam.PTransform):
    """Gather rows into one list, arrange it (sort or cut), and write one CSV file with a header."""

    def __init__(self, prefix, header, arrange):
        super().__init__()
        self.prefix, self.header, self.arrange = prefix, header, arrange

    def expand(self, rows):
        return (
            rows
            | 'Gather rows' >> beam.combiners.ToList()  # one list of tuples
            | 'Arrange rows' >> beam.Map(self.arrange)  # one arranged list
            | 'Make CSV body' >> beam.Map(rows_to_csv)  # one str, so the lines keep their order
            | 'Write file' >> beam.io.WriteToText(
                self.prefix, file_name_suffix='.csv', shard_name_template='', header=self.header)
        )


def build_pipeline(pipeline, inputs_pattern, output_dir, genres, stopwords=frozenset(),
                   top_n=10, genre_top_n=15, min_plays=3, min_count=30):
    """Attach all the comparison steps to a pipeline."""
    first, second = genres
    counts = (
        pipeline
        | 'Read lines' >> beam.io.textio.ReadFromTextWithFilename(inputs_pattern)  # (path, line)
        | 'Find words' >> beam.FlatMap(words_of)  # (genre, play, word)
        | 'Count per play' >> beam.combiners.Count.PerElement()  # ((genre, play, word), count)
    )

    # 1. Statistics per play: a custom combiner folds each play's word counts into two numbers.
    (
        counts
        | 'Key by play' >> beam.MapTuple(lambda key, count: ((key[0], key[1]), count))
        | 'Play stats' >> beam.CombinePerKey(PlayStats())  # ((genre, play), (words, distinct))
        | 'Play stat rows' >> beam.MapTuple(play_stat_row)
        | 'Write play stats' >> WriteCsv(
            os.path.join(output_dir, 'play_stats'), 'genre,play,words,distinct_words,distinct_per_word',
            lambda rows: sorted(rows))
    )

    # 2. The top words of each play, without stopwords.
    (
        counts
        | 'Keep real words' >> beam.Filter(lambda element: element[0][2] not in stopwords)
        | 'Key by play, value word' >> beam.MapTuple(lambda key, count: ((key[0], key[1]), (key[2], count)))
        | 'Group words per play' >> beam.GroupByKey()
        | 'Rank per play' >> beam.FlatMapTuple(
            lambda key, pairs: [(key[0], key[1], place, word, count)
                                for place, (word, count) in enumerate(rank(pairs, top_n), 1)])
        | 'Write top words' >> WriteCsv(
            os.path.join(output_dir, 'play_top_words'), 'genre,play,rank,word,count',
            lambda rows: sorted(rows))
    )

    # 3. Words that one genre uses much more than the other. The genre totals reach every word
    #    through a side input.
    genre_word = (
        counts
        | 'Key by genre and word' >> beam.MapTuple(lambda key, count: ((key[0], key[2]), (count, 1)))
        | 'Add counts and plays' >> beam.CombinePerKey(add_pairs)  # ((genre, word), (count, plays))
    )
    totals = (
        genre_word
        | 'Key by genre' >> beam.MapTuple(lambda key, pair: (key[0], pair[0]))
        | 'Genre totals' >> beam.CombinePerKey(sum)  # (genre, words in genre)
    )
    (
        genre_word
        | 'Key by word' >> beam.MapTuple(lambda key, pair: (key[1], (key[0], pair[0], pair[1])))
        | 'Group genres per word' >> beam.GroupByKey()
        | 'Score words' >> beam.FlatMap(
            score_word, beam.pvalue.AsDict(totals), genres, min_plays, min_count)
        | 'Write genre words' >> WriteCsv(
            os.path.join(output_dir, 'genre_words'),
            'word,favours,{0}_count,{1}_count,{0}_per_10k,{1}_per_10k,ratio_{1}_over_{0},plays'.format(
                first, second),
            lambda rows: pick_extremes(rows, genre_top_n))
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='plays/*/*.txt', help='pattern for plays/<genre>/<play>.txt')
    parser.add_argument('--output-dir', default='outputs', help='folder for the three CSV files')
    parser.add_argument('--top-n', type=int, default=10, help='top words kept per play')
    parser.add_argument('--genre-top-n', type=int, default=15, help='words kept for each genre')
    parser.add_argument('--min-plays', type=int, default=3, help='a word must appear in this many plays')
    parser.add_argument('--min-count', type=int, default=30, help='a word must be said this many times')
    parser.add_argument('--stopwords', default='stopwords.txt', help='stopwords for the per-play top words')
    args = parser.parse_args()
    try:
        if min(args.top_n, args.genre_top_n, args.min_plays, args.min_count) < 1:
            raise ValueError('--top-n, --genre-top-n, --min-plays and --min-count must be 1 or more')
        check_input(args.input)
        genres = find_genres(args.input)
        stopwords = load_stopwords(args.stopwords)
        os.makedirs(args.output_dir, exist_ok=True)
    except (ValueError, OSError) as error:
        sys.exit('compare: {}'.format(error))
    with beam.Pipeline() as pipeline:
        build_pipeline(pipeline, args.input, args.output_dir, genres, stopwords,
                       args.top_n, args.genre_top_n, args.min_plays, args.min_count)
    print('compare: wrote play_stats.csv, play_top_words.csv and genre_words.csv to {}'.format(args.output_dir))


if __name__ == '__main__':
    main()
