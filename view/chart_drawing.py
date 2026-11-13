"""Draws charts onto a matplotlib figure.

These functions only need a figure, not a window or pyplot, so they can
be tested in headless and multiple windows can each draw their own figure
without needing any global state
"""
import math

MAX_TICKS = 10
PLACEHOLDER_Y = (2, 4, 3, 6, 5, 8, 7)


def visible_ticks(x_labels, x_min, x_max, max_ticks=MAX_TICKS):
    """Choose which x labels to show for the visible range.

    Returns (positions, labels). Only labels in the view are used
    """
    first = max(math.ceil(x_min), 0)
    last = min(math.floor(x_max), len(x_labels) - 1)
    if last < first:
        return [], []
    count = last - first + 1
    step = max(math.ceil(count / max_ticks), 1)
    positions = list(range(first, last + 1, step))
    return positions, [x_labels[i] for i in positions]


def draw_chart(figure, chart, view, title=None):
    """Draw ChartData inside the part given by a ViewWindow."""
    figure.clear()
    axes = figure.add_subplot(111)

    for name, points in chart.series.items():
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        axes.plot(xs, ys, marker="o", markersize=4, label=name)

    axes.set_xlim(view.x_min, view.x_max)
    axes.set_ylim(view.y_min, view.y_max)

    positions, labels = visible_ticks(chart.x_labels, view.x_min, view.x_max)
    axes.set_xticks(positions)
    axes.set_xticklabels(labels, rotation=45, ha="right")

    axes.set_xlabel(chart.x_key)
    axes.set_ylabel(chart.y_key)
    if title:
        axes.set_title(title)
    if chart.series_key:
        axes.legend(title=chart.series_key, fontsize="small")
    axes.grid(True, alpha=0.3)
    figure.tight_layout()


def draw_placeholder(figure, message="No data loaded"):
    """Draw an empty chart with a message, shown until real data
    is available."""
    figure.clear()
    axes = figure.add_subplot(111)

    axes.plot(range(len(PLACEHOLDER_Y)), PLACEHOLDER_Y, color="lightgray", linestyle="--", marker="o")
    axes.set_xticks([])
    axes.set_yticks([])
    axes.text(0.5, 0.5, message, transform=axes.transAxes, ha="center",
              va="center", fontsize=16, color="gray",
              bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85})
    figure.tight_layout()