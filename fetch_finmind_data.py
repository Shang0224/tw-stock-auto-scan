import requests
import os
import time
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta

def get_tw50():
    url = "https://www.yuantaetfs.com/api/StkWeights?fundid=0050"

    res = requests.get(url)
    
    print(res.status_code)
    print(res.text[:200])  # 看前200字
    
    data = requests.get(url).json()

    df = pd.DataFrame(data)
    df = df[['StockCode', 'StockName', 'Weight']]

    return df

def fetch_finmind_data():



    df = get_tw50()
    print(df)
    
    # 1. 初始化 FinMind 客戶端
    finmindtoken = os.getenv("FINMIND_ACCESS_TOKEN")
    dl = DataLoader(token=finmindtoken)
    
    # 2. 設定存檔資料夾
    target_dir = "data"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"📁 已建立資料夾: {target_dir}")

    # 3. 取得台灣 50 與 中型 100 清單 (由 FinMind 取得最新成份股)
    print("🔍 正在取得指數成份股清單...")
    
    stock_list = []
    
    try:
        tw50 = dl.taiwan_stock_holding_shares_per(stock_id="0050")
        mid100 = dl.taiwan_stock_holding_shares_per(stock_id="0051")
    
        # 合併代號並去重 (取 stock_id 欄位)
        stock_list = list(set(tw50['stock_id'].tolist() + mid100['stock_id'].tolist()))
        print(f"✅ 預計抓取股票數量: {len(stock_list)} 檔")
    except Exception as e:
            print(f"❌ 處理時發生錯誤: {e}")
    

    # 4. 設定時間區間 (回溯 20 年)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=20*365)).strftime('%Y-%m-%d')

    # 5. 開始迴圈抓取
    for i, stock_id in enumerate(stock_list):
        try:
            # 檢查是否已有該股票的任何 CSV (避免重複抓取)
            existing_files = [f for f in os.listdir(target_dir) if f.startswith(f"{stock_id}_")]
            if existing_files:
                print(f"⏩ [{i+1}/{len(stock_list)}] {stock_id} 已存在，跳過。")
                continue

            print(f"🚀 [{i+1}/{len(stock_list)}] 正在抓取 {stock_id} (從 {start_date} 起)...")
            
            # 抓取日成交資料
            df = dl.taiwan_stock_daily(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date
            )

            if not df.empty:
                # 取得最後一筆資料的日期
                last_date = df['date'].iloc[-1]
                
                # 設定檔名: 代號_最後日期.csv
                file_name = f"{stock_id}_{last_date}.csv"
                file_path = os.path.join(target_dir, file_name)
                
                # 儲存 CSV
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                print(f"💾 已存檔: {file_name} (共 {len(df)} 筆)")
            else:
                print(f"⚠️ {stock_id} 無資料返回。")

            # 💡 關鍵：防封鎖機制 (每抓一檔停 2 秒)
            time.sleep(2)

        except Exception as e:
            print(f"❌ 處理 {stock_id} 時發生錯誤: {e}")
            time.sleep(5) # 發生錯誤時停久一點

    print("\n✨ 所有任務執行完畢！")

if __name__ == "__main__":
    fetch_finmind_data()
