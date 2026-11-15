
"""Headless tests for the local DES
includes chart drawing and the controller. No window is opened.
"""
import sys

import FreeSimpleGUI as sg
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from controller.des_controller import DesController
from model.data_source import DataSource
from model.view_window import ViewWindow
from tests.test_local_mode import approx, write_temp_csv
from view.chart_drawing import draw_chart, draw_placeholder, visible_ticks

FIRST = "Period,Count,Type\n2010,50,Births\n2010,40,Deaths\n" \
        "2011,55,Births\n2011,45,Deaths\n"
SECOND = "Period,Count,Type\n2012,60,Births\n2012,48,Deaths\n"
WRONG_COLUMNS = "Period,Other\n2012,1\n"
NO_NUMBERS = "Name,Colour\nx,red\n"


class FakeDesView:
    """Returns scripted events, gives out
    scripted file paths ('' means the user cancelled the dialog) and
    records everything the controller shows."""

    def __init__(self, events, files=()):
        self._events = list(events)
        self._files = list(files)
        self.draws = []  # (has_data, view limits) at each redraw
        self.asked = []  # prompts of the file dialogs that were opened
        self.errors = []
        self.statuses = []
        self.closed = False

    def read(self, timeout=None):
        if not self._events:
            raise RuntimeError("FakeDesView ran out of scripted events")
        return self._events.pop(0), {}

    def draw(self, explorer, loading=False):
        limits = explorer.view.limits() if explorer.has_data() else None
        self.draws.append((explorer.has_data(), limits))

    def ask_for_file(self, prompt):
        self.asked.append(prompt)
        return self._files.pop(0) if self._files else ""

    def show_status(self, text):
        self.statuses.append(text)

    def show_error(self, message):
        self.errors.append(str(message))

    def close(self):
        self.closed = True


def run_controller(events, files=(), initial_file=None):
    view = FakeDesView(list(events) + [sg.WIN_CLOSED], files)
    controller = DesController(view=view)
    controller.run(initial_file)
    return controller, view


