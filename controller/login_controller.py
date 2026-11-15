from view.login_view import LoginView
from controller.register_controller import RegisterController
from data.database_manager import DatabaseError
from data.user_repository import AuthError
import FreeSimpleGUI as sg


class LoginController:
    def __init__(self, user_repository, view=None):
        self.user_repository = user_repository
        self.view = view if view is not None else LoginView()

    def run(self):
        while True:
            event, values = self.view.read()

            if event in (sg.WIN_CLOSED, "Cancel"):
                self.view.close()
                return

            if event == "Register":
                self.view.hide()
                RegisterController(self.user_repository).run()
                self.view.un_hide()

            if event == "Login":
                try:
                    user = self.user_repository.login(
                        values["-USERNAME-"], values["-PASSWORD-"])
                except AuthError as e:
                    self.view.show_error(str(e))
                    continue
                except DatabaseError:
                    self.view.show_error(
                        "Could not reach the database. Please try again later.")
                    continue

                self.view.show_message("Login successful")
                self.view.close()
                return user
