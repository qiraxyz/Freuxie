import os
import re
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

# —————————————————————————————————————————
# CONFIG
# —————————————————————————————————————————
LOGIN_URL = "https://elearning.bsi.ac.id/login"
SCH_URL = "https://elearning.bsi.ac.id/sch"
BYPASS_WITH_COOKIES = True

# Load environment variables from .env file
load_dotenv()


# Read environment variables from .env file
def read_env():
    env_data = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    env_data[key] = value
    return env_data


# Save environment variables to .env file
def write_env(env_data):
    try:
        with open(".env", "w") as f:
            for key, value in env_data.items():
                f.write(f"{key}={value}\n")
        print(".env file updated successfully.")
    except IOError as error:
        print(f"Error saving to .env: {error}")


# Save tokens to .env
def save_tokens_to_env(extc, ems):
    env_data = read_env()
    # Update or add new tokens
    env_data["XSRF_TOKEN_COOKIE"] = extc
    env_data["MYBEST_SESSION_COOKIE"] = ems
    write_env(env_data)


# Save username and password to .env
def save_username_password(username, password):
    env_data = read_env()
    # Update or add new credentials
    env_data["USERNAME"] = username
    env_data["PASSWORD"] = password
    write_env(env_data)


# Example usage
save_tokens_to_env("abc123", "xyz789")
save_username_password("user1", "pass123")

# —————————————————————————————————————————
# Prepare session with CA BUNDLE
# —————————————————————————————————————————
session = requests.Session()
session.verify = "fullchain.pem"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": LOGIN_URL,
    "Accept": "text/html,application/xhtml+xml",
}


def login():
    """
    Perform login (GET login → parse CSRF & captcha → POST form)
    """
    r = session.get(LOGIN_URL, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # get CSRF token
    token_input = soup.find("input", {"name": "_token"})
    token = token_input.get("value") if token_input else None
    if not token:
        raise RuntimeError("CSRF token not found on login page")

    # parse captcha to text form
    form = soup.find("form") or soup
    text = form.get_text(separator=" ", strip=True)
    m = re.search(r"(\d+)\s*([+\-*/])\s*(\d+)", text)
    if not m:
        raise RuntimeError(f"Captcha question not found in form text: '{text}'")
    a, op, b = m.groups()
    if op == "+":
        captcha_answer = str(int(a) + int(b))
    elif op == "-":
        captcha_answer = str(int(a) - int(b))
    elif op == "*":
        captcha_answer = str(int(a) * int(b))
    else:
        captcha_answer = str(int(int(a) / int(b)))

    print(f"→ CSRF: {token}   Captcha: {a} {op} {b} → {captcha_answer}")

    payload = {"_token": token, "username": os.getenv("USERNAME"), "password": os.getenv("PASSWORD"),
               "captcha_answer": captcha_answer}
    r2 = session.post(
        LOGIN_URL,
        headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
        allow_redirects=False
    )
    return r2.status_code == 302 and "/user/dashboard" in r2.headers.get("Location", "")


def parse_today_classes(html: str):
    soup = BeautifulSoup(html, "html.parser")
    today = []
    # Search All header, filter with 'secondary'
    for hdr in soup.find_all("div", class_=lambda c: c and "pricing-header" in c.split()):
        classes = hdr.get("class")

        if "secondary" not in classes:
            title_tag = hdr.find("h6", class_="pricing-title")
            time_tag = hdr.find("div", class_="pricing-save")
            title = title_tag.get_text(strip=True) if title_tag else ""
            times = time_tag.get_text(strip=True) if time_tag else ""
            today.append({"course": title, "time": times})
    return today


def parse_class_entry(html: str):
    soup = BeautifulSoup(html, "html.parser")
    classes_links = []

    # Search All pricing-plan div (that contains Courses)
    for plan_div in soup.find_all("div", class_="pricing-plan"):
        header_div = plan_div.find("div", class_="pricing-header")

        if header_div and "secondary" not in header_div.get("class"):
            # get course INFO
            title_tag = header_div.find("h6", class_="pricing-title")
            time_tag = header_div.find("div", class_="pricing-save")
            course = title_tag.get_text(strip=True) if title_tag else ""
            time = time_tag.get_text(strip=True) if time_tag else ""

            # Search Button "Enter Class"
            footer_div = plan_div.find("div", class_="pricing-footer")
            if footer_div:
                entry_link = footer_div.find("a", class_="btn-primary", string=lambda s: s and "Masuk Kelas" in s)
                if entry_link and entry_link.get("href"):
                    classes_links.append({
                        "course": course,
                        "time": time,
                        "entry_link": entry_link.get("href")
                    })

    return classes_links


def access_class_pages(class_links):
    results = []
    for i, class_info in enumerate(class_links):
        print(f"🔄 Accessing class {class_info['course']}...")

        try:
            r = session.get(class_info['entry_link'], headers=HEADERS)
            r.raise_for_status()

            # save to HTML file
            filename = f"class_{i + 1}_{class_info['course'].replace(' ', '_')}.html"
            with open(filename, "w", encoding=r.encoding) as f:
                f.write(r.text)

            print(f"✅ Access success and saving the HTML parser to root path {class_info['course']} No. {filename}")

            # Add to list
            results.append({
                **class_info,
                "html_content": r.text,
                "filename": filename,
                "status_code": r.status_code
            })
        except Exception as e:
            print(f"❌ Failed to access class {class_info['course']}: {e}")
            results.append({
                **class_info,
                "error": str(e)
            })

    return results


def access_and_parse_sch():
    r = session.get(SCH_URL, headers=HEADERS)
    r.raise_for_status()
    print(f"🟢 /sch status: {r.status_code}")

    # Parse courses for Today
    courses_today = parse_today_classes(r.text)
    if courses_today:
        print("📋 Today's courses:")
        for k in courses_today:
            print(f" - {k['course']} at {k['time']}")
    else:
        print("🔴 No courses for today.")

    # Parse "Enter Class" links
    class_links = parse_class_entry(r.text)
    if class_links:
        print("🔗 'Enter Class' links found:")
        for cl in class_links:
            print(f" - {cl['course']} ({cl['time']}): {cl['entry_link']}")

        # Access each "Enter Class" link
        class_results = access_class_pages(class_links)
        print(f"✅ Successfully accessed {len(class_results)} class pages.")
    else:
        print("⚠️ No 'Enter Class' links found.")

    # Save /sch page HTML for reference
    with open("sch_page.html", "w", encoding=r.encoding) as f:
        f.write(r.text)

    return class_links


def auto_attendance():
    # Bypass login
    if BYPASS_WITH_COOKIES:
        session.cookies.set("XSRF-TOKEN", os.getenv("XSRF_TOKEN_COOKIE"))
        session.cookies.set("mybest_session", os.getenv("MYBEST_SESSION_COOKIE"))
        print("🔑 Bypass login: cookies have been set ", os.getenv("XSRF_TOKEN_COOKIE"),
              os.getenv("MYBEST_SESSION_COOKIE"))
        success = True
    else:
        try:
            success = login()
            # Save cookies
            if success:
                xtc = session.cookies.get("XSRF-TOKEN")
                msc = session.cookies.get("mybest_session")
                save_tokens_to_env(xtc, msc)
                print("💾 New token saved in file .env")
        except Exception as e:
            print(f"Error login: {e}")
            success = False

    if not success:
        print("❌ Login Failed. Check again the Credentials or Cookies TOKEN.")
        exit(1)

    print("🚀 Authenticated — accessing and parsing /sch …")
    class_links = access_and_parse_sch()