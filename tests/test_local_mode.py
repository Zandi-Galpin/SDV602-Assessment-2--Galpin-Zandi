"""Headless tests for local mode, including csv loading, data source, zoom/pan and
the explorer. No windows, files only in temporary directories.
"""
import os
import tempfile

from data.csv_loader import load_csv
from model.data_source import DataError, DataSource
from model.explorer import Explorer
from model.view_window import ViewWindow

#helpers

def approx(a, b):
    return abs(a - b) < 1e-9

def sample_source(name="sample.csv"):
    rows = [
        {"Period": "2011", "Count": "50", "Type": "Births"},
        {"Period": "2010", "Count": "60", "Type": "Births"},
        {"Period": "2010", "Count": "40", "Type": "Deaths"},
        {"Period": "2011", "Count": "45", "Type": "Deaths"},
    ]
    return DataSource(name, ["Period", "Count", "Type"], rows)

def write_temp_csv(content, encoding="utf-8", name="data.csv"):
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, name)
    mode = "wb" if isinstance(content, bytes) else "w"
    kwargs = {} if mode == "wb" else {"encoding": encoding, "newline": ""}
    with open(path, mode, **kwargs) as file:
        file.write(content)
    return path

def expect_data_error(func, fragment):
    try:
        func()
    except DataError as e:
        assert fragment in str(e), f"expected '{fragment}' in '{e}'"
        return
    raise AssertionError(f"no DataError raised (expected '{fragment}')")


#CSV loader

def test_load_csv_reads_rows_and_columns():
    path = write_temp_csv("Period,Count\n2010,5\n2011,6\n")
    source = load_csv(path)
    assert source.columns == ["Period", "Count"], source.columns
    assert len(source.rows) == 2
    assert source.rows[1] == {"Period": "2011", "Count": "6"}, source.rows

def test_load_csv_handles_bom_and_spaces():
    #bom (byte order mark) invisible character at the start of a text file
    path = write_temp_csv("Period , Count\n 2010 , 5 \n", encoding="utf-8-sig")
    source = load_csv(path)
    assert source.columns == ["Period", "Count"], source.columns
    assert source.rows[0] == {"Period": "2010", "Count": "5"}, source.rows

def test_load_csv_short_rows_become_blank():
    path = write_temp_csv("Period,Count\n2010\n")
    assert load_csv(path).rows[0] == {"Period": "2010", "Count": ""}

def test_load_csv_missing_file():
    expect_data_error(lambda: load_csv("skibidi_not_real_file.csv"), "File not found")

def test_load_csv_empty_file():
    expect_data_error(lambda: load_csv(write_temp_csv("")), "is empty")

def test_load_csv_header_only():
    path = write_temp_csv("Period,Count\n")
    expect_data_error(lambda: load_csv(path), "no data rows")

def test_load_csv_binary_file():
    path = write_temp_csv(b"\x80\x81\x82\n\x83\x84", name="image.csv")
    expect_data_error(lambda: load_csv(path), "not a readable")

#DataSource 

def test_guess_columns_for_expected_data():
    assert sample_source().guess_chart_columns() == ("Period", "Count", "Type")

def test_guess_columns_without_named_columns():
    source = DataSource("s", ["a", "b", "c"], [{"a": "1", "b": "2", "c": "3"}, {"a": "4", "b": "5", "c": "6"}])
    assert source.guess_chart_columns() == ("a", "c", None)

def test_that_guess_columns_needs_a_numeric_column():
    source = DataSource("s", ["Period", "Name"], [{"Period": "2010", "Name": "a"}])
    expect_data_error(source.guess_chart_columns, "no numeric column")

def test_that_numeric_column_works_for_a_few_markers():
    rows = [{"Count": str(i)} for i in range(9)] + [{"Count": ".."}]
    assert DataSource("s", ["Count"], rows).is_numeric_column("Count")

def test_that_chart_data_groups_the_series_and_orders_the_labels():
    chart = sample_source().chart_data("Period", "Count", "Type")
    assert chart.x_labels == ["2010", "2011"], chart.x_labels
    assert chart.series["Births"] == [(0, 60.0), (1, 50.0)], chart.series
    assert chart.series["Deaths"] == [(0, 40.0), (1, 45.0)], chart.series

def test_that_chart_data_sorts_number_labels_by_number():
    rows = [{"P": "100", "V": "1"}, {"P": "9", "V": "2"}, {"P": "10", "V": "3"}]
    chart = DataSource("s", ["P", "V"], rows).chart_data("P", "V")
    assert chart.x_labels == ["9", "10", "100"], chart.x_labels

