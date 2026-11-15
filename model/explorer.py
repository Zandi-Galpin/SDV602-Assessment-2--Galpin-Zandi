"""The state and logic of one DES

Holds the data source, the chart built from it and the visible area.
It doesnt do stuff with files or GUIs, a controller loads a DataSource,
Then gives it in. each change builds the new state first and then
replaces the old one, so failure leaves the screen as it was.
Zoom and pan work on the x axis only. After each one the y axis is
rescaled to fit the data that is visible, so the chart never zooms into an
empty gap between lines.
"""
from model.data_source import DataError
from model.view_window import ViewWindow


class Explorer:

    def __init__(self):
        self.source = None
        self.chart = None
        self.view = None

    def has_data(self):
        return self.source is not None

    def set_source(self, source):
        """Show a new data source (used for the first load and when changing
        a source). The view is reset to show everything."""
        x_key, y_key, series_key = source.guess_chart_columns()
        chart = source.chart_data(x_key, y_key, series_key)
        self.source = source
        self._show(chart)

    def append_source(self, other):
        """Add another sources rows to the current one and draw again with the
        same columns. Returns the number of rows added."""
        self.require_data()
        candidate = self.source.copy()
        added = candidate.append(other)
        chart = candidate.chart_data(
            self.chart.x_key, self.chart.y_key, self.chart.series_key)
        self.source = candidate
        self._show(chart)
        return added

    def zoom_in(self):
        self.require_data()
        self.view.zoom(ViewWindow.ZOOM_STEP, zoom_y=False)
        self._fit_y()

    def zoom_out(self):
        self.require_data()
        self.view.zoom(1 / ViewWindow.ZOOM_STEP, zoom_y=False)
        self._fit_y()

    def pan(self, dx_fraction):
        self.require_data()
        self.view.pan(dx_fraction)
        self._fit_y()

    def reset_view(self):
        self.require_data()
        self.view.reset()

    def describe(self):
        if not self.has_data():
            return "No data loaded."
        return self.source.describe(self.chart)

    def require_data(self):
        if not self.has_data():
            raise DataError("Load a data source first.")

    def _show(self, chart):
        x_low, x_high = chart.x_extent()
        y_low, y_high = chart.y_extent()
        self.chart = chart
        self.view = ViewWindow.fitting(x_low, x_high, y_low, y_high)

    def _fit_y(self):
        """Rescale y to the lines visible in the current x range. If there
        is nothing to fit the y range is left as what it was before"""
        values = self._visible_values()
        if values:
            self.view.set_y(*ViewWindow.padded(min(values), max(values)))

    def _visible_values(self):
        """The y values of every point inside the x range plus
        the height of each line where it crosses the left and right edges.
        The edges matter when the view sits between two points. no point
        is visible then, but the line between them is."""
        x_min, x_max = self.view.x_min, self.view.x_max
        values = []
        for points in self.chart.series.values():
            values.extend(y for x, y in points if x_min <= x <= x_max)
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                for edge in (x_min, x_max):
                    if x0 < edge < x1:
                        values.append(
                            y0 + (y1 - y0) * (edge - x0) / (x1 - x0))
        return values
