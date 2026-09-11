"""Unit tests for the interval predicates. No bedtools, no fixtures, milliseconds.

Every expected value here was checked against real bedtools first -- see the
comment on each case. Where bedtools surprises, the test encodes bedtools.
"""

import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "mytools"
_spec = spec_from_loader("mytools", SourceFileLoader("mytools", str(_PATH)))
mytools = module_from_spec(_spec)
_spec.loader.exec_module(mytools)

overlaps = mytools.overlaps
within_merge_distance = mytools.within_merge_distance


class TestOverlapPredicate(unittest.TestCase):
    """The predicate itself: a.start < b.end AND b.start < a.end, strict both ways."""

    def test_plain_overlap(self):
        self.assertTrue(overlaps(100, 200, 150, 250))

    def test_disjoint(self):
        self.assertFalse(overlaps(100, 200, 300, 400))

    def test_one_base_of_overlap(self):
        # b covers 199 only; a covers 100..199. They share base 199.
        self.assertTrue(overlaps(100, 200, 199, 300))

    def test_one_base_apart(self):
        # a covers 100..199, b covers 201..299. Base 200 belongs to neither.
        self.assertFalse(overlaps(100, 200, 201, 300))

    def test_is_symmetric(self):
        self.assertEqual(overlaps(100, 200, 150, 250), overlaps(150, 250, 100, 200))
        self.assertEqual(overlaps(100, 200, 200, 300), overlaps(200, 300, 100, 200))


class TestBookended(unittest.TestCase):
    """a.end == b.start: touching, but sharing no base."""

    def test_bookended_do_not_overlap(self):
        # a01/a02 in the fixtures meet at 100. bedtools intersect -v reports the
        # left one, i.e. no overlap.
        self.assertFalse(overlaps(100, 200, 200, 300))

    def test_bookended_the_other_way_round(self):
        self.assertFalse(overlaps(200, 300, 100, 200))

    def test_bookended_do_merge_at_distance_zero(self):
        # The gap is 0 and merge joins features whose gap is <= d. This is the
        # one place bookended features behave as if they belonged together.
        self.assertTrue(within_merge_distance(200, 200, 0))

    def test_one_base_gap_does_not_merge_at_zero(self):
        self.assertFalse(within_merge_distance(200, 201, 0))

    def test_one_base_gap_merges_at_distance_one(self):
        self.assertTrue(within_merge_distance(200, 201, 1))


class TestZeroLength(unittest.TestCase):
    """start == end. Legal in BED, and bedtools does not treat it as empty.

    bedtools widens [x, x) to [x - 1, x + 1) before testing overlap. Confirmed
    against the oracle on twelve cases; the four corners are pinned below.
    """

    def test_zero_length_inside_an_interval(self):
        # bedtools intersect -u -a "chr1 500 500" -b "chr1 400 600" -> reported.
        self.assertTrue(overlaps(500, 500, 400, 600))

    def test_zero_length_on_the_start_edge(self):
        self.assertTrue(overlaps(400, 400, 400, 600))

    def test_zero_length_on_the_end_edge(self):
        # Surprising: 600 is NOT a base of [400, 600), yet bedtools reports an
        # overlap. That is the widening, and it is the oracle's answer.
        self.assertTrue(overlaps(600, 600, 400, 600))

    def test_zero_length_just_past_the_end_edge(self):
        # One base further out and the widening no longer reaches.
        self.assertFalse(overlaps(601, 601, 400, 600))

    def test_zero_length_just_before_the_start_edge(self):
        self.assertFalse(overlaps(399, 399, 400, 600))

    def test_two_zero_length_at_the_same_point(self):
        # a07 and b07 in the fixtures are both chr1 500 500.
        self.assertTrue(overlaps(500, 500, 500, 500))

    def test_two_zero_length_one_base_apart(self):
        self.assertTrue(overlaps(500, 500, 501, 501))

    def test_two_zero_length_two_bases_apart(self):
        self.assertFalse(overlaps(500, 500, 502, 502))

    def test_zero_length_in_b_is_widened_too(self):
        # bedtools intersect -a "chr1 100 200" -b "chr1 150 150" prints the
        # region chr1 149 151 -- b was widened, not a.
        self.assertTrue(overlaps(100, 200, 150, 150))
        self.assertTrue(overlaps(100, 200, 200, 200))
        self.assertFalse(overlaps(100, 200, 201, 201))


class TestNested(unittest.TestCase):
    """One interval entirely inside another. a06 sits inside a05 in the fixtures."""

    def test_nested_overlaps(self):
        self.assertTrue(overlaps(320, 350, 300, 400))

    def test_containing_overlaps(self):
        self.assertTrue(overlaps(300, 400, 320, 350))

    def test_nested_sharing_the_start(self):
        self.assertTrue(overlaps(300, 320, 300, 400))

    def test_nested_sharing_the_end(self):
        self.assertTrue(overlaps(380, 400, 300, 400))


class TestIdentical(unittest.TestCase):
    """a09 and a10 are byte-identical; a03 and a04 differ only by strand."""

    def test_identical_intervals_overlap(self):
        self.assertTrue(overlaps(700, 800, 700, 800))

    def test_identical_zero_length_intervals_overlap(self):
        self.assertTrue(overlaps(300, 300, 300, 300))


class TestPositionZero(unittest.TestCase):
    """Coordinates at 0. a01 starts at 0; a12 is chr2 0 0."""

    def test_interval_at_zero(self):
        self.assertTrue(overlaps(0, 100, 0, 50))

    def test_interval_at_zero_is_bookended_with_its_neighbour(self):
        self.assertFalse(overlaps(0, 100, 100, 200))

    def test_zero_length_at_zero(self):
        # Widening takes this to [-1, 1). A negative coordinate never reaches
        # the output, but the predicate has to survive producing one.
        self.assertTrue(overlaps(0, 0, 0, 10))

    def test_zero_length_at_zero_does_not_reach_base_one(self):
        self.assertFalse(overlaps(0, 0, 1, 10))

    def test_merge_at_zero(self):
        self.assertTrue(within_merge_distance(0, 0, 0))


if __name__ == "__main__":
    unittest.main()
