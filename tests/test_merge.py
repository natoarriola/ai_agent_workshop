"""Unit tests for merge clustering. No bedtools, no fixtures.

Every expected value was checked against real bedtools first. The zero-length
cases are the ones nobody guesses right, so each carries its oracle result.
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


def merge(text, d=0):
    records = mytools.read_bed(io.StringIO(text), "test")
    return list(mytools.merge_clusters(records, d, "test"))


def bed(*rows):
    return "".join(f"{chrom}\t{start}\t{end}\n" for chrom, start, end in rows)


class TestBasicClustering(unittest.TestCase):
    def test_empty_input_yields_nothing(self):
        self.assertEqual(merge(""), [])

    def test_single_feature(self):
        self.assertEqual(merge(bed(("chr1", 100, 200))), [("chr1", 100, 200)])

    def test_overlapping_features_join(self):
        got = merge(bed(("chr1", 100, 200), ("chr1", 150, 250)))
        self.assertEqual(got, [("chr1", 100, 250)])

    def test_disjoint_features_stay_apart(self):
        got = merge(bed(("chr1", 100, 200), ("chr1", 300, 400)))
        self.assertEqual(got, [("chr1", 100, 200), ("chr1", 300, 400)])

    def test_nested_feature_does_not_shorten_the_cluster(self):
        # The second feature ends earlier; the cluster end is a running max.
        got = merge(bed(("chr1", 100, 300), ("chr1", 150, 200)))
        self.assertEqual(got, [("chr1", 100, 300)])

    def test_equal_starts_decreasing_ends_is_not_an_error(self):
        # bedtools exits 0 here and prints chr1 100 200.
        got = merge(bed(("chr1", 100, 200), ("chr1", 100, 150)))
        self.assertEqual(got, [("chr1", 100, 200)])

    def test_clusters_never_span_chromosomes(self):
        got = merge(bed(("chr1", 100, 200), ("chr2", 100, 200)))
        self.assertEqual(got, [("chr1", 100, 200), ("chr2", 100, 200)])


class TestBookended(unittest.TestCase):
    """The gap between bookended features is 0, so they merge at the default d."""

    def test_bookended_merge_at_the_default_distance(self):
        got = merge(bed(("chr1", 100, 200), ("chr1", 200, 300)))
        self.assertEqual(got, [("chr1", 100, 300)])

    def test_one_base_gap_does_not_merge_at_zero(self):
        got = merge(bed(("chr1", 100, 200), ("chr1", 201, 300)))
        self.assertEqual(got, [("chr1", 100, 200), ("chr1", 201, 300)])

    def test_one_base_gap_merges_at_one(self):
        got = merge(bed(("chr1", 100, 200), ("chr1", 201, 300)), d=1)
        self.assertEqual(got, [("chr1", 100, 300)])


class TestDistance(unittest.TestCase):
    def test_gap_equal_to_d_merges(self):
        # bedtools -d 10 joins chr1 100 200 and chr1 210 300; -d 9 does not.
        self.assertEqual(
            merge(bed(("chr1", 100, 200), ("chr1", 210, 300)), d=10),
            [("chr1", 100, 300)],
        )

    def test_gap_one_over_d_does_not_merge(self):
        self.assertEqual(
            merge(bed(("chr1", 100, 200), ("chr1", 210, 300)), d=9),
            [("chr1", 100, 200), ("chr1", 210, 300)],
        )

    def test_negative_d_demands_that_much_overlap(self):
        # -d -5 joins (100,200) with (195,300) -- five bases of overlap -- but
        # not with (196,300), which overlaps by four.
        self.assertEqual(
            merge(bed(("chr1", 100, 200), ("chr1", 195, 300)), d=-5),
            [("chr1", 100, 300)],
        )
        self.assertEqual(
            merge(bed(("chr1", 100, 200), ("chr1", 196, 300)), d=-5),
            [("chr1", 100, 200), ("chr1", 196, 300)],
        )


class TestZeroLength(unittest.TestCase):
    """Widened to [x-1, x+1), and the widening reaches the output.

    The exception is a cluster of one feature, which prints its own original
    coordinates. Confirmed against bedtools on all of the cases below.
    """

    def test_a_lone_zero_length_feature_is_unchanged(self):
        self.assertEqual(merge(bed(("chr1", 500, 500))), [("chr1", 500, 500)])

    def test_a_lone_zero_length_feature_is_unchanged_at_any_distance(self):
        self.assertEqual(merge(bed(("chr1", 500, 500)), d=100), [("chr1", 500, 500)])

    def test_two_zero_length_features_at_the_same_point_widen(self):
        # bedtools prints chr1 499 501, not chr1 500 500.
        got = merge(bed(("chr1", 500, 500), ("chr1", 500, 500)))
        self.assertEqual(got, [("chr1", 499, 501)])

    def test_zero_length_widens_leftwards_into_a_cluster(self):
        # The fixture case: sorted a.bed reports chr1 499 600 for a07 + a08.
        got = merge(bed(("chr1", 500, 500), ("chr1", 500, 600)))
        self.assertEqual(got, [("chr1", 499, 600)])

    def test_zero_length_reaches_one_base_further_than_you_expect(self):
        # (501,600) does not touch [500,500), but it does touch [499,501).
        got = merge(bed(("chr1", 500, 500), ("chr1", 501, 600)))
        self.assertEqual(got, [("chr1", 499, 600)])

    def test_zero_length_does_not_reach_two_bases(self):
        got = merge(bed(("chr1", 500, 500), ("chr1", 502, 600)))
        self.assertEqual(got, [("chr1", 500, 500), ("chr1", 502, 600)])

    def test_zero_length_widens_rightwards_out_of_a_cluster(self):
        got = merge(bed(("chr1", 400, 500), ("chr1", 500, 500)))
        self.assertEqual(got, [("chr1", 400, 501)])

    def test_two_zero_length_features_one_base_apart(self):
        got = merge(bed(("chr1", 500, 500), ("chr1", 501, 501)))
        self.assertEqual(got, [("chr1", 499, 502)])

    def test_two_zero_length_features_three_bases_apart_stay_apart(self):
        got = merge(bed(("chr1", 500, 500), ("chr1", 503, 503)))
        self.assertEqual(got, [("chr1", 500, 500), ("chr1", 503, 503)])

    def test_the_distance_gap_is_measured_on_widened_coordinates(self):
        # chr1 500 500 and chr1 503 600 stay apart at -d 1 and join at -d 2,
        # because the gap is measured from the widened end at 501.
        rows = bed(("chr1", 500, 500), ("chr1", 503, 600))
        self.assertEqual(merge(rows, d=1), [("chr1", 500, 500), ("chr1", 503, 600)])
        self.assertEqual(merge(rows, d=2), [("chr1", 499, 600)])

    def test_zero_length_at_zero_can_print_a_negative_coordinate(self):
        # chr1 0 0 beside chr1 0 10 really does print chr1 -1 10. Do not clamp
        # it: whatever bedtools prints is the answer.
        self.assertEqual(
            merge(bed(("chr1", 0, 0), ("chr1", 0, 10))), [("chr1", -1, 10)]
        )
        self.assertEqual(
            merge(bed(("chr1", 0, 0), ("chr1", 1, 10))), [("chr1", -1, 10)]
        )

    def test_a_lone_zero_length_at_zero_is_still_unchanged(self):
        self.assertEqual(merge(bed(("chr1", 0, 0))), [("chr1", 0, 0)])

    def test_zero_length_swallowed_by_a_containing_feature(self):
        got = merge(bed(("chr1", 400, 600), ("chr1", 500, 500)))
        self.assertEqual(got, [("chr1", 400, 600)])

    def test_zero_length_just_past_a_feature_extends_it(self):
        self.assertEqual(
            merge(bed(("chr1", 400, 600), ("chr1", 601, 601))), [("chr1", 400, 602)]
        )


class TestSortedness(unittest.TestCase):
    """Checked the way bedtools checks it, which is looser than you would guess."""

    def test_out_of_order_starts_are_an_error(self):
        with self.assertRaises(BedError):
            merge(bed(("chr1", 300, 400), ("chr1", 100, 200)))

    def test_descending_chromosomes_are_not_an_error(self):
        # bedtools exits 0 and keeps input order. Only revisiting is an error.
        got = merge(bed(("chr2", 100, 200), ("chr1", 100, 200)))
        self.assertEqual(got, [("chr2", 100, 200), ("chr1", 100, 200)])

    def test_returning_to_an_earlier_chromosome_is_an_error(self):
        with self.assertRaises(BedError):
            merge(bed(("chr1", 100, 200), ("chr2", 100, 200), ("chr1", 300, 400)))

    def test_the_error_says_what_was_out_of_order(self):
        with self.assertRaises(BedError) as caught:
            merge(bed(("chr1", 300, 400), ("chr1", 100, 200)))
        self.assertIn("chr1:100", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
