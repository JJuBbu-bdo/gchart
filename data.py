import os
import json
import time
from datetime import datetime, timedelta  # <-- 이 줄이 꼭 필요합니다!

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def update_db_and_trigger(scraped_data):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. GitHub Actions의 Secret을 환경변수로 불러오기
    creds_json = os.environ.get("GCP_CREDENTIALS")
    
    if creds_json:
        # 깃헙 환경: Secret 문자열을 딕셔너리로 변환하여 인증
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # 로컬 환경: PC에서 직접 실행할 때는 기존 JSON 파일 사용
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
    client = gspread.authorize(creds)
    
    # 2. 스프레드시트 연결 (실제 이름이나 URL로 꼭 변경해주세요)
    sheet = client.open("https://docs.google.com/spreadsheets/d/1CW7Xr3eWBUKBPC0DXRDsqqrx2itUlzZfXPVF2hUoMAw/edit?gid=2017461349#gid=2017461349")
    db_sheet = sheet.worksheet("월간신작DB")
    config_sheet = sheet.worksheet("설정")
    
    # 1. 기존 데이터 가져오기
    existing_records = db_sheet.get_all_records()
    existing_keys = {f"{r.get('게임명', '')}_{r.get('플랫폼', '')}": r for r in existing_records if r.get('게임명')}
    new_keys = {f"{r['게임명']}_{r['플랫폼']}": r for r in scraped_data}
    
    # 2. 변경점 감지 로직
    has_changes = False
    if set(existing_keys.keys()) != set(new_keys.keys()):
        has_changes = True
    else:
        for k, v in new_keys.items():
            if existing_keys[k]['출시일'] != v['출시일']:
                has_changes = True
                break
                
    is_month_start = (datetime.now().day == 1)
    
    # 3. DB 시트 덮어쓰기
    db_sheet.clear()
    db_sheet.append_row(["출시일", "게임명", "플랫폼", "퍼블리셔", "출시유형"])
    if scraped_data:
        db_sheet.append_rows([[d['출시일'], d['게임명'], d['플랫폼'], d['퍼블리셔'], d['출시유형']] for d in scraped_data])
        
    # 4. 앱스크립트 트리거 발동 (변경점이 있거나 1일인 경우)
    if existing_records == [] or has_changes or is_month_start:
        config_sheet.update_acell('B1', '발송요청')
        print("변경점 감지됨. 발송 트리거(B1)를 '발송요청'으로 변경했습니다.")
    else:
        print("변경점 없음. 트리거를 건드리지 않습니다.")

# 실행부
if __name__ == "__main__":
    now = datetime.now()
    scraped_data = scrape_calendar_by_url(now.year, now.month)
    update_db_and_trigger(scraped_data)
