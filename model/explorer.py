"""The state and logic of one DES

Holds the data source, the chart built from it and the visible area.
It doesnt do stuff with files or GUIs, a controller loads a DataSource,
Then gives it in. each change builds the new state first and then 
replaces the old one, so failure leaves the screen as it was.
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
        self._require_data()
        candidate = self.source.copy()
        added = candidate.append(other)
        chart = candidate.chart_data(self.chart.x_key, self.chart.y_key, self.chart.series_key)
        self.source = candidate
        self._show(chart)
        return added

    def zoom_in(self):
        self._require_data()
        self.view.zoom(ViewWindow.ZOOM_STEP)

    def zoom_out(self):
        self._require_data()
        self.view.zoom(1 / ViewWindow.ZOOM_STEP)

    def pan(self, dx_fraction=0.0, dy_fraction=0.0):
        self._require_data()
        self.view.pan(dx_fraction, dy_fraction)

    def reset_view(self):
        self._require_data()
        self.view.reset()

    def describe(self):
        if not self.has_data():
            return "No data loaded."
        return self.source.describe(self.chart)

    def _show(self, chart):
        x_low, x_high = chart.x_extent()
        y_low, y_high = chart.y_extent()
        self.chart = chart
        self.view = ViewWindow.fitting(x_low, x_high, y_low, y_high)

    def _require_data(self):
        if not self.has_data():
            raise DataError("Load a data source first.")