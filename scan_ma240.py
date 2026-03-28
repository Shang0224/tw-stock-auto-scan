import pandas as pd
import yfinance as yf
from datetime import datetime
import os

def check_stock(ticker):
    """判斷單一股票是否突破年線"""
    try:
        # 抓取 1.5 年數據確保 240MA 計算準確
        stock = yf.Ticker(ticker)
        df = stock.history(period="18mo")
        
        if len(df) < 240:
            return None

        # 計算 240MA (年線)
        df['MA240'] = df['Close'].rolling(window=240).mean()
     
        # 取得最後兩筆資料
        # today 是最後一筆，yesterday 是倒數第二筆
        today = df.iloc[-1]
        yesterday = df.iloc[-2]

        print(f"股票：{ticker} (年線: {today['MA240']})")
        
        # 突破條件：昨日收盤 < 昨日年線 AND 今日收盤 > 今日年線
        is_breakout = (yesterday['Close'] < yesterday['MA240']) and (today['Close'] > today['MA240'])
        
        if is_breakout:
            return {
                "代號": ticker,
                "收盤價": round(today['Close'], 2),
                "年線值": round(today['MA240'], 2),
                "今日漲幅": f"{round((today['Close']/yesterday['Close']-1)*100, 2)}%",
                "今日成交量": int(today['Volume'])
            }
    except Exception as e:
        print(f"查詢 {ticker} 時發生錯誤: {e}")
    return None
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
    # 1. 讀取 CSV 檔案 (路徑請根據您的 Repo 調整)
    csv_path = "data/TW50.csv"
    
    if not os.path.exists(csv_path):
        print(f"找不到檔案: {csv_path}")
        return

    # 讀取 CSV，假設欄位名稱是 '代號'
    # 如果您的 CSV 只有代號，請確認欄位名稱
    df_list = smart_read_csv(csv_path)
    
    # 確保代號格式正確 (加上 .TW)
    raw_codes = df_list['代號'].astype(str).tolist()
    tickers = [f"{c.strip()}.TW" if not c.endswith('.TW') else c for c in raw_codes]

    print(f"📅 執行日期: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"🔍 正在掃描 {len(tickers)} 檔成分股...")

    # 2. 執行掃描
    hits = []
    for t in tickers:
        result = check_stock(t)
        if result:
            hits.append(result)
            print(f"🚀 發現突破：{result['代號']} (價格: {result['收盤價']})")

    # 3. 輸出結果
    if hits:
        report_df = pd.DataFrame(hits)
        print("\n=== 突破 240MA 掃描結果 ===")
        print(report_df.to_string(index=False))
        # 儲存結果方便 OpenClaw 讀取通知
        report_df.to_csv("data/breakout_report.csv", index=False, encoding='utf-8-sig')
    else:
        print("\n今日無符合條件之股票。")

if __name__ == "__main__":
    main()
