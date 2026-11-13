import FreeSimpleGUI as sg


def format_messages(messages):
    """The chat log as text, a name: text line for each message."""
    return "".join(f"{m.username}: {m.text}\n" for m in messages)


class ChatView:

    def __init__(self, title="Live Chat"):
        sg.theme("DarkBlue")

        self.layout = [
            [sg.Multiline(size=(50, 20), disabled=True, autoscroll=True, key='-OUTPUT-')],
            [sg.Input(size=(40, 5), key='-CHAT-', do_not_clear=True)],
            [sg.Button('Send', bind_return_key=True)],
            [sg.Text("", key="-STATUS-", size=(50, 1), text_color="orange")],
        ]

        self.window = sg.Window(title, self.layout, finalize=True)

    def update_messages(self, messages):
        self.window['-OUTPUT-'].update(format_messages(messages))

    def clear_input(self):
        self.window['-CHAT-'].update('')

    def read(self, timeout=None):
        return self.window.read(timeout=timeout)

    def close(self):
        self.window.close()

    def show_status(self, text):
        self.window['-STATUS-'].update(text)

    def show_error(self, message):
        sg.popup_error(message)

    def show_message(self, message):
        sg.popup(message)