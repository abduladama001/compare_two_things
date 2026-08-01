"""The one schema every domain adapts into. This is the actual point of
this project: Weather, Currency, Movies, and GitHub are four completely
unrelated data sources with four completely different raw JSON shapes --
but the comparison UI only ever has to know about this one dataclass.

Each domain module (weather_adapter.py, currency_adapter.py, etc.) writes
exactly one function -- to_comparison_fields(item_a, item_b) -- that
converts its domain's raw data into a list[ComparisonField]. The
renderer in main.py / templates/index.html never branches on "is this
weather or movies" -- it just iterates the list.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ComparisonField:
    label: str
    value_a: Any
    value_b: Any
    higher_is_better: bool | None = None  # None = no meaningful "winner" for this row
    unit: str | None = None

    @property
    def display_a(self) -> str:
        return _format_value(self.value_a, self.unit)

    @property
    def display_b(self) -> str:
        return _format_value(self.value_b, self.unit)

    @property
    def winner(self) -> str | None:
        """'a', 'b', or None (no winner -- missing data, tie, or this
        field has no meaningful 'better' direction at all).
        """
        if self.higher_is_better is None:
            return None
        if self.value_a is None or self.value_b is None:
            return None
        if self.value_a == self.value_b:
            return None
        a_wins = self.value_a > self.value_b if self.higher_is_better else self.value_a < self.value_b
        return "a" if a_wins else "b"


def _format_value(value: Any, unit: str | None) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        text = f"{value:,.1f}"
    elif isinstance(value, int):
        text = f"{value:,}"
    else:
        text = str(value)
    return f"{text} {unit}" if unit else text
