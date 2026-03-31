from FinMind.data import DataLoader
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import requests

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

def strategy_near_ma240(sid, dl):
    """
    年線預備股策略：自主決定抓取 500 天資料
    """
    import datetime
    # 策略決定需要的時間長度
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=500)).strftime("%Y-%m-%d")
    
    # 策略自主抓取資料
    df = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
    
    if df.empty or len(df) < 240:
        return False, {}

    # 計算邏輯
    #df['MA240'] = df['close'].rolling(240).mean()
    #today = df.iloc[-1]
    #dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    
    #is_hit = abs(dist_ratio) <= 0.03

    breakout_hits = []
    
    try:
        # 抓取台股日成交資料 (建議 start_date 抓 500 天前以利計算與比較)
        df = dl.taiwan_stock_daily(
                        stock_id=sid,
                        start_date=start_date,
                        end_date=end_date)
            
        if len(df) < 240:
            return False, {}

        # 計算各指標
        df['MA20'] = df['close'].rolling(window=20).mean()   # 月線
        df['MA60'] = df['close'].rolling(window=60).mean()   # 季線
        df['MA240'] = df['close'].rolling(window=240).mean() # 年線
            
        today = df.iloc[-1]
            
        curr_price = today['close']
        ma240 = today['MA240']
        ma20 = today['MA20']
            
        # --- 邏輯抽換：預備股篩選清單 ---
            
        # 1. 價格區間：設定在年線上下 3% 範圍內
        # 公式：|股價 - 年線| / 年線 <= 0.03
        dist_ratio = (curr_price - ma240) / ma240
        is_in_range = abs(dist_ratio) <= 0.03
            
        # 2. 進階過濾：短線必須先轉強 (股價已站上月線)
        # 這能過濾掉「一路陰跌且尚未止跌」的股票
        is_short_term_strong = curr_price > ma20

        if is_in_range and is_short_term_strong:
            # 判斷是在年線之上還是之下
            status = "年線上方強勢整理" if dist_ratio > 0 else "年線下方準備突破"
                
            breakout_hits.append({
                    "股票代號": sid,
                    "今日收盤": curr_price,
                    "年線位置": round(ma240, 2),
                    "距離年線幅": f"{round(dist_ratio * 100, 2)}%",
                    "狀態": status,
                    "成交量": today['Trading_Volume']
                })
            print(f"🎯 發現預備標的：{sid} ({status})，距離比：{round(dist_ratio*100, 2)}%")
            
        # FinMind 頻率限制
        time.sleep(0.5)

    except Exception as e:
        print(f"❌ 處理 {sid} 時出錯: {e}")

    
    #return is_hit, {"年線": f"{round(today['MA240'], 2)}", "距離年線": f"{round(dist_ratio*100, 2)}%", "收盤": today['close']}
    return is_in_range, breakout_hits


def scan_stocks(stock_ids, algo_func, dl):
    """
    通用掃描器：只負責傳入代號，不干涉策略細節
    """
    hits = []
    for sid in stock_ids:
        try:
            # 只需要把 sid 和 dl 丟進去，剩下的策略會自己搞定
            is_hit, info = algo_func(sid, dl)
            
            if is_hit:
                res = {"股票代號": sid}
                res.update(info)
                hits.append(res)
                print(f"✅ 策略命中: {sid}")
            
            time.sleep(0.5) # 保護 API
        except Exception as e:
            print(f"❌ {sid} 處理出錯: {e}")
    return hits

def main():

    send_line_message("tessts")
    
    
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

    print(f"🔍 正在透過 FinMind 掃描 {len(stock_ids)} 檔成分股 (原始數據)...")

    results = []

    # 3. 逐一抓取並計算
    try:
        # --- D. 執行 scan_stocks 呼叫敘述 ---
        # 這裡就是你問的「呼叫敘述」
        results = scan_stocks(
                            stock_ids=stock_ids, 
                            algo_func=strategy_near_ma240, 
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
