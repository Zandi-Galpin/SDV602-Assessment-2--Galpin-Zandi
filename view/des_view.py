import FreeSimpleGUI as sg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from view.chart_drawing import draw_chart, draw_placeholder

CHART_SIZE = (720, 440)
DPI = 100

class DesView:
    """data Explorer Screen window. the chart, view buttons, a status
    line and the description. It shows what it is told and reports button
    presses. """

    def __init__(self, title="Data Explorer - Local"):
        sg.theme("DarkBlue")

        view_buttons = [
            sg.Button("Zoom In", key="-ZOOM_IN-"),
            sg.Button("Zoom Out", key="-ZOOM_OUT-"),
            sg.Text("  Pan:"),
            sg.Button("\u2190", key="-PAN_LEFT-", size=(3, 1)),
            sg.Button("\u2192", key="-PAN_RIGHT-", size=(3, 1)),
            sg.Button("Reset View", key="-RESET-"),
        ]
        data_buttons = [
            sg.Button("Change Source", key="-CHANGE_SOURCE-"),
            sg.Button("Append Data", key="-APPEND-"),
        ]

        layout = [
            [sg.Canvas(key="-CANVAS-", size=CHART_SIZE)],
            view_buttons + [sg.Push()] + data_buttons,
            [sg.Text("", key="-STATUS-", size=(90, 1))],
            [sg.Text("Description", font="Any 10 bold")],
            [sg.Multiline("", key="-DESCRIPTION-", size=(90, 4),
                          disabled=True, no_scrollbar=True)],
        ]
        self.window = sg.Window(title, layout, finalize=True)

        self.figure = Figure(figsize=(CHART_SIZE[0] / DPI,
                                      CHART_SIZE[1] / DPI), dpi=DPI)
        self.canvas = FigureCanvasTkAgg(self.figure, self.window["-CANVAS-"].TKCanvas)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=1)

    def read(self, timeout=None):
        return self.window.read(timeout=timeout)

    def draw(self, explorer, loading=False):
        """Redraw the chart and description from an explorer. Shows the
        placeholder chart while there is no data."""
        if explorer.has_data():
            draw_chart(self.figure, explorer.chart, explorer.view, title=" + ".join(explorer.source.part_names))
        else:
            message = "Loading data..." if loading else "No data loaded"
            draw_placeholder(self.figure, message)
        self.canvas.draw()
        self.window["-DESCRIPTION-"].update(explorer.describe())

    def ask_for_file(self, prompt):
        """Ask the user to pick a csv file. Returns '' if they cancel."""
        path = sg.popup_get_file(
            prompt, no_window=True,
            file_types=(("CSV files", "*.csv"), ("All files", "*.*")))
        return path or ""

    def show_status(self, text):
        self.window["-STATUS-"].update(text)

    def show_error(self, message):
        sg.popup_error(message)

    def close(self):
        self.window.close()