import FreeSimpleGUI as sg

from view.login_view import LoginView
from view.register_view import RegisterView
from user import User


def register():
    view = RegisterView()

    while True:
        event, values = view.read()

        if event in (sg.WIN_CLOSED, "Cancel", "Login"):
            view.close()
            return

        if event == "Register":
            try:
                User(values["-USERNAME-"], values["-PASSWORD-"]).save()
                view.show_message("Registration successful")
                view.close()
                return
            except Exception as e:
                view.show_error(e)


def login():



if __name__ == "__main__":
    login()