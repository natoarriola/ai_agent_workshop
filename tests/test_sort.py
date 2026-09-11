"""Unit tests for BED parsing and the sort ordering. No bedtools, no fixtures.

Expected values were checked against real bedtools first; the surprising ones
carry the invocation that proves them.
"""

import io
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "mytools"
_spec = spec_from_loader("mytools", SourceFileLoader("mytools", str(_PATH)))
mytools = module_from_spec(_spec)
_spec.loader.exec_module(mytools)

BedError = mytools.BedError
read_bed = mytools.read_bed


def parse(text):
    return list(read_bed(io.StringIO(text), "test"))


def sort_key(record):
    return (record.chrom, record.start, record.end)


class TestParsing(unittest.TestCase):
    def test_bed3(self):
        (rec,) = parse("chr1\t100\t200\n")
        self.assertEqual((rec.chrom, rec.start, rec.end), ("chr1", 100, 200))

    def test_bed6(self):
        (rec,) = parse("chr1\t100\t200\tname\t5\t+\n")
        self.assertEqual(rec.line, "chr1\t100\t200\tname\t5\t+")

    def test_line_is_carried_through_verbatim(self):
        # Columns beyond the first three are never parsed, only preserved --
        # a score of "1e3" or a strand of "." must survive untouched.
        text = "chr1\t100\t200\tn\t1e3\t.\n"
        (rec,) = parse(text)
        self.assertEqual(rec.line + "\n", text)

    def test_missing_trailing_newline(self):
        (rec,) = parse("chr1\t100\t200")
        self.assertEqual(rec.end, 200)

    def test_zero_length_is_legal(self):
        (rec,) = parse("chr1\t500\t500\n")
        self.assertEqual(rec.start, rec.end)

    def test_position_zero_is_legal(self):
        (rec,) = parse("chr1\t0\t0\n")
        self.assertEqual((rec.start, rec.end), (0, 0))


class TestSkippedLines(unittest.TestCase):
    """bedtools drops these silently and exits 0 -- confirmed on a fixture."""

    def test_comment(self):
        self.assertEqual(parse("# comment\nchr1\t1\t2\n"), parse("chr1\t1\t2\n"))

    def test_track_line(self):
        self.assertEqual(parse("track name=x\nchr1\t1\t2\n"), parse("chr1\t1\t2\n"))

    def test_browser_line(self):
        self.assertEqual(
            parse("browser position chr1\nchr1\t1\t2\n"), parse("chr1\t1\t2\n")
        )

    def test_blank_and_whitespace_only_lines(self):
        self.assertEqual(parse("\nchr1\t1\t2\n   \n"), parse("chr1\t1\t2\n"))

    def test_a_file_of_only_headers_yields_nothing(self):
        self.assertEqual(parse("# one\ntrack x\n\n"), [])


class TestBadInput(unittest.TestCase):
    """Everything here is exit 1: bad data, not bad usage."""

    def test_fewer_than_three_columns(self):
        with self.assertRaises(BedError):
            parse("chr1\t100\n")

    def test_space_delimited_is_not_tab_delimited(self):
        with self.assertRaises(BedError):
            parse("chr1 100 200\n")

    def test_non_integer_start(self):
        with self.assertRaises(BedError):
            parse("chr1\tfoo\t200\n")

    def test_non_integer_end(self):
        with self.assertRaises(BedError):
            parse("chr1\t100\tbar\n")

    def test_start_greater_than_end(self):
        with self.assertRaises(BedError) as caught:
            parse("chr1\t500\t400\n")
        self.assertIn("500 > 400", str(caught.exception))

    def test_negative_coordinate(self):
        with self.assertRaises(BedError):
            parse("chr1\t-1\t200\n")

    def test_ragged_column_counts(self):
        # bedtools refuses rather than padding: "Differing number of BED fields
        # encountered at line: 2.  Exiting..." on stderr, exit 1, no stdout.
        with self.assertRaises(BedError):
            parse("chr1\t1\t2\tname\t0\t+\nchr1\t3\t4\n")

    def test_ragged_the_other_way_round(self):
        with self.assertRaises(BedError):
            parse("chr1\t1\t2\nchr1\t3\t4\tname\t0\t+\n")

    def test_the_error_names_the_line_number(self):
        with self.assertRaises(BedError) as caught:
            parse("chr1\t1\t2\n# skipped\nchr1\tbad\t4\n")
        self.assertIn("test:3", str(caught.exception))


class TestOrdering(unittest.TestCase):
    def test_chromosomes_sort_byte_wise_not_naturally(self):
        # chr17 before chr7, and chr10 before chr2. Confirmed against bedtools
        # on a fixture of 1, CHR1, chr1, chr10, chr2, chrM, chrX, scaffold_9.
        names = ["chr7", "chr17", "chr2", "chr10", "chrX", "chrM", "1", "CHR1"]
        records = parse("".join(f"{n}\t1\t2\n" for n in names))
        ordered = [r.chrom for r in sorted(records, key=sort_key)]
        expected = ["1", "CHR1", "chr10", "chr17", "chr2", "chr7", "chrM", "chrX"]
        self.assertEqual(ordered, expected)

    def test_start_orders_within_a_chromosome(self):
        records = parse("chr1\t200\t300\nchr1\t100\t200\n")
        self.assertEqual([r.start for r in sorted(records, key=sort_key)], [100, 200])

    def test_end_breaks_a_start_tie(self):
        records = parse("chr1\t100\t300\nchr1\t100\t200\n")
        self.assertEqual([r.end for r in sorted(records, key=sort_key)], [200, 300])

    def test_sort_is_stable_on_identical_coordinates(self):
        # bedtools keeps input order here -- a09 before a10 in the fixtures.
        text = "chr1\t100\t200\tzebra\nchr1\t100\t200\talpha\nchr1\t100\t200\tmid\n"
        names = [r.line.split("\t")[3] for r in sorted(parse(text), key=sort_key)]
        self.assertEqual(names, ["zebra", "alpha", "mid"])

    def test_zero_length_sorts_before_a_feature_starting_at_the_same_base(self):
        # a07 (chr1 500 500) comes out before a08 (chr1 500 600).
        records = parse("chr1\t500\t600\nchr1\t500\t500\n")
        self.assertEqual([r.end for r in sorted(records, key=sort_key)], [500, 600])


if __name__ == "__main__":
    unittest.main()
