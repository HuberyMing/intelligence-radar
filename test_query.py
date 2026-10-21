import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("NOTION_API_TOKEN")
DB_ID = os.getenv("NOTION_DATABASE_ID", "").replace("-", "")

url = f"https://api.notion.com/v1/databases/{DB_ID}/query"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# 1. 測試不帶任何 filter 的空查詢
res = requests.post(url, headers=headers, json={})
print("空查詢狀態碼:", res.status_code)

if res.status_code == 200:
    results = res.json().get("results", [])
    print(f"成功查詢到 {len(results)} 筆資料！")
else:
    print("錯誤訊息:", res.text)