from FinMind.data import DataLoader
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import requests

from strategy.near_ma240 import st_near_ma240

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

    print(f"USER ID : {user_id}\nMessage {message}")
    
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

    print(f"USER ID : {user_id}\nMessage {message}")
    
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        print("LINE 報告發送成功！")
    else:
        print(f"發送失敗，狀態碼：{res.status_code}, 內容：{res.text}")

def scan_stocks(stock_ids, algo_func, dl):
    """
    通用掃描器：只負責傳入代號，不干涉策略細節
    """
    # 1. 先抓一次全市場基本資訊
    df_info = dl.taiwan_stock_info()
    # 建立一個字典，方便快速查找名稱：{ "2317": "鴻海", ... }
    stock_name_dict = dict(zip(df_info['stock_id'], df_info['stock_name']))
    
    hits = []
    for sid in stock_ids:
        try:
            # 只需要把 sid 和 dl 丟進去，剩下的策略會自己搞定
            is_hit, info = algo_func(sid, dl)

            if is_hit:
                # 從傳進來的字典取得名稱
                res = {"股票名稱": stock_name_dict.get(sid, "未知")}
                res.update(info)
                hits.append(res)
                print(f"✅ 策略命中: {sid}")
            
            time.sleep(0.5) # 保護 API
        except Exception as e:
            print(f"❌ {sid} 處理出錯: {e}")
    return hits

def main():

    send_line_message("tessts")
    
    FinMindToken = os.getenv("FINMIMD_ACCESS_TOKEN")
    
    # 1. 初始化 FinMind (建議去官網申請免費 Token 速度更快，沒 Token 每日限額較少)
    dl = DataLoader(token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0yOCAxOToxMzo1NiIsInVzZXJfaWQiOiJKdWxpMDQwMiIsImVtYWlsIjoia3VvMDIyNEBnbWFpbC5jb20iLCJpcCI6IjEuMTYwLjExLjIyIn0.Eu4oVipAFick0oXt9wHTQU477KT4LxrunZy-Fp5d1vY")
    
    # 2. 讀取.csv檔

    # 從系統環境變數讀取，若讀不到則給予預設值
    files_env = os.getenv('STOCK_FILES', 'data/MID100.csv')
    
    # 解析字串（將逗號分隔的字串轉回 list）
    files = [f.strip() for f in files_env.split(',')]
    
    stock_ids = []
    for file in files:
        try:
            df = pd.read_csv(file, encoding='big5')
            # 確保代號欄位存在並轉為字串
            stock_ids.extend(df['代號'].astype(str).tolist())
            print(f"✅ 讀取成功: {file}")
        except Exception as e:
            print(f"❌ 讀取 {file} 失敗: {e}")
            
    # 去除重複項
    stock_ids = list(set(stock_ids))   

    print(f"🔍 正在透過 FinMind 掃描 {len(stock_ids)} 檔成分股 (原始數據)...")

    results = []

    # 3. 逐一抓取並計算
    try:
        # --- D. 執行 scan_stocks 呼叫敘述 ---
        # 這裡就是你問的「呼叫敘述」
        results = scan_stocks(
                            stock_ids=stock_ids, 
                            algo_func=st_near_ma240, 
                            dl=dl)

        # --- E. 處理結果 ---
        print("\n=== 掃描完成，符合條件的標的如下 ===")
        for item in results:
            print(item)
    except Exception as e:
        print(f"❌ 處理 {sid} 時出錯: {e}")

    # 4. 輸出報告
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    if results:
        report = pd.DataFrame(results)
    
        # 建立訊息標頭
        message_text = f"📅 掃描完成: {now_str}\n"
        message_text += "=== 靠近年線的名單 ===\n\n"
    
        # 逐行加入股票資訊
        message_text += report.to_string(index=False)
        
        # 儲存 CSV（原本的邏輯保留）
        report.to_csv('data/breakout_report_finmind.csv', index=False, encoding='utf-8-sig')

    else:
        message_text = f"📅 {now_str}\n今日無符合條件之股票。"

    # 原本的 print 輸出也可以保留在 Console 方便除錯
    print(message_text)
    
    # 傳出訊息
    # 確保您的 send_line_message 函數已經設定好 Channel Access Token    
    send_line_message(message_text)

if __name__ == "__main__":
    main()