def test_that_chart_data_skips_unusable_rows():
    rows = [{"P": "a", "V": "1"}, {"P": "b", "V": ""},
            {"P": "c", "V": ".."}, {"P": "d", "V": "nan"},
            {"P": "e", "V": "inf"}, {"P": "", "V": "5"}]
    chart = DataSource("s", ["P", "V"], rows).chart_data("P", "V")
    assert chart.x_labels == ["a"], chart.x_labels
    assert chart.skipped == 5, chart.skipped

def test_chart_data_unknown_column():
    expect_data_error(lambda: sample_source().chart_data("Nope", "Count"), "'Nope'")

def test_chart_data_with_no_numbers():
    source = DataSource("s", ["P", "V"], [{"P": "a", "V": "x"}])
    expect_data_error(lambda: source.chart_data("P", "V"), "no numbers")

def test_append_adds_rows():
    source = sample_source("a.csv")
    added = source.append(sample_source("b.csv"))
    assert added == 4 and len(source.rows) == 8
    assert source.part_names == ["a.csv", "b.csv"], source.part_names

def test_append_rejects_mismatched_columns_and_changes_nothing():
    source = sample_source()
    other = DataSource("o.csv", ["Period", "Other"],
                       [{"Period": "2012", "Other": "1"}])
    expect_data_error(lambda: source.append(other), "missing Count, Type")
    assert len(source.rows) == 4, "rows changed after a failed append"
    assert source.part_names == ["sample.csv"], source.part_names

def test_append_rejects_empty_source():
    empty = DataSource("e.csv", ["Period", "Count", "Type"], [])
    expect_data_error(lambda: sample_source().append(empty), "no rows")

def test_that_describe_works_to_describe_properly():
    source = sample_source()
    text = source.describe(source.chart_data("Period", "Count", "Type"))
    for fragment in ("sample.csv", "4 rows", "Count by Period", "Births, Deaths", "2010 to 2011", "40 to 60"):
        assert fragment in text, f"'{fragment}' missing from: {text}"

#ViewWindow

def test_that_view_fitting_pads_the_data():
    view = ViewWindow.fitting(0, 10, 0, 100)
    assert approx(view.x_min, -0.5) and approx(view.x_max, 10.5)
    assert approx(view.y_min, -5) and approx(view.y_max, 105)
    assert view.is_full_view()

def test_for_view_that_single_value_is_widened():
    view = ViewWindow.fitting(0, 0, 5, 5)
    assert view.x_max > view.x_min and view.y_max > view.y_min

