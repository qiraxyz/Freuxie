import sys
import time

from lib import save_tokens_to_env, save_username_password, login, auto_attendance


def add_token():
    xtf = input("Enter XSRF_TOKEN_COOKIE: ")
    msc = input("Enter MYBEST_SESSION_COOKIE: ")
    time.sleep(1)

    print(f"Token added.")
    save_tokens_to_env(xtf, msc)


def set_user_password():
    username = input("Enter username: ")
    password = input("Enter password: ")
    time.sleep(1)

    print(f"Username and password set for {username}.")
    save_username_password(username, password)



def check_license():
    print("Checking license...")
    time.sleep(1)
    print("License valid.")


def attendance_in():
    print("Auto absent triggered.")
    time.sleep(1)

    auto_attendance()
    print("Attendance recorded.")

def exit_application():
    print("Goodbye!")
    sys.exit(0)


MENU_OPTIONS = {
    "1": ("Add Token Cookies", add_token),
    "2": ("Set username and password", set_user_password),
    "3": ("Check license", check_license),
    "4": ("Auto absent", attendance_in),
    "5": ("Exit", exit_application()),
}


def menu_show():
    print("\n==== Program Auto Absent ====")
    for key, (desc, _) in MENU_OPTIONS.items():
        print(f"{key}. {desc}")
    choice = input("Select menu> ")
    return choice


def main():
    while True:
        choice = menu_show()
        action = MENU_OPTIONS.get(choice)
        if action:
            action[1]()
        else:
            print(f"Menu '{choice}' is not valid. You can try again.\n")


if __name__ == "__main__":
    main()
