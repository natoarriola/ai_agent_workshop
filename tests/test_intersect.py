"""Unit tests for the -b index and intersect's reporting rules. No bedtools.

Checked against the oracle first; the surprising cases carry their invocation.
"""

import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import NamedTemporaryFile

_PATH = Path(__file__).resolve().parent.parent / "mytools"
_spec = spec_from_loader("mytools", SourceFileLoader("mytools", str(_PATH)))
mytools = module_from_spec(_spec)
_spec.loader.exec_module(mytools)


def index_of(*rows):
    """Build an Index from (chrom, start, end) rows, via a real file."""
    with NamedTemporaryFile("w", suffix=".bed", delete=False) as fh:
        for chrom, start, end in rows:
            fh.write(f"{chrom}\t{start}\t{end}\n")
        path = fh.name
    try:
        return mytools.Index.load(path)
    finally:
        Path(path).unlink()


def query(index, chrom, start, end):
    """Hits for [start, end), widening the query the way intersect does."""
    return index.hits(chrom, *mytools.widen_if_empty(start, end))


class TestIndexSearch(unittest.TestCase):
    def test_no_such_chromosome(self):
        index = index_of(("chr1", 100, 200))
        self.assertEqual(query(index, "chr9", 100, 200), [])

    def test_plain_hit(self):
        index = index_of(("chr1", 100, 200))
        self.assertEqual(query(index, "chr1", 150, 250), [(100, 200)])

    def test_bookended_is_not_a_hit(self):
        index = index_of(("chr1", 100, 200))
        self.assertEqual(query(index, "chr1", 200, 300), [])

    def test_nested_is_a_hit_both_ways(self):
        self.assertEqual(query(index_of(("chr1", 100, 300)), "chr1", 150, 200),
                         [(100, 300)])
        self.assertEqual(query(index_of(("chr1", 150, 200)), "chr1", 100, 300),
                         [(150, 200)])

    def test_identical_intervals_both_hit(self):
        index = index_of(("chr1", 100, 200), ("chr1", 100, 200))
        self.assertEqual(query(index, "chr1", 100, 200), [(100, 200), (100, 200)])

    def test_an_interval_far_left_does_not_stop_the_search(self):
        # The running max-end is what lets the scan stop early; a long interval
        # near the start of the chromosome must not be skipped.
        index = index_of(("chr1", 0, 1000), ("chr1", 10, 20), ("chr1", 900, 950))
        self.assertEqual(query(index, "chr1", 920, 930), [(0, 1000), (900, 950)])

    def test_position_zero(self):
        index = index_of(("chr1", 0, 50))
        self.assertEqual(query(index, "chr1", 0, 100), [(0, 50)])


class TestHitOrder(unittest.TestCase):
    """bedtools reports hits in -b file order, not coordinate order."""

    def test_hits_come_back_in_file_order(self):
        # bedtools intersect -a "chr1 100 200" -b [150-160, 110-120, 180-190]
        # prints 150 160, then 110 120, then 180 190.
        index = index_of(("chr1", 150, 160), ("chr1", 110, 120), ("chr1", 180, 190))
        self.assertEqual(
            query(index, "chr1", 100, 200), [(150, 160), (110, 120), (180, 190)]
        )

    def test_file_order_is_per_file_not_per_chromosome(self):
        index = index_of(("chr2", 100, 200), ("chr1", 100, 200))
        self.assertEqual(query(index, "chr1", 100, 200), [(100, 200)])


class TestZeroLength(unittest.TestCase):
    """-b features are stored widened, and the widening reaches the output."""

    def test_zero_length_b_is_stored_widened(self):
        # bedtools intersect -a "chr1 100 200" -b "chr1 150 150" prints the
        # region chr1 149 151 -- so the stored interval really is [149, 151).
        index = index_of(("chr1", 150, 150))
        self.assertEqual(query(index, "chr1", 100, 200), [(149, 151)])

    def test_zero_length_b_reaches_one_base_past_the_end(self):
        index = index_of(("chr1", 200, 200))
        self.assertEqual(query(index, "chr1", 100, 200), [(199, 201)])

    def test_zero_length_b_two_bases_past_the_end_does_not_reach(self):
        self.assertEqual(query(index_of(("chr1", 201, 201)), "chr1", 100, 200), [])

    def test_zero_length_a_is_widened_for_the_query(self):
        # a = chr1 600 600 against b = chr1 400 600 is reported, even though
        # 600 is not a base of [400, 600).
        self.assertEqual(query(index_of(("chr1", 400, 600)), "chr1", 600, 600),
                         [(400, 600)])

    def test_zero_length_on_both_sides(self):
        self.assertEqual(query(index_of(("chr1", 500, 500)), "chr1", 500, 500),
                         [(499, 501)])

    def test_a_negative_widening_in_b_is_the_oracle_crash(self):
        # chr2 0 0 in -b widens to -1 and bedtools dies: "Received illegal bin
        # number -1 from getBin call", exit 1, empty stdout. We refuse too.
        with self.assertRaises(mytools.BedError):
            index_of(("chr2", 0, 0))

    def test_a_zero_length_at_zero_is_fine_in_a(self):
        # Only -b is indexed, so chr2 0 0 on the -a side is harmless --
        # `intersect -a a.bed -b b.bed` exits 0 with a.bed containing it.
        self.assertEqual(query(index_of(("chr2", 0, 10)), "chr2", 0, 0), [(0, 10)])


if __name__ == "__main__":
    unittest.main()
