import pandas as pd
import yfinance as yf
from datetime import datetime

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
    # 1. 讀取 CSV (請確保檔案在 data 資料夾)

    csv_path = "data/TW50.csv"
    
    if not os.path.exists(csv_path):
        print(f"找不到檔案: {csv_path}")
        return
    
    try:
        df_list = smart_read_csv('data/TW50.csv')
        # 取得代號並加上 .TW
        tickers = [f"{str(c).strip()}.TW" for c in df_list['代號']]
    except Exception as e:
        print(f"讀取 CSV 失敗: {e}")
        return

    print(f"🔍 正在批次下載 {len(tickers)} 檔股票數據...")

    # 2. 一次下載所有股票 (2年資料，關閉自動還原)
    # auto_adjust=False 確保抓到的是跟券商一樣的「原始收盤價」
    data = yf.download(tickers, period="2y", auto_adjust=False, group_by='ticker')

    breakout_list = []

    # 3. 逐一計算並判斷
    for ticker in tickers:
        try:
            # 取得該股的原始收盤價 (Close)
            df = data[ticker]['Close'].dropna()
            
            if len(df) < 240:
                continue

            # 計算 SMA240
            sma240 = df.rolling(window=240).mean()
            
            today_price = df.iloc[-1]
            yesterday_price = df.iloc[-2]
            today_sma = sma240.iloc[-1]
            yesterday_sma = sma240.iloc[-2]

            print(f"股票：{ticker}  收盤價: {round(today_price, 2)}  (年線: {today_sma})")

            
            # 突破判斷：昨天在線下，今天在線上
            if yesterday_price < yesterday_sma and today_price > today_sma:
                breakout_list.append({
                    "代號": ticker,
                    "今日收盤": round(today_price, 2),
                    "原始年線": round(today_sma, 2),
                    "偏離率": f"{round(((today_price/today_sma)-1)*100, 2)}%"
                })
        except Exception as e:
            # 有些新上市股票可能沒資料，跳過即可
            continue

    # 4. 顯示結果
    print(f"\n📅 掃描日期: {datetime.now().strftime('%Y-%m-%d')}")
    if breakout_list:
        result_df = pd.DataFrame(breakout_list)
        print("✨ 發現以下股票剛突破原始年線：")
        print(result_df.to_string(index=False))
        # 存成報告供 OpenClaw 讀取
        result_df.to_csv('data/breakout_report.csv', index=False, encoding='utf-8-sig')
    else:
        print("今日無符合突破條件的股票。")

if __name__ == "__main__":
    main()
