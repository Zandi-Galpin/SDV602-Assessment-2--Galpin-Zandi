from view.register_view import RegisterView
from data.database_manager import DatabaseError
from data.user_repository import AuthError
import FreeSimpleGUI as sg


class RegisterController:
    def __init__(self, user_repository, view=None):
        self.user_repository = user_repository
        self.view = view if view is not None else RegisterView()

    def run(self):
        while True:
            event, values = self.view.read()

            if event in (sg.WIN_CLOSED, "Cancel", "Login"):
                self.view.close()
                return

            if event == "Register":
                if values["-PASSWORD-"] != values["-CONFIRM_PASSWORD-"]:
                    self.view.show_error("Passwords do not match.")
                    continue

                try:
                    self.user_repository.create_user(
                        values["-USERNAME-"], values["-PASSWORD-"])
                except AuthError as e:
                    self.view.show_error(str(e))
                    continue
                except DatabaseError:
                    self.view.show_error(
                        "Could not reach the database. Please try again later.")
                    continue

                self.view.show_message("Registration successful")
                self.view.close()
                return
