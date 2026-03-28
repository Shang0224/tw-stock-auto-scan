from FinMind.data import DataLoader
import pandas as pd
import time
from datetime import datetime, timedelta
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
    
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        print("LINE 報告發送成功！")
    else:
        print(f"發送失敗，狀態碼：{res.status_code}, 內容：{res.text}")


def main():

    
    # 1. 初始化 FinMind (建議去官網申請免費 Token 速度更快，沒 Token 每日限額較少)
    dl = DataLoader(token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0yOCAxOToxMzo1NiIsInVzZXJfaWQiOiJKdWxpMDQwMiIsImVtYWlsIjoia3VvMDIyNEBnbWFpbC5jb20iLCJpcCI6IjEuMTYwLjExLjIyIn0.Eu4oVipAFick0oXt9wHTQU477KT4LxrunZy-Fp5d1vY")
    
    # 2. 讀取您的 TW50.csv
    # 1. 定義檔案名稱
   
    #file_tw50 = 'data/TW50.csv'
    #file_mid100 = 'data/MID100.csv'
    
    #combined_codes = []

    # 2. 讀取 台灣 50
    #if os.path.exists(file_tw50):
     #   df_50 = pd.read_csv(file_tw50, encoding='big5')
        # 確保代號是字串，避免遺失前導零（雖然台股目前較少見）
      #  combined_codes.extend(df_50['代號'].astype(str).tolist())
    #else:  
    #print(f"警告：找不到 {file_tw50}")

    # 3. 讀取 中型 100
 #   if os.path.exists(file_mid100):
  #      df_mid100 = pd.read_csv(file_mid100, encoding='big5')
   #        combined_codes.extend(df_mid100['代號'].astype(str).tolist())
   # else:
    #   print(f"警告：找不到 {file_mid100}")

    # 4. 去除重複項（若有股票同時存在於兩個清單）並排序
    #unique_codes = sorted(list(set(combined_codes)))

    # 5. 建立為 yfinance 格式的 stock_ids (加上 .TW)
    #stock_ids = [f"{code}.TW" for code in unique_codes]

    # 2. 讀取 CSV
    try:
        df_list = pd.read_csv('data/MID100.csv', encoding='big5')
        # 確保欄位名稱正確
        stock_ids = df_list['代號'].astype(str).tolist()
    except Exception as e:
        print(f"❌ 讀取 CSV 失敗: {e}")
        return

    # 設定時間範圍：抓取過去 360 天（確保有 240 根 K 線）
    start_date = (datetime.now() - timedelta(days=500)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"🔍 正在透過 FinMind 掃描 {len(stock_ids)} 檔成分股 (原始數據)...")
    breakout_hits = []

    # 3. 逐一抓取並計算
    for sid in stock_ids:
        try:
            # 抓取台股日成交資料
            df = dl.taiwan_stock_daily(
                stock_id=sid,
                start_date=start_date,
                end_date=end_date
            )
            
            if len(df) < 240:
                print(f"⚠️ {sid} 資料不足 240 筆，跳過。")
                continue

            # 計算 SMA240 (原始價格平均)
            df['MA240'] = df['close'].rolling(window=240).mean()
            
            # 取得最新兩筆數據
            today = df.iloc[-1]
            yesterday = df.iloc[-2]

            print(f"股票：{sid}  收盤價: {round(today['close'], 2)}  (年線: {today['MA240']})")
 
            # 突破條件：昨日收盤 < 昨日年線 AND 今日收盤 > 今日年線
            if yesterday['close'] < yesterday['MA240'] and today['close'] > today['MA240']:
                breakout_hits.append({
                    "股票代號": sid,
                    "今日收盤": today['close'],
                    "原始年線": round(today['MA240'], 2),
                    "成交量": today['Trading_Volume']
                })
                print(f"🚀 發現突破：{sid}！")
            
            # 💡 免費版 FinMind 建議加入短暫延遲，避免頻率限制
            time.sleep(0.5)

        except Exception as e:
            print(f"❌ 處理 {sid} 時出錯: {e}")

    # 4. 輸出報告

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    if breakout_hits:
        report = pd.DataFrame(breakout_hits)
    
        # 建立訊息標頭
        message_text = f"📅 掃描完成: {now_str}\n"
        message_text += "=== 今日突破 240MA 名單 ===\n\n"
    
        # 逐行加入股票資訊
        message_text += report.to_string(index=False)
        
        # 儲存 CSV（原本的邏輯保留）
        report.to_csv('data/breakout_report_finmind.csv', index=False, encoding='utf-8-sig')

    else:
        message_text = f"📅 {now_str}\n今日無符合突破 240MA 條件之股票。"

    # 傳出訊息
    # 確保您的 send_line_message 函數已經設定好 Channel Access Token
    send_line_message(message_text)

    # 原本的 print 輸出也可以保留在 Console 方便除錯
    print(message_text)



   # print(f"\n📅 掃描完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    #if breakout_hits:
     #   report = pd.DataFrame(breakout_hits)
      #  print("\n=== 今日突破 240MA 名單 (原始價) ===")
       # print(report.to_string(index=False))
        # 儲存 CSV 供後續 OpenClaw 或通知使用
        #report.to_csv('data/breakout_report_finmind.csv', index=False, encoding='utf-8-sig')
   # else:
         #print("今日無符合條件之股票。")

if __name__ == "__main__":
    main()
