# Apache Beam Lab – Word Count on King Lear

[![Tests](https://github.com/1AlgoRythm/mlops-lab3/actions/workflows/tests.yml/badge.svg)](https://github.com/1AlgoRythm/mlops-lab3/actions/workflows/tests.yml)

An Apache Beam pipeline that counts the words in Shakespeare's *King Lear*. Beam is a library for
writing data pipelines. A pipeline runs on a "runner", the engine that executes it, and Beam has
several runners. This pipeline
reads the play, splits it into words, counts them, sorts them and writes the top words to a CSV
file. It runs as a normal Python program, and 19 tests check the code.

Based on `Labs/Data_Labs/Apache_Beam_Labs` from https://github.com/raminmohammadi/MLOps
(MLOps, DADS 7305, Northeastern University). The original notebook is kept here, unchanged, as
`Try_Apache_Beam_Python.ipynb`.

## Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Continuous Integration](#continuous-integration)
- [Testing](#testing)
- [Changes From the Upstream Lab](#changes-from-the-upstream-lab)
- [Known Limitations](#known-limitations)
- [Lessons Learned](#lessons-learned)

## Overview

The pipeline is a chain of steps. Beam calls the data that flows between steps a `PCollection`.
The steps run in this order:

1. `Read lines`: reads `data/kinglear.txt` (5,525 lines).
2. `Find words`: splits each line into lower-case words and counts lines and words as it goes.
3. `Drop stopwords`: removes the words in an optional stopword file.
4. `Pair words with 1`, then `Group and sum`: counts each word.
5. `Gather pairs`, then `Sort by count`: puts all pairs in one list, sorted by count.
6. `Make CSV body`, then `Write results`: writes `outputs/word_counts.csv`.

On the whole play there are 27,986 words and 4,176 different words. The most common are `the`
(910), `and` (738) and `i` (652).

## Requirements

- Python 3.12 or 3.13. Apache Beam 2.77 lists Python 3.10 to 3.14.
- The packages in `requirements.txt`: `apache-beam` and `pytest`.
- Tested with Python 3.12.15 and 3.13.16, Apache Beam 2.77.0 and pytest 9.2.0.

## Installation

```bash
git clone https://github.com/1AlgoRythm/mlops-lab3.git
cd mlops-lab3
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Count the words and write the top 20:

```bash
python wordcount.py
head -5 outputs/word_counts.csv
```

Options:

| Option | Default | What it does |
|---|---|---|
| `--input` | `data/*` | The file or file pattern to read |
| `--output` | `outputs/word_counts` | The output file name; `.csv` is added |
| `--top-n` | `20` | Keep the N most common words. `0` keeps all of them |
| `--stopwords` | none | A file of words to ignore, one per line |

For example, the eight most common words without the very common ones:

```bash
python wordcount.py --top-n 8 --stopwords stopwords.txt
```

This gives `king` (311), `lear` (253), `thou` (220), `kent` (175), `gloucester` (167), `thy` (161),
`no` (154) and `so` (141). The program also prints the three counters of the run, for example
`wordcount: lines 5525, lines_without_words 1665, words 27986`.

If the input is missing or empty, the program stops with a message and exits with code 1. It
writes no output file.

## Project Structure

```
.
├── wordcount.py                  the pipeline and its command line
├── stopwords.txt                 a short list of very common words
├── data/kinglear.txt             the input text (from the original lab)
├── outputs/part-00000-of-00001   the original lab's output file (unchanged)
├── Try_Apache_Beam_Python.ipynb  the original lab notebook (unchanged)
├── tests/test_wordcount.py       19 tests
├── requirements.txt
├── pytest.ini
└── .github/workflows/tests.yml   runs the tests on GitHub
```

## API Reference

Everything is in `wordcount.py`.

| Name | What it does |
|---|---|
| `find_words(line)` | Returns the lower-case words of one line |
| `FindWords` | The Beam step that uses `find_words` and keeps three counters |
| `rank(word_counts, top_n=0)` | Sorts `(word, count)` pairs, highest count first, then by word |
| `to_csv(ranked)` | Makes the CSV lines, `word,count` |
| `check_input(pattern)` | Raises `ValueError` if no file matches or every file is empty |
| `load_stopwords(path)` | Reads a stopword file into a set |
| `build_pipeline(...)` | Adds all the steps to a Beam pipeline |

A word is letters, with single apostrophes allowed inside it:

```python
>>> from wordcount import find_words, rank, to_csv
>>> find_words("The KING doesn't say 'tis so")
['the', 'king', "doesn't", 'say', 'tis', 'so']
>>> rank([('b', 2), ('a', 2), ('c', 5)])
[('c', 5), ('a', 2), ('b', 2)]
>>> rank([('b', 2), ('a', 2), ('c', 5)], 2)
[('c', 5), ('a', 2)]
>>> to_csv([('the', 9), ('of', 4)])
'the,9\nof,4'

```

## Continuous Integration

### How it works

1. A push to `main`, or a pull request, triggers the workflow.
2. GitHub starts a fresh Ubuntu machine for each Python version in the matrix.
3. The machine checks out the code and installs the requested Python version.
4. It installs the packages in `requirements.txt`.
5. It runs the tests and writes an XML report.
6. GitHub shows a green check if every step passed and a red cross if any step failed.

### Workflows

| Workflow | File | Runs on | Command | Artifacts |
|---|---|---|---|---|
| Tests | `tests.yml` | push to `main`; pull requests | `pytest --junitxml=pytest-report.xml` | `test-results-3.12`, `test-results-3.13` |

The job is written once, and GitHub runs it once per version in `strategy.matrix.python-version`:
**3.12** and **3.13**. Versions are written in quotes, and `fail-fast: false` lets one version
fail without cancelling the other.

## Testing

```bash
pip install -r requirements.txt
pytest
```

The 19 tests take about 10 seconds. They cover four things:

- **The small functions:** `find_words`, `rank`, `to_csv`, `load_stopwords` and `check_input`.
- **The Beam steps:** two tests run a tiny pipeline with Beam's own test helpers
  (`TestPipeline`, `assert_that`, `equal_to`).
- **Full runs through the command line:** a small text file, a stopword file and a bad input.
- **The real data:** one test checks the numbers written in this README (4,176 words, 27,986
  counted, `the` first with 910).

The tests passed on Python 3.12.15 and on 3.13.16. Eight deliberate breaks of `wordcount.py`
(no lowercasing, edge apostrophes back, no tie-break, wrong sort order, an off-by-one top-N,
a wrong word counter, stopwords ignored, no empty-file check) were each caught by a test.

## Changes From the Upstream Lab

Each change is its own commit.

### Fixed

- **Upper and lower case were different words.** The lab counted `the` 786 times and `The` 122
  times. Words are now lower-cased, so `the` is 908 before the next fix. The 4,784 different
  "words" became 4,215.
- **A quote mark was counted as a word.** The lab counted a lone `'` 15 times, and counted
  `'tis` and `tis` apart. A word is now letters with apostrophes only inside it. The count of
  different words is 4,176.
- **The output was Python's text form of a tuple,** such as `('KING', 243)`, in no order. It is
  now a CSV file with a header, sorted by count and then by word.
- **The pipeline could only run in a notebook.** Its last line needed a helper that uses `!`
  shell commands. The pipeline now lives in `wordcount.py` and runs from the command line.
  (A comment in the notebook says "first 20 results", and the command prints 200. The notebook
  is left unchanged, and the new command has a `--top-n` option instead.)

### Added

- **Options:** `--top-n` and an optional stopword file.
- **An input check** that stops with a clear message.
- **Three counters** with Beam's metrics: lines, lines without words, and words. They matched
  independent counts of the file: 5,525 lines, 1,665 lines with no letter, and 27,986 words
  (the sum of all the counts).
- **19 tests** and a `requirements.txt`.
- **A GitHub Actions workflow** that runs the tests on Python 3.12 and 3.13.

### Changed

- Nothing in the three original files. The notebook, the data file and the original output file
  are byte-identical to the course repository.

## Known Limitations

- **All the pairs are gathered on one worker to sort them.** Beam does not promise any order,
  so the pipeline puts every word in one list. This is fine for one play and would not scale to
  a large text.
- **Only the letters `a` to `z` count as letters.** An accented letter splits a word, so `café`
  becomes `caf`. The *King Lear* file has no such letters, so it does not change these results.
- **The stopword list is short and chosen for this lab.** It is not a standard list. Words like
  `thou` and `thy` stay in the results.
- **The packages are not pinned.** The tested versions were Apache Beam 2.77.0 and pytest 9.2.0.
- **The runner is Beam's default.** In Beam 2.77 it is `SwitchingDirectRunner`, and the log of
  this pipeline shows `PrismRunner`. Another Beam version may choose differently.
- **GitHub Actions had not run on this code at the time of writing.** The workflow's commands
  were run locally and passed.

## Lessons Learned

- Beam is a chain of steps on a `PCollection`, written as `pipeline | 'name' >> step`. Each step
  gets a name.
- Beam gives no promise about order. The lab's own output was in no order, and a sort needs all
  the pairs in one place. Gathering them into one list and sorting it did that, at the cost of
  one worker.
- Counters live inside the steps and are read from the result after the run. They matched
  independent counts of the file, which showed that the word-splitting step saw every line.
- The default local runner is not the one the notebook names. The notebook says
  `DirectRunner`. Beam 2.77's default is `SwitchingDirectRunner`, and the log of this pipeline
  showed Prism running it.
- A pipeline that ran is not a pipeline that is right. The lab ran fine and still counted
  `The` and `the` apart and counted a quote mark 15 times. Check the output, not only the exit
  code.
- A small pipeline can be tested like any function. `TestPipeline` and `assert_that` check a
  step on a few lines, and the whole test run takes about 10 seconds.
