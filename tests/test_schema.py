"""Tests for schema.py -- the core of this project. If this logic is
wrong, every domain's comparison is wrong."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema import ComparisonField  # noqa: E402


def test_winner_higher_is_better_true():
    f = ComparisonField("Goals", 12, 8, higher_is_better=True)
    assert f.winner == "a"


def test_winner_higher_is_better_false():
    f = ComparisonField("Handicap", 12, 8, higher_is_better=False)
    assert f.winner == "b"


def test_no_winner_when_higher_is_better_none():
    f = ComparisonField("Release Year", 2010, 2014, higher_is_better=None)
    assert f.winner is None


def test_no_winner_on_tie():
    f = ComparisonField("Rating", 7.5, 7.5, higher_is_better=True)
    assert f.winner is None


def test_no_winner_when_either_value_missing():
    f1 = ComparisonField("Goals", None, 8, higher_is_better=True)
    f2 = ComparisonField("Goals", 12, None, higher_is_better=True)
    assert f1.winner is None
    assert f2.winner is None


def test_display_formats_none_as_na():
    f = ComparisonField("Goals", None, 8)
    assert f.display_a == "N/A"
    assert f.display_b == "8"


def test_display_includes_unit():
    f = ComparisonField("Temp", 29.4, 18.0, unit="\u00b0C")
    assert "29.4" in f.display_a and "\u00b0C" in f.display_a


def test_display_formats_large_int_with_commas():
    f = ComparisonField("Votes", 35000, 8000)
    assert f.display_a == "35,000"


def test_display_passes_through_strings_unchanged():
    f = ComparisonField("Condition", "Rain", "Clear")
    assert f.display_a == "Rain"
    assert f.display_b == "Clear"
