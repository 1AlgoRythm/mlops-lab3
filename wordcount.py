"""Word count with Apache Beam, moved out of the course notebook so it can run as a program."""
import argparse
import glob
import os
import re
import sys

import apache_beam as beam


def find_words(line):
    """Return every word in one line of text, in lower case.

    A word is letters, with single apostrophes allowed inside it: don't stays one word,
    'tis counts as tis, and a lone quote mark is not a word.
    """
    return re.findall(r"[a-z]+(?:'[a-z]+)*", line.lower())


def load_stopwords(path):
    """Read a stopword file: one word per line, blank lines ignored, case ignored."""
    with open(path) as handle:
        return {line.strip().lower() for line in handle if line.strip()}


def check_input(inputs_pattern):
    """Stop early, with a clear message, if the pattern matches no file or only empty files."""
    paths = glob.glob(inputs_pattern)
    if not paths:
        raise ValueError("no file matches '{}'".format(inputs_pattern))
    if all(os.path.getsize(path) == 0 for path in paths):
        raise ValueError("every file matching '{}' is empty".format(inputs_pattern))


def rank(word_counts, top_n=0):
    """Sort (word, count) pairs by count, highest first, then by word. top_n 0 keeps them all."""
    ranked = sorted(word_counts, key=lambda pair: (-pair[1], pair[0]))
    return ranked[:top_n] if top_n else ranked


def to_csv(ranked):
    """Make the CSV body, one 'word,count' line per pair. Words hold only letters and apostrophes."""
    return '\n'.join('{},{}'.format(word, count) for word, count in ranked)


def build_pipeline(pipeline, inputs_pattern, outputs_prefix, top_n=0, stopwords=frozenset()):
    """Attach the word-count steps to a pipeline. Element types are noted after each step."""
    word_counts = (
        pipeline
        | 'Read lines' >> beam.io.ReadFromText(inputs_pattern)  # str, one line
        | 'Find words' >> beam.FlatMap(find_words)  # str, one word
        | 'Drop stopwords' >> beam.Filter(lambda word: word not in stopwords)  # str, one word
        | 'Pair words with 1' >> beam.Map(lambda word: (word, 1))  # (str, int)
        | 'Group and sum' >> beam.CombinePerKey(sum)  # (str, int): word, count
    )
    (
        word_counts
        # Beam gives no order guarantee, so gather the pairs into one list and sort that list.
        # This puts every word on one worker, which is fine for one play and not for a large corpus.
        | 'Gather pairs' >> beam.combiners.ToList()  # one list of (str, int)
        | 'Sort by count' >> beam.Map(rank, top_n)  # one sorted list, cut to top_n
        # One element, so the lines cannot be reordered on the way to the file.
        | 'Make CSV body' >> beam.Map(to_csv)  # one str
        | 'Write results' >> beam.io.WriteToText(
            outputs_prefix, file_name_suffix='.csv', shard_name_template='', header='word,count')
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='data/*', help='file or glob to read')
    parser.add_argument('--output', default='outputs/word_counts', help='output file prefix; .csv is added')
    parser.add_argument('--top-n', type=int, default=20, help='keep the N most common words; 0 keeps all')
    parser.add_argument('--stopwords', help='file of words to ignore, one per line')
    args = parser.parse_args()
    try:
        if args.top_n < 0:
            raise ValueError('--top-n must be 0 or more')
        check_input(args.input)
        stopwords = load_stopwords(args.stopwords) if args.stopwords else frozenset()
    except (ValueError, OSError) as error:
        sys.exit('wordcount: {}'.format(error))
    with beam.Pipeline() as pipeline:
        build_pipeline(pipeline, args.input, args.output, args.top_n, stopwords)


if __name__ == '__main__':
    main()
