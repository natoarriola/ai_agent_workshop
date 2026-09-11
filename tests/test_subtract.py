"""Unit tests for subtract's hole-punching. No bedtools, no fixtures.

Checked against the oracle first. The zero-length rule here is a third one,
different again from intersect's and merge's, so each case names its evidence.
"""

import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "mytools"
_spec = spec_from_loader("mytools", SourceFileLoader("mytools", str(_PATH)))
mytools = module_from_spec(_spec)
_spec.loader.exec_module(mytools)

remaining = mytools.remaining


class TestRemaining(unittest.TestCase):
    def test_no_holes_leaves_the_feature_whole(self):
        self.assertEqual(remaining(100, 200, []), [(100, 200)])

    def test_a_hole_that_misses_leaves_the_feature_whole(self):
        self.assertEqual(remaining(100, 200, [(300, 400)]), [(100, 200)])

    def test_a_bookended_hole_leaves_the_feature_whole(self):
        # Touching is not overlapping: [200, 300) removes no base of [100, 200).
        self.assertEqual(remaining(100, 200, [(200, 300)]), [(100, 200)])

    def test_a_hole_off_the_left_trims_the_start(self):
        self.assertEqual(remaining(100, 200, [(50, 150)]), [(150, 200)])

    def test_a_hole_off_the_right_trims_the_end(self):
        self.assertEqual(remaining(100, 200, [(150, 250)]), [(100, 150)])

    def test_a_hole_in_the_middle_splits_one_feature_into_two(self):
        self.assertEqual(remaining(100, 200, [(140, 160)]), [(100, 140), (160, 200)])

    def test_a_covering_hole_removes_the_feature(self):
        self.assertEqual(remaining(100, 200, [(50, 250)]), [])

    def test_an_exactly_matching_hole_removes_the_feature(self):
        self.assertEqual(remaining(100, 200, [(100, 200)]), [])

    def test_holes_accumulate(self):
        got = remaining(0, 100, [(10, 20), (40, 50), (90, 200)])
        self.assertEqual(got, [(0, 10), (20, 40), (50, 90)])

    def test_holes_need_not_arrive_in_order(self):
        # They arrive in -b file order, which is not sorted.
        got = remaining(0, 100, [(90, 200), (10, 20), (40, 50)])
        self.assertEqual(got, [(0, 10), (20, 40), (50, 90)])

    def test_overlapping_holes_do_not_double_cut(self):
        self.assertEqual(remaining(0, 100, [(10, 60), (40, 80)]), [(0, 10), (80, 100)])

    def test_a_split_piece_can_be_split_again(self):
        got = remaining(0, 100, [(20, 30), (60, 70)])
        self.assertEqual(got, [(0, 20), (30, 60), (70, 100)])

    def test_no_zero_length_piece_is_ever_produced(self):
        for holes in ([(0, 50)], [(50, 100)], [(0, 1), (99, 100)]):
            for start, end in remaining(0, 100, holes):
                self.assertLess(start, end)


class TestWidenedHoles(unittest.TestCase):
    """The holes are -b's widened intervals, which is what eats the extra base."""

    def test_the_fixture_case(self):
        # a01 (chr1 0 100) against b01 (0,50) and the zero-length b02 at 100,
        # which widens to [99, 101): bedtools prints chr1 50 99, not 50 100.
        holes = [mytools.widen_if_empty(0, 50), mytools.widen_if_empty(100, 100)]
        self.assertEqual(remaining(0, 100, holes), [(50, 99)])

    def test_a_zero_length_hole_in_the_middle_takes_two_bases(self):
        # bedtools subtract -a "chr1 10 20" -b "chr1 15 15" prints
        # chr1 10 14 and chr1 16 20 -- the hole is [14, 16).
        holes = [mytools.widen_if_empty(15, 15)]
        self.assertEqual(remaining(10, 20, holes), [(10, 14), (16, 20)])


class TestZeroLengthFeature(unittest.TestCase):
    """A zero-length -a feature is cut as [x-1, x+1) but printed as [x, x).

    It survives whole or not at all, so what matters is only whether anything
    is left of the widened span. All four confirmed against bedtools.
    """

    @staticmethod
    def survives(point, holes):
        start, end = mytools.widen_if_empty(point, point)
        return bool(remaining(start, end, holes))

    def test_survives_a_hole_that_starts_at_the_point(self):
        # b = [9, 10) leaves the base at 8, so chr1 9 9 is kept.
        self.assertTrue(self.survives(9, [(9, 10)]))

    def test_survives_a_hole_that_ends_at_the_point(self):
        self.assertTrue(self.survives(9, [(6, 9)]))

    def test_is_removed_by_a_hole_that_covers_the_widened_span(self):
        # b = [8, 10) covers all of it, so bedtools prints nothing.
        self.assertFalse(self.survives(9, [(8, 10)]))

    def test_is_removed_by_an_identical_zero_length_hole(self):
        # b = chr1 9 9 widens to [8, 10) -- the same covering hole.
        self.assertFalse(self.survives(9, [mytools.widen_if_empty(9, 9)]))

    def test_survives_a_zero_length_hole_one_base_away(self):
        self.assertTrue(self.survives(9, [mytools.widen_if_empty(10, 10)]))

    def test_is_removed_by_two_holes_that_together_cover_it(self):
        # From the fuzzer: holes [9, 10) and [6, 9) leave nothing of [8, 10).
        self.assertFalse(self.survives(9, [(9, 10), (6, 9)]))


if __name__ == "__main__":
    unittest.main()
