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
# Siapkan Session dengan CA bundle
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
    Lakukan login (GET login → parse CSRF & captcha → POST form)
    """
    r = session.get(LOGIN_URL, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # ambil CSRF token
    token_input = soup.find("input", {"name": "_token"})
    token = token_input.get("value") if token_input else None
    if not token:
        raise RuntimeError("CSRF token tidak ditemukan di halaman login")

    # parse soal captcha di teks form
    form = soup.find("form") or soup
    text = form.get_text(separator=" ", strip=True)
    m = re.search(r"(\d+)\s*([+\-*/])\s*(\d+)", text)
    if not m:
        raise RuntimeError(f"Soal captcha tidak ditemukan di teks form: '{text}'")
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

    payload = {"_token": token, "username": os.getenv("USERNAME"), "password": os.getenv("PASSWORD"), "captcha_answer": captcha_answer}
    r2 = session.post(
        LOGIN_URL,
        headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
        allow_redirects=False
    )
    return r2.status_code == 302 and "/user/dashboard" in r2.headers.get("Location", "")


def parse_today_classes(html: str):
    """
    Dari HTML /sch, kembalikan list mata kuliah yang tersedia hari ini beserta jam.
    """
    soup = BeautifulSoup(html, "html.parser")
    today = []
    # cari semua header, filter yang tidak memiliki kelas 'secondary'
    for hdr in soup.find_all("div", class_=lambda c: c and "pricing-header" in c.split()):
        classes = hdr.get("class")
        # hanya ambil yang murni 'pricing-header' atau tanpa 'secondary'
        if "secondary" not in classes:
            title_tag = hdr.find("h6", class_="pricing-title")
            time_tag = hdr.find("div", class_="pricing-save")
            title = title_tag.get_text(strip=True) if title_tag else ""
            times = time_tag.get_text(strip=True) if time_tag else ""
            today.append({"matkul": title, "waktu": times})
    return today


def parse_masuk_kelas(html: str):
    """
    Dari HTML /sch, kembalikan list link "Masuk Kelas" untuk mata kuliah hari ini.
    """
    soup = BeautifulSoup(html, "html.parser")
    classes_links = []

    # Cari semua pricing-plan div (yang berisi info mata kuliah)
    for plan_div in soup.find_all("div", class_="pricing-plan"):
        header_div = plan_div.find("div", class_="pricing-header")

        # Pastikan ini mata kuliah hari ini (bukan secondary)
        if header_div and "secondary" not in header_div.get("class"):
            # Ambil info mata kuliah
            title_tag = header_div.find("h6", class_="pricing-title")
            time_tag = header_div.find("div", class_="pricing-save")
            matkul = title_tag.get_text(strip=True) if title_tag else ""
            waktu = time_tag.get_text(strip=True) if time_tag else ""

            # Cari tombol "Masuk Kelas"
            footer_div = plan_div.find("div", class_="pricing-footer")
            if footer_div:
                masuk_link = footer_div.find("a", class_="btn-primary", string=lambda s: s and "Masuk Kelas" in s)
                if masuk_link and masuk_link.get("href"):
                    classes_links.append({
                        "matkul": matkul,
                        "waktu": waktu,
                        "link_masuk": masuk_link.get("href")
                    })

    return classes_links


def access_class_pages(class_links):
    """
    Akses setiap link "Masuk Kelas" dan simpan HTML-nya.
    """
    results = []
    for i, class_info in enumerate(class_links):
        print(f"🔄 Mengakses kelas {class_info['matkul']}...")

        try:
            r = session.get(class_info['link_masuk'], headers=HEADERS)
            r.raise_for_status()

            # Simpan HTML ke file
            filename = f"kelas_{i + 1}_{class_info['matkul'].replace(' ', '_')}.html"
            with open(filename, "w", encoding=r.encoding) as f:
                f.write(r.text)

            print(f"✅ Berhasil mengakses dan menyimpan HTML kelas {class_info['matkul']} ke {filename}")

            # Tambahkan hasil ke list
            results.append({
                **class_info,
                "html_content": r.text,
                "filename": filename,
                "status_code": r.status_code
            })
        except Exception as e:
            print(f"❌ Gagal mengakses kelas {class_info['matkul']}: {e}")
            results.append({
                **class_info,
                "error": str(e)
            })

    return results


def access_and_parse_sch():
    """
    Akses halaman /sch, parse mata kuliah hari ini, dan dapatkan link "Masuk Kelas".
    """
    r = session.get(SCH_URL, headers=HEADERS)
    r.raise_for_status()
    print(f"🟢 /sch status: {r.status_code}")

    # Parse mata kuliah hari ini
    kelas_today = parse_today_classes(r.text)
    if kelas_today:
        print("📋 Mata kuliah hari ini:")
        for k in kelas_today:
            print(f" - {k['matkul']} pada {k['waktu']}")
    else:
        print("🔴 Tidak ada mata kuliah hari ini.")

    # Parse link "Masuk Kelas"
    class_links = parse_masuk_kelas(r.text)
    if class_links:
        print("🔗 Link 'Masuk Kelas' ditemukan:")
        for cl in class_links:
            print(f" - {cl['matkul']} ({cl['waktu']}): {cl['link_masuk']}")

        # Akses setiap link "Masuk Kelas"
        class_results = access_class_pages(class_links)
        print(f"✅ Berhasil mengakses {len(class_results)} halaman kelas.")
    else:
        print("⚠️ Tidak ditemukan link 'Masuk Kelas'.")

    # Simpan HTML halaman /sch untuk referensi
    with open("sch_page.html", "w", encoding=r.encoding) as f:
        f.write(r.text)

    return class_links


def auto_attendance():

    # Bypass login
    if BYPASS_WITH_COOKIES:
        session.cookies.set("XSRF-TOKEN",os.getenv("XSRF_TOKEN_COOKIE"))
        session.cookies.set("mybest_session",os.getenv("MYBEST_SESSION_COOKIE"))
        print("🔑 Bypass login: cookie sudah diset ", os.getenv("XSRF_TOKEN_COOKIE"), os.getenv("MYBEST_SESSION_COOKIE"))
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
