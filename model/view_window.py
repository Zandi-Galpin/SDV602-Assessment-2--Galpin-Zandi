"""The visible part of the chart. zoom and pan are
changes to four numbers, so they can be tested without a window.
"""

# spans this close to the full range count as the full range, so repeated
# zooming in and out wont leave the view short of fully zoomed out.
FULL_SPAN_TOLERANCE = 1e-9


class ViewWindow:
    ZOOM_STEP = 1.5
    PAN_STEP = 0.25
    MIN_SPAN = 0.02  # cant zoom past 2% of the full thing

    def __init__(self, x_min, x_max, y_min, y_max):
        if x_max <= x_min or y_max <= y_min:
            raise ValueError("view limits need to have max greater than min")
        self.full = (x_min, x_max, y_min, y_max)
        self.x_min, self.x_max = x_min, x_max
        self.y_min, self.y_max = y_min, y_max

    @classmethod
    def fitting(cls, x_low, x_high, y_low, y_high, padding=0.05):
        """A full view around the given extents, with some padding.
        A range of zero width (one value) is made wider so it can be drawn."""
        x_min, x_max = cls.padded(x_low, x_high, padding)
        y_min, y_max = cls.padded(y_low, y_high, padding)
        return cls(x_min, x_max, y_min, y_max)

    @staticmethod
    def padded(low, high, padding=0.05):
        span = high - low
        if span == 0:
            return low - 1.0, high + 1.0
        return low - span * padding, high + span * padding

    @staticmethod
    def _fit_inside(low, high, full_low, full_high):
        """Shift (low, high) so it lies inside the full range."""
        span = high - low
        full_span = full_high - full_low
        if span >= full_span * (1 - FULL_SPAN_TOLERANCE):
            return full_low, full_high
        if low < full_low:
            return full_low, full_low + span
        if high > full_high:
            return full_high - span, full_high
        return low, high

    @classmethod
    def _zoom_axis(cls, low, high, full_low, full_high, factor):
        full_span = full_high - full_low
        span = (high - low) / factor
        span = max(min(span, full_span), full_span * cls.MIN_SPAN)
        centre = (low + high) / 2
        return cls._fit_inside(centre - span / 2, centre +
                               span / 2, full_low, full_high)

    def zoom(self, factor, zoom_x=True, zoom_y=True):
        """factor above 1 zooms in, below 1 zooms out.
        zoom_x and zoom_y choose which axes change."""
        if factor <= 0:
            raise ValueError("zoom factor must be positive")
        fx_min, fx_max, fy_min, fy_max = self.full
        if zoom_x:
            self.x_min, self.x_max = self._zoom_axis(
                self.x_min, self.x_max, fx_min, fx_max, factor)
        if zoom_y:
            self.y_min, self.y_max = self._zoom_axis(
                self.y_min, self.y_max, fy_min, fy_max, factor)

    def pan(self, dx_fraction=0.0, dy_fraction=0.0):
        """Shift the view by a fraction of its width and height.
        The view stops at the edge of the data."""
        fx_min, fx_max, fy_min, fy_max = self.full
        dx = (self.x_max - self.x_min) * dx_fraction
        dy = (self.y_max - self.y_min) * dy_fraction
        self.x_min, self.x_max = self._fit_inside(
            self.x_min + dx, self.x_max + dx, fx_min, fx_max)
        self.y_min, self.y_max = self._fit_inside(
            self.y_min + dy, self.y_max + dy, fy_min, fy_max)

    def set_y(self, low, high):
        """Set the visible y range directly (used to fit y to the data)."""
        if high <= low:
            raise ValueError("view limits must have max greater than min")
        self.y_min, self.y_max = low, high

    def reset(self):
        self.x_min, self.x_max, self.y_min, self.y_max = self.full

    def is_full_view(self):
        return (self.x_min, self.x_max, self.y_min, self.y_max) == self.full

    def limits(self):
        return self.x_min, self.x_max, self.y_min, self.y_max
