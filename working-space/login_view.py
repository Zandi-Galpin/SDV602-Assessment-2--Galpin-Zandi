import FreeSimpleGUI as sg


class LoginView:

    def __init__(self):
        sg.theme("DarkBlue")

        self.layout = [
            [sg.Text("Username")],
            [sg.Input(key="-USERNAME-")],
            [sg.Text("Password")],
            [sg.Input(key="-PASSWORD-", password_char="*")],
            [sg.Text("", key="-ERROR-", text_color="red")],
            [sg.Button("Login", bind_return_key=True)],
        ]

        self.window = sg.Window("Login", self.layout, finalize=True)

    def read(self, timeout=None):
        return self.window.read(timeout=timeout)

    def show_error(self, message):
        self.window["-ERROR-"].update(message)

    def close(self):
        self.window.close()