def sample_chart():
    rows = [{"Period": str(2010 + i // 2), "Count": str(50 + i),
             "Type": "Births" if i % 2 == 0 else "Deaths"}
            for i in range(10)]
    source = DataSource("s.csv", ["Period", "Count", "Type"], rows)
    return source.chart_data("Period", "Count", "Type")


# chart drawing tests

def test_tick_labels_do_not_exceed_the_maximum_limit():
    labels = [f"L{i}" for i in range(60)]
    positions, shown = visible_ticks(labels, -1, 60, max_ticks=10)
    assert 0 < len(positions) <= 10, positions
    assert shown == [labels[i] for i in positions], "labels out of step"


def test_tick_labels_only_show_values_inside_the_view():
    labels = [f"L{i}" for i in range(20)]
    positions, shown = visible_ticks(labels, 5.5, 8.5)
    assert positions == [6, 7, 8], positions
    assert shown == ["L6", "L7", "L8"], shown


def test_no_tick_labels_are_shown_between_data_points():
    assert visible_ticks(["a", "b", "c", "d", "e"], 3.2, 3.8) == ([], [])


def test_chart_displays_all_data_series_correctly():
    chart = sample_chart()
    view = ViewWindow.fitting(*chart.x_extent(), *chart.y_extent())
    figure = Figure()
    draw_chart(figure, chart, view, title="s.csv")
    axes = figure.axes[0]
    assert len(axes.lines) == 2, f"{len(axes.lines)} lines drawn"
    assert approx(axes.get_xlim()[0], view.x_min)
    assert approx(axes.get_xlim()[1], view.x_max)
    assert approx(axes.get_ylim()[0], view.y_min)
    assert approx(axes.get_ylim()[1], view.y_max)
    assert axes.get_xlabel() == "Period" and axes.get_ylabel() == "Count"
    assert axes.get_title() == "s.csv"
    assert axes.get_legend() is not None, "legend missing for two series"


def test_redrawing_chart_does_not_create_extra_charts():
    chart = sample_chart()
    view = ViewWindow.fitting(*chart.x_extent(), *chart.y_extent())
    figure = Figure()
    draw_chart(figure, chart, view)
    draw_chart(figure, chart, view)
    assert len(figure.axes) == 1, "second draw stacked a new set of axes"


def test_chart_can_be_drawn_when_zoomed_in_close():
    chart = sample_chart()
    view = ViewWindow.fitting(*chart.x_extent(), *chart.y_extent())
    figure = Figure()
    canvas = FigureCanvasAgg(figure)
    draw_chart(figure, chart, view)
    canvas.draw()
    view.x_min, view.x_max = 3.2, 3.8
    draw_chart(figure, chart, view)
    canvas.draw()


def test_placeholder_displays_the_correct_message():
    for message in ("No data loaded", "Loading data..."):
        figure = Figure()
        FigureCanvasAgg(figure)
        draw_placeholder(figure, message)
        texts = [t.get_text() for t in figure.axes[0].texts]
        assert message in texts, f"{message!r} not in {texts}"
        figure.canvas.draw()


# DES controller tests

def test_controller_does_not_open_the_gui_when_imported():
    assert "view.des_view" not in sys.modules, \
        "importing the controller pulled in the GUI window class"


def test_controller_shows_empty_chart_at_start_and_closes():
    controller, view = run_controller([])
    assert view.draws == [(False, None)], view.draws
    assert view.closed, "window not closed when the user closed it"


def test_controller_loads_initial_file_before_showing_chart():
    path = write_temp_csv(FIRST, name="first.csv")
    controller, view = run_controller([], initial_file=path)
    assert controller.explorer.has_data()
    assert view.draws[0][0] is True, view.draws
    assert view.statuses == ["Loaded first.csv."], view.statuses


def test_controller_shows_error_for_invalid_initial_file():
    path = write_temp_csv(NO_NUMBERS, name="bad.csv")
    controller, view = run_controller([], initial_file=path)
    assert len(view.errors) == 1 and "no numeric column" in view.errors[0]
    assert view.draws == [(False, None)], view.draws
    assert view.closed


def test_controller_shows_error_when_initial_file_is_missing():
    controller, view = run_controller([], initial_file="nowhere/none.csv")
    assert len(view.errors) == 1 and "File not found" in view.errors[0]
    assert view.draws == [(False, None)], view.draws


def test_controller_loads_a_new_file_when_source_is_changed():
    path = write_temp_csv(FIRST, name="first.csv")
    controller, view = run_controller(["-CHANGE_SOURCE-"], files=[path])
    assert controller.explorer.source.name == "first.csv"
    assert view.errors == [] and view.statuses == ["Loaded first.csv."]
    assert view.draws[-1][0] is True


def test_canceling_file_selection_does_not_change_data():
    # cancelling when no data is loaded
    controller, view = run_controller(["-CHANGE_SOURCE-"], files=[""])
    assert not controller.explorer.has_data()
    assert view.errors == [] and view.statuses == [], view.errors

    # cancelling both dialogs when data is already loaded
    path = write_temp_csv(FIRST, name="first.csv")
    controller, view = run_controller(
        ["-CHANGE_SOURCE-", "-APPEND-", "-CHANGE_SOURCE-"],
        files=[path, "", ""])
    assert controller.explorer.source.name == "first.csv"
    assert len(controller.explorer.source.rows) == 4
    assert view.errors == [], view.errors
    assert view.statuses == ["Loaded first.csv."], view.statuses


def test_invalid_file_does_not_replace_existing_data():
    good = write_temp_csv(FIRST, name="good.csv")
    bad = write_temp_csv(NO_NUMBERS, name="bad.csv")
    controller, view = run_controller(
        ["-CHANGE_SOURCE-", "-CHANGE_SOURCE-"], files=[good, bad])
    assert controller.explorer.source.name == "good.csv"
    assert len(view.errors) == 1 and "no numeric column" in view.errors[0]


def test_appending_file_adds_rows_and_shows_confirmation():
    first = write_temp_csv(FIRST, name="first.csv")
    second = write_temp_csv(SECOND, name="second.csv")
    controller, view = run_controller(
        ["-CHANGE_SOURCE-", "-APPEND-"], files=[first, second])
    assert len(controller.explorer.source.rows) == 6
    assert view.statuses[-1] == "Added 2 rows from second.csv.", \
        view.statuses
    assert view.errors == []


def test_appending_file_with_different_columns_is_rejected():
    first = write_temp_csv(FIRST, name="first.csv")
    wrong = write_temp_csv(WRONG_COLUMNS, name="wrong.csv")
    controller, view = run_controller(
        ["-CHANGE_SOURCE-", "-APPEND-"], files=[first, wrong])
    assert len(controller.explorer.source.rows) == 4
    assert len(view.errors) == 1 and "does not match" in view.errors[0]


def test_view_buttons_show_error_when_no_data_is_loaded():
    controller, view = run_controller(
        ["-ZOOM_IN-", "-ZOOM_OUT-", "-PAN_LEFT-", "-PAN_RIGHT-", "-RESET-"])
    assert view.errors == ["Load a data source first."] * 5, view.errors


def test_append_button_does_not_open_file_selection_without_data():
    path = write_temp_csv(FIRST, name="first.csv")
    controller, view = run_controller(["-APPEND-"], files=[path])
    assert view.errors == ["Load a data source first."], view.errors
    assert view.asked == [], f"dialog opened anyway: {view.asked}"
    assert not controller.explorer.has_data()


def test_zoom_pan_and_reset_buttons_update_the_chart():
    path = write_temp_csv(FIRST, name="first.csv")
    controller, view = run_controller(
        ["-CHANGE_SOURCE-", "-ZOOM_IN-", "-PAN_RIGHT-"], files=[path])
    assert len(view.draws) == 4, view.draws
    assert not controller.explorer.view.is_full_view()
    zoomed = view.draws[2][1]
    panned = view.draws[3][1]
    assert panned[0] > zoomed[0], "pan right did not move the view right"

    controller, view = run_controller(
        ["-CHANGE_SOURCE-", "-ZOOM_IN-", "-PAN_LEFT-", "-RESET-"],
        files=[path])
    assert controller.explorer.view.is_full_view()
    assert view.errors == []


def test_pan_left_moves_the_chart_to_the_left():
    path = write_temp_csv(FIRST, name="first.csv")
    controller, view = run_controller(
        ["-CHANGE_SOURCE-", "-ZOOM_IN-", "-ZOOM_IN-", "-PAN_RIGHT-",
         "-PAN_LEFT-"], files=[path])
    before_pan_left = view.draws[-2][1]
    after_pan_left = view.draws[-1][1]
    assert after_pan_left[0] < before_pan_left[0], view.draws[-2:]


def test_unknown_actions_are_ignored():
    controller, view = run_controller(["-SOMETHING_ELSE-", "__TIMEOUT__"])
    assert view.draws == [(False, None)], "an unknown event caused a redraw"
    assert view.errors == []


ALL_TESTS = [
    test_tick_labels_do_not_exceed_the_maximum_limit,
    test_tick_labels_only_show_values_inside_the_view,
    test_no_tick_labels_are_shown_between_data_points,
    test_chart_displays_all_data_series_correctly,
    test_redrawing_chart_does_not_create_extra_charts,
    test_chart_can_be_drawn_when_zoomed_in_close,
    test_placeholder_displays_the_correct_message,
    test_controller_does_not_open_the_gui_when_imported,
    test_controller_shows_empty_chart_at_start_and_closes,
    test_controller_loads_initial_file_before_showing_chart,
    test_controller_shows_error_for_invalid_initial_file,
    test_controller_shows_error_when_initial_file_is_missing,
    test_controller_loads_a_new_file_when_source_is_changed,
    test_canceling_file_selection_does_not_change_data,
    test_invalid_file_does_not_replace_existing_data,
    test_appending_file_adds_rows_and_shows_confirmation,
    test_appending_file_with_different_columns_is_rejected,
    test_view_buttons_show_error_when_no_data_is_loaded,
    test_append_button_does_not_open_file_selection_without_data,
    test_zoom_pan_and_reset_buttons_update_the_chart,
    test_pan_left_moves_the_chart_to_the_left,
    test_unknown_actions_are_ignored,
]
