import gspread
from gspread.exceptions import WorksheetNotFound
from oauth2client.service_account import ServiceAccountCredentials
from google_play_scraper import collection, Collection
from datetime import datetime, timedelta, timezone
import os
import json

# 1. 인증 및 구글 시트 연결
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get('GCP_CREDENTIALS')
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet_url = os.environ.get('SHEET_URL')
doc = client.open_by_url(sheet_url)

# 2. 한국 시간(KST) 기준으로 오늘/어제 날짜 계산
KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
today_str = now.strftime("%Y-%m-%d")
yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

# 3. 어제 시트에서 전일 순위 파악하기 (앱 이름 기준)
previous_ranks = {}
try:
    yesterday_sheet = doc.worksheet(yesterday_str)
    records = yesterday_sheet.get_all_records()
    for row in records:
        if row.get('앱 이름') and row.get('순위'):
            previous_ranks[row['앱 이름']] = int(row['순위'])
except WorksheetNotFound:
    print(f"어제({yesterday_str}) 시트를 찾을 수 없어 전일 대비 데이터는 'NEW'로 표시됩니다.")

# 4. 오늘 날짜의 시트 준비 (없으면 새로 생성, 있으면 초기화)
try:
    today_sheet = doc.worksheet(today_str)
    today_sheet.clear() # 이미 시트가 있다면 내용을 비우고 덮어씌움
except WorksheetNotFound:
    # 100위까지 기록해야 하므로 넉넉하게 120행, 5열로 시트 생성
    today_sheet = doc.add_worksheet(title=today_str, rows="120", cols="5")

# 5. 구글 플레이스토어 게임 최고 매출 순위 크롤링 (1~100위)
try:
    top_games, _ = collection(
        Collection.TOP_GROSSING,
        category='GAME',
        country='kr',
        lang='ko'
    )
except Exception as e:
    print(f"크롤링 에러 발생: {e}")
    top_games = []

# 6. 헤더 및 데이터 정리
headers = ["날짜", "순위", "앱 이름", "개발사(퍼블리셔)", "전일 대비"]
new_rows = [headers]

for rank, game in enumerate(top_games[:100], start=1):
    title = game['title']
    developer = game.get('developer', '알 수 없음')
    
    # 전일 대비 순위 계산 로직 ('앱 이름'으로 어제 시트와 비교)
    if title in previous_ranks:
        prev_rank = previous_ranks[title]
        diff = prev_rank - rank
        if diff > 0:
            change = f"▲ {diff}"
        elif diff < 0:
            change = f"▼ {abs(diff)}"
        else:
            change = "-"
    else:
        change = "NEW"
        
    new_rows.append([today_str, rank, title, developer, change])

# 7. 완성된 데이터를 오늘 시트에 한 번에 쓰기
if len(new_rows) > 1:
    today_sheet.update(values=new_rows, range_name="A1")
    print(f"{today_str} 기준 Top 100 매출 순위 업데이트 완료! (시트명: {today_str})")
else:
    print("업데이트할 데이터가 없습니다.")
