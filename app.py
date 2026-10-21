from data.user_repository import UserRepository
from data.message_repository import MessageRepository

from controller.login_controller import LoginController
from controller.chat_controller import ChatController
import FreeSimpleGUI as sg
from data.database_manager import DatabaseError

class App:
    def __init__(self):
        self.user_repository = UserRepository()
        self.message_repository = MessageRepository()

    def run(self):
        user = LoginController(self.user_repository).run()

        if user:
            ChatController(user.name, self.message_repository).run()

if __name__ == "__main__":
    try:
        App().run()
    except DatabaseError as e:
        sg.popup_error(f"{e}. Check the database is running and try again.")