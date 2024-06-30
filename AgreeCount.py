import requests
import json
import time
from datetime import datetime
import os

MAX_LOG_LINES = 4000
LOG_FILE_NAME = "AgreeCountLog.txt"
TIMEOUT = 60  # seconds
RETRY_DELAY = 5  # seconds

def get_agree_count():
    url = "https://petitions.assembly.go.kr/api/petits/14CBAF8CE5733410E064B49691C1987F?petitId=14CBAF8CE5733410E064B49691C1987F&sttusCode="
    
    headers = {
        "Host": "petitions.assembly.go.kr",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Priority": "u=1"
    }
    
    while True:
        try:
            response = requests.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
            return data.get('agreCo')
        except requests.exceptions.Timeout:
            print(f"Request timed out after {TIMEOUT} seconds. Retrying in {RETRY_DELAY} seconds...")
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}. Retrying in {RETRY_DELAY} seconds...")
        
        time.sleep(RETRY_DELAY)

def manage_log_file():
    if not os.path.exists(LOG_FILE_NAME):
        return

    with open(LOG_FILE_NAME, 'r') as file:
        lines = file.readlines()

    if len(lines) > MAX_LOG_LINES:
        with open(LOG_FILE_NAME, 'w') as file:
            file.writelines(lines[-MAX_LOG_LINES:])

def log_agree_count(count):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp}: Agree Count = {count}\n"
    
    with open(LOG_FILE_NAME, "a") as log_file:
        log_file.write(log_entry)
    
    manage_log_file()

def main():
    while True:
        agree_count = get_agree_count()
        if agree_count is not None:
            log_agree_count(agree_count)
            print(f"Logged agree count: {agree_count}")
        time.sleep(5)

if __name__ == "__main__":
    main()