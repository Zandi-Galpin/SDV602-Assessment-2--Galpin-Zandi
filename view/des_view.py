import FreeSimpleGUI as sg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from view.chart_drawing import draw_chart, draw_placeholder
from view.chat_view import format_messages

CHART_SIZE = (720, 440)
DPI = 100

class DesView:
    """data Explorer Screen window. the chart, view buttons, a status
    line and the description. It shows what it is told and reports button
    presses. """

    def __init__(self, title="Data Explorer - Local", remote=False):
        sg.theme("DarkBlue")

        view_buttons = [
            sg.Button("Zoom In", key="-ZOOM_IN-"),
            sg.Button("Zoom Out", key="-ZOOM_OUT-"),
            sg.Text("  Pan:"),
            sg.Button("\u2190", key="-PAN_LEFT-", size=(3, 1)),
            sg.Button("\u2192", key="-PAN_RIGHT-", size=(3, 1)),
            sg.Button("Reset View", key="-RESET-"),
        ]
        if remote:
            data_buttons = [sg.Button("Upload Data", key="-UPLOAD-"), sg.Button("Append Data", key="-APPEND-")]
        else:
            data_buttons = [sg.Button("Change Source", key="-CHANGE_SOURCE-"), sg.Button("Append Data", key="-APPEND-")]

        chart_rows = [
            [sg.Canvas(key="-CANVAS-", size=CHART_SIZE)],
            view_buttons + [sg.Push()] + data_buttons,
            [sg.Text("", key="-STATUS-", size=(90, 1))],
            [sg.Text("Description", font="Any 10 bold")],
            [sg.Multiline("", key="-DESCRIPTION-", size=(90, 4), disabled=True, no_scrollbar=True)],
        ]
        if remote:
            chat_rows = [
                [sg.Text("Live chat", font="Any 10 bold")],
                [sg.Multiline("", key="-CHAT_LOG-", size=(36, 22), disabled=True, autoscroll=True)],
                [sg.Input(key="-CHAT_INPUT-", size=(28, 1)), sg.Button("Send", key="-CHAT_SEND-", bind_return_key=True)],
                [sg.Text("", key="-CHAT_STATUS-", size=(40, 1), text_color="orange")],
            ]
            layout = [[sg.Column(chart_rows), sg.VSeparator(), sg.Column(chat_rows, vertical_alignment="top")]]
        else:
            layout = chart_rows
        self.window = sg.Window(title, layout, finalize=True)

        self.figure = Figure(figsize=(CHART_SIZE[0] / DPI, CHART_SIZE[1] / DPI), dpi=DPI)
        self.canvas = FigureCanvasTkAgg(self.figure, self.window["-CANVAS-"].TKCanvas)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=1)

    def read(self, timeout=None):
        return self.window.read(timeout=timeout)

    def post(self, key, value):
        """Send an event to this window from another thread"""
        self.window.write_event_value(key, value)

    def draw(self, explorer, loading=False, message=None):
        """Redraw the chart and description from an explorer. Shows the
        placeholder chart while there is no data."""
        if explorer.has_data():
            draw_chart(self.figure, explorer.chart, explorer.view, title=" + ".join(explorer.source.part_names))
        else:
            text = message or ("Loading data..." if loading else "No data loaded")
            draw_placeholder(self.figure, text)
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

    def update_chat(self, messages):
        self.window["-CHAT_LOG-"].update(format_messages(messages))

    def clear_chat_input(self):
        self.window["-CHAT_INPUT-"].update("")

    def show_chat_status(self, text):
        self.window["-CHAT_STATUS-"].update(text)

    def show_error(self, message):
        sg.popup_error(message)

    def close(self):
        self.window.close()