from FinMind.data import DataLoader
import pandas as pd
import time
from datetime import datetime, timedelta

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

def main():

    
    # 1. 初始化 FinMind (建議去官網申請免費 Token 速度更快，沒 Token 每日限額較少)
    dl = DataLoader(token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0yOCAxOToxMzo1NiIsInVzZXJfaWQiOiJKdWxpMDQwMiIsImVtYWlsIjoia3VvMDIyNEBnbWFpbC5jb20iLCJpcCI6IjEuMTYwLjExLjIyIn0.Eu4oVipAFick0oXt9wHTQU477KT4LxrunZy-Fp5d1vY")
    
    # 2. 讀取您的 TW50.csv
    try:
        # 假設您的 CSV 欄位是 StockCode
        stock_list_df = smart_read_csv('data/TW50.csv')
        stock_ids = stock_list_df['代號'].astype(str).tolist()
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

            print(f"股票：{ticker}  收盤價: {round(today['Close'], 2)}  (年線: {today['MA240']})")
 
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
    print(f"\n📅 掃描完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if breakout_hits:
        report = pd.DataFrame(breakout_hits)
        print("\n=== 今日突破 240MA 名單 (原始價) ===")
        print(report.to_string(index=False))
        # 儲存 CSV 供後續 OpenClaw 或通知使用
        report.to_csv('data/breakout_report_finmind.csv', index=False, encoding='utf-8-sig')
    else:
        print("今日無符合條件之股票。")

if __name__ == "__main__":
    main()
