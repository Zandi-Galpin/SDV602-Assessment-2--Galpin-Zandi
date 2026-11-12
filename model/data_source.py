"""A  data source and the logic that turns it into chart data.

No gui or file code is here, so everything can be tested without gui.
"""
import math

MAX_SERIES = 12
NUMBER_MAX = 0.8
X_COLUMN_NAMES = ("period", "date", "year", "time", "month")
Y_COLUMN_NAMES = ("count", "value", "data_value", "amount", "total")


class DataError(Exception):
    """A problem with the data!!!!! The message is safe to show to a user."""


def _text(value):
    """Return a value as stripped text"""
    return "" if value is None else str(value).strip()


def _to_number(value):
    """Return value as a finite float, or None if it is not one."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _format_number(value):
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _join_names(names, limit=5):
    names = sorted(names)
    shown = ", ".join(names[:limit])
    if len(names) > limit:
        shown += f" and {len(names) - limit} more"
    return shown


def sort_labels(labels):
    """Unique labels in order, if not numbers then text"""
    unique = set(labels)
    if all(_to_number(label) is not None for label in unique):
        return sorted(unique, key=float)
    return sorted(unique)


class ChartData:
    """Plot ready data, x labels in order plus a list of points per series.

    Each point is (x_index, y_value), x_index is the position of the
    points label in x_labels. Plotting by index keeps zoom and pan as
    numbers even when the labels are text
    """

    def __init__(self, x_key, y_key, series_key, x_labels, series, skipped):
        self.x_key = x_key
        self.y_key = y_key
        self.series_key = series_key
        self.x_labels = x_labels
        self.series = series
        self.skipped = skipped

    def x_extent(self):
        return 0, max(len(self.x_labels) - 1, 0)

    def y_extent(self):
        values = [y for points in self.series.values() for _, y in points]
        return min(values), max(values)


class DataSource:
    """Rows of data (a list of dictionarys) with named columns."""

    def __init__(self, name, columns, rows):
        self.name = name
        self.columns = list(columns)
        self.rows = [dict(row) for row in rows]
        self.part_names = [name]

    def copy(self):
        clone = DataSource(self.name, self.columns, self.rows)
        clone.part_names = list(self.part_names)
        return clone

    def is_numeric_column(self, column):
        """True if most of the column's values are numbers."""
        filled = [_text(row.get(column)) for row in self.rows]
        filled = [value for value in filled if value != ""]
        if not filled:
            return False
        numeric = sum(1 for value in filled if _to_number(value) is not None)
        return numeric / len(filled) >= NUMBER_MAX

    def distinct_count(self, column):
        values = {_text(row.get(column)) for row in self.rows}
        return len(values - {""})

    def guess_chart_columns(self):
        """Pick (x_key, y_key, series_key) for chart.

        x is a column named like a date or period, or else its just the first
        column. y is a column named like a count or value, or else its just the
        last number column. series is the first text column with a small
        number of unique values, or None.
        """
        if not self.columns:
            raise DataError(f"{self.name} has no columns.")

        lowered = {column: column.lower() for column in self.columns}
        x_key = next((c for c in self.columns if lowered[c] in X_COLUMN_NAMES), self.columns[0])

        numeric = [c for c in self.columns if c != x_key and self.is_numeric_column(c)]
        if not numeric:
            raise DataError(f"{self.name} has no numeric column to plot.")
        y_key = next((c for c in numeric if lowered[c] in Y_COLUMN_NAMES), numeric[-1])

        series_key = next(
            (c for c in self.columns
             if c not in (x_key, y_key)
             and not self.is_numeric_column(c)
             and 2 <= self.distinct_count(c) <= MAX_SERIES),
            None)
        return x_key, y_key, series_key

    def chart_data(self, x_key, y_key, series_key=None):
        """Builds ChartData. Rows without a label or a number in the
        y column are skipped and counted."""
        for key in (x_key, y_key, series_key):
            if key is not None and key not in self.columns:
                raise DataError(f"Column '{key}' was not found in {self.name}.")

        grouped = {}
        skipped = 0
        for row in self.rows:
            x_label = _text(row.get(x_key))
            y_value = _to_number(row.get(y_key))
            if x_label == "" or y_value is None:
                skipped += 1
                continue
            if series_key:
                name = _text(row.get(series_key)) or "(blank)"
            else:
                name = y_key
            grouped.setdefault(name, []).append((x_label, y_value))

        if not grouped:
            raise DataError(f"There are no numbers to plot in '{y_key}'.")

        x_labels = sort_labels(x for points in grouped.values()
                               for x, _ in points)
        index = {label: i for i, label in enumerate(x_labels)}
        series = {
            name: sorted((index[x], y) for x, y in points)
            for name, points in grouped.items()
        }
        return ChartData(x_key, y_key, series_key, x_labels, series, skipped)

    def append(self, other):
        """Add the rows of another DataSource and return how many were added.

        The columns have to match. If this raises, nothing has changed.
        """
        if not other.rows:
            raise DataError(f"{other.name} has no rows to add.")

        missing = set(self.columns) - set(other.columns)
        extra = set(other.columns) - set(self.columns)
        if missing or extra:
            problems = []
            if missing:
                problems.append("missing " + ", ".join(sorted(missing)))
            if extra:
                problems.append("unexpected " + ", ".join(sorted(extra)))
            raise DataError(f"{other.name} does not match {self.name}: "
                            + "; ".join(problems) + ".")

        self.rows.extend(dict(row) for row in other.rows)
        self.part_names.extend(other.part_names)
        return len(other.rows)

    def describe(self, chart):
        """A description of what the chart shows."""
        sentences = [f"{' + '.join(self.part_names)}: {len(self.rows)} rows, {len(self.columns)} columns."]

        showing = f"Showing {chart.y_key} by {chart.x_key}"
        if chart.series_key:
            showing += (f", one line per {chart.series_key} ({_join_names(chart.series)})")
        sentences.append(showing + ".")

        if len(chart.x_labels) > 1:
            sentences.append(f"{chart.x_key} runs from {chart.x_labels[0]} to {chart.x_labels[-1]}.")

        low, high = chart.y_extent()
        sentences.append(f"{chart.y_key} ranges from {_format_number(low)} to {_format_number(high)}.")

        if chart.skipped:
            sentences.append(f"{chart.skipped} rows were skipped because they had values that couldnt be used.")
        return " ".join(sentences)