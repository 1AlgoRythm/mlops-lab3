"""Word count with Apache Beam, moved out of the course notebook so it can run as a program."""
import argparse
import re

import apache_beam as beam


def find_words(line):
    """Return every word in one line of text, in lower case.

    A word is letters, with single apostrophes allowed inside it: don't stays one word,
    'tis counts as tis, and a lone quote mark is not a word.
    """
    return re.findall(r"[a-z]+(?:'[a-z]+)*", line.lower())


def build_pipeline(pipeline, inputs_pattern, outputs_prefix):
    """Attach the word-count steps to a pipeline. Element types are noted after each step."""
    word_counts = (
        pipeline
        | 'Read lines' >> beam.io.ReadFromText(inputs_pattern)  # str, one line
        | 'Find words' >> beam.FlatMap(find_words)  # str, one word
        | 'Pair words with 1' >> beam.Map(lambda word: (word, 1))  # (str, int)
        | 'Group and sum' >> beam.CombinePerKey(sum)  # (str, int): word, count
    )
    (
        word_counts
        | 'Format results' >> beam.Map(str)  # str, the text form of the tuple
        | 'Write results' >> beam.io.WriteToText(outputs_prefix)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='data/*', help='file or glob to read')
    parser.add_argument('--output', default='outputs/part', help='output file prefix')
    args = parser.parse_args()
    with beam.Pipeline() as pipeline:
        build_pipeline(pipeline, args.input, args.output)


if __name__ == '__main__':
    main()
