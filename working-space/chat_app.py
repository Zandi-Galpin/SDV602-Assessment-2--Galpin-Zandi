import FreeSimpleGUI as fsg
from chat_view import ChatView
from chat_message import ChatMessage
from login_view import LoginView
from user import User
import config


def login():
    """Runs login screen loop. Returns authenticated User if
    successful, or returns None if window was closed without logging in."""
    view = LoginView()

    while True:
        event, values = view.read()

        if event in (None, "Exit"):
            view.close()
            return None

        if event == "Login":
            username = values["-USERNAME-"].strip()
            password = values["-PASSWORD-"]

            if not username or not password:
                view.show_error("Please enter both a username and password.")
                continue

            result = User.authenticate(username, password)

            if result.success:
                view.close()
                return result.user

            view.show_error(result.message)


def format_messages(messages=[]):
    if messages:
        output = ""
        for message in messages:
            output += f"{message.username}: {message.text}\n"
        return output


def run():
    current_user = login()

    if current_user is None:
        return

    view = ChatView()

    messages = ChatMessage.all()
    view.update_messages(format_messages(messages))

    while True:
        event, values = view.read(timeout=config.POLL_RATE)

        if event == fsg.WIN_CLOSED:
            break

        if event == "__TIMEOUT__":
            messages = ChatMessage.all()
            view.update_messages(format_messages(messages))

        if event == "Send":
            text = values["-CHAT-"]

            if text:
                ChatMessage(current_user.username, text).save()
                view.clear_input()
                messages = ChatMessage.all()
                view.update_messages(format_messages(messages))

    view.close()


if __name__ == "__main__":
    run()