def test_that_view_rejects_empty_limits_and_bad_zoom():
    try:
        ViewWindow(1, 1, 0, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("empty limits accepted")
    for bad in (0, -2):
        try:
            ViewWindow.fitting(0, 1, 0, 1).zoom(bad)
        except ValueError:
            continue
        raise AssertionError(f"zoom factor {bad} accepted")

def test_for_view_that_zoom_in_halves_the_span_around_centre():
    view = ViewWindow(0, 100, 0, 100)
    view.zoom(2)
    assert approx(view.x_min, 25) and approx(view.x_max, 75), view.limits()
    assert approx(view.y_min, 25) and approx(view.y_max, 75), view.limits()

def test_for_view_that_zoom_out_never_exceeds_the_full_view():
    view = ViewWindow(0, 100, 0, 100)
    view.zoom(4)
    view.zoom(0.001)
    assert view.limits() == (0, 100, 0, 100), view.limits()

def test_for_view_that_zoom_in_stops_at_minimum():
    view = ViewWindow(0, 100, 0, 100)
    for _ in range(50):
        view.zoom(2)
    assert approx(view.x_max - view.x_min, 100 * ViewWindow.MIN_SPAN)

def test_view_that_pan_moves_and_stops_at_edge():
    view = ViewWindow(0, 100, 0, 100)
    view.zoom(2) #now 25 75
    view.pan(0.5)#50 wide, move 25 right
    assert approx(view.x_min, 50) and approx(view.x_max, 100), view.limits()
    view.pan(0.5) #already at the edge
    assert approx(view.x_max, 100), view.limits()
    view.pan(dy_fraction=-10)
    assert approx(view.y_min, 0), view.limits()

def test_for_view_that_pan_does_nothing_when_fully_zoomed_out():
    view = ViewWindow(0, 100, 0, 100)
    view.pan(0.5, 0.5)
    assert view.is_full_view(), view.limits()

def test_view_reset():
    view = ViewWindow(0, 100, 0, 100)
    view.zoom(3)
    view.pan(0.3)
    view.reset()
    assert view.is_full_view()

#Explorer

def test_that_set_source_for_explorer_builds_chart_and_description():
    explorer = Explorer()
    assert not explorer.has_data()
    assert explorer.describe() == "No data loaded."
    explorer.set_source(sample_source())
    assert explorer.has_data() and explorer.view.is_full_view()
    assert "Count by Period" in explorer.describe(), explorer.describe()

def test_that_explorer_actions_before_loading_are_refused():
    explorer = Explorer()
    for action in (explorer.zoom_in, explorer.zoom_out, explorer.pan, explorer.reset_view, lambda: explorer.append_source(sample_source())):
        expect_data_error(action, "Load a data source first")

def test_that_explorer_zoom_and_pan_changes_the_view():
    explorer = Explorer()
    explorer.set_source(sample_source())
    explorer.zoom_in()
    assert not explorer.view.is_full_view()
    explorer.zoom_out()
    assert explorer.view.is_full_view(), explorer.view.limits()
    explorer.zoom_in()
    explorer.zoom_in()
    before = explorer.view.limits()
    explorer.pan(0.1, 0.1)
    assert explorer.view.limits() != before

def test_explorer_change_source_replaces_data_and_resets_view():
    explorer = Explorer()
    explorer.set_source(sample_source("first.csv"))
    explorer.zoom_in()
    other = DataSource("second.csv", ["Year", "Value"], [{"Year": "1", "Value": "7"}, {"Year": "2", "Value": "9"}])
    explorer.set_source(other)
    assert explorer.source.name == "second.csv"
    assert explorer.chart.y_key == "Value"
    assert explorer.view.is_full_view()

def test_explorer_failed_change_keeps_old_data():
    explorer = Explorer()
    explorer.set_source(sample_source())
    bad = DataSource("bad.csv", ["Name"], [{"Name": "x"}])
    expect_data_error(lambda: explorer.set_source(bad), "no numeric column")
    assert explorer.source.name == "sample.csv"
    assert explorer.chart.y_key == "Count"

def test_that_append_for_explorer_extends_chart_and_resets_view():
    explorer = Explorer()
    explorer.set_source(sample_source("a.csv"))
    explorer.zoom_in()
    later = DataSource("b.csv", ["Period", "Count", "Type"], [{"Period": "2012", "Count": "80", "Type": "Births"}])
    assert explorer.append_source(later) == 1
    assert explorer.chart.x_labels == ["2010", "2011", "2012"]
    assert explorer.view.is_full_view()
    assert "a.csv + b.csv" in explorer.describe(), explorer.describe()

def test_that_an_explorer_failed_append_keeps_same_state():
    explorer = Explorer()
    explorer.set_source(sample_source())
    explorer.zoom_in()
    limits = explorer.view.limits()
    bad = DataSource("bad.csv", ["Period", "Other"], [{"Period": "2012", "Other": "1"}])
    expect_data_error(lambda: explorer.append_source(bad), "does not match")
    assert len(explorer.source.rows) == 4
    assert explorer.view.limits() == limits, "view changed on failed append"

ALL_TESTS = [
    test_load_csv_reads_rows_and_columns,
    test_load_csv_handles_bom_and_spaces,
    test_load_csv_short_rows_become_blank,
    test_load_csv_missing_file,
    test_load_csv_empty_file,
    test_load_csv_header_only,
    test_load_csv_binary_file,
    test_guess_columns_for_expected_data,
    test_guess_columns_without_named_columns,
    test_that_guess_columns_needs_a_numeric_column,
    test_that_numeric_column_works_for_a_few_markers,
    test_that_chart_data_groups_the_series_and_orders_the_labels,
    test_that_chart_data_sorts_number_labels_by_number,
    test_that_chart_data_skips_unusable_rows,
    test_chart_data_unknown_column,
    test_chart_data_with_no_numbers,
    test_append_adds_rows,
    test_append_rejects_mismatched_columns_and_changes_nothing,
    test_append_rejects_empty_source,
    test_that_describe_works_to_describe_properly,
    test_that_view_fitting_pads_the_data,
    test_for_view_that_single_value_is_widened,
    test_that_view_rejects_empty_limits_and_bad_zoom,
    test_for_view_that_zoom_in_halves_the_span_around_centre,
    test_for_view_that_zoom_out_never_exceeds_the_full_view,
    test_for_view_that_zoom_in_stops_at_minimum,
    test_view_that_pan_moves_and_stops_at_edge,
    test_for_view_that_pan_does_nothing_when_fully_zoomed_out,
    test_view_reset,
    test_that_set_source_for_explorer_builds_chart_and_description,
    test_that_explorer_actions_before_loading_are_refused,
    test_that_explorer_zoom_and_pan_changes_the_view,
    test_explorer_change_source_replaces_data_and_resets_view,
    test_explorer_failed_change_keeps_old_data,
    test_that_append_for_explorer_extends_chart_and_resets_view,
    test_that_an_explorer_failed_append_keeps_same_state,
]