import requests
import os

def smart_read_csv(file_path):
    # 測試清單：UTF-8 (現代標準), Big5 (台灣常見), UTF-8-SIG (Excel 專用)
    encodings = ['utf-8', 'big5', 'utf-8-sig', 'cp950']
    
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, encoding=enc)
            print(f"✅ 成功使用 {enc} 編碼讀取檔案！")
            return df
        except UnicodeDecodeError:
            continue
    
    print("❌ 找不到匹配的編碼，請檢查檔案格式。")
    return None

def send_line_message(message):
    """透過 LINE Messaging API 發送訊息"""
    token = os.getenv("LINE_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")

    #print(f"USER ID : {user_id}\nMessage {message}")
    
    if not token or not user_id:
        print("錯誤：找不到 LINE 的設定資訊 (Secrets)")
        return

    url = "https://api.line.me/v2/bot/message/push"       
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }

    #print(f"USER ID : {user_id}\nMessage {message}")
    
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        print("LINE 報告發送成功！")
    else:
        print(f"發送失敗，狀態碼：{res.status_code}, 內容：{res.text}")
