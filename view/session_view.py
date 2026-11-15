import FreeSimpleGUI as sg

HEADINGS = ["Name", "Owner", "Visibility"]


class SessionView:
    """session management window. It shows what it is told and reports button presses"""

    def __init__(self, username):
        sg.theme("DarkBlue")

        table = sg.Table(
            values=[], headings=HEADINGS, key="-TABLE-",
            auto_size_columns=False, col_widths=[30, 20, 10], num_rows=12,
            select_mode=sg.TABLE_SELECT_MODE_BROWSE, enable_events=True,
            justification="left", expand_x=True)

        layout = [
            [sg.Text(f"Logged in as {username}", font="Any 11 bold")],
            [sg.Text("Public sessions, plus your own private ones")],
            [table],
            [sg.Button("Join", key="-JOIN-", disabled=True),
             sg.Button("Delete", key="-DELETE-", disabled=True),
             sg.Button("Refresh", key="-REFRESH-"),
             sg.Push(),
             sg.Button("Logout", key="-LOGOUT-")],
            [sg.HorizontalSeparator()],
            [sg.Text("New session"),
             sg.Input(key="-NEW_NAME-", size=(30, 1)),
             sg.Checkbox("Private", key="-PRIVATE-"),
             sg.Button("Create", key="-CREATE-", bind_return_key=True)],
            [sg.Text("", key="-STATUS-", size=(70, 1))],
        ]
        self.window = sg.Window("Sessions", layout, finalize=True)

    def read(self, timeout=None):
        return self.window.read(timeout=timeout)

    def show_sessions(self, rows):
        self.window["-TABLE-"].update(values=rows)

    def set_buttons(self, join_enabled, delete_enabled):
        self.window["-JOIN-"].update(disabled=not join_enabled)
        self.window["-DELETE-"].update(disabled=not delete_enabled)

    def clear_new_name(self):
        self.window["-NEW_NAME-"].update("")

    def confirm_delete(self, name):
        answer = sg.popup_yes_no(
            f"Delete the session '{name}'?\nThis cannot be undone.",
            title="Delete session")
        return answer == "Yes"

    def show_status(self, text):
        self.window["-STATUS-"].update(text)

    def show_error(self, message):
        sg.popup_error(message)

    def close(self):
        self.window.close()
