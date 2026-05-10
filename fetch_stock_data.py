import requests
import os
import time
import pandas as pd
import yfinance as yf

from FinMind.data import DataLoader
from fugle_marketdata import RestClient
from datetime import datetime, timedelta, timezone

def fetch_yfinance_data():
    
    # 2. 設定存檔資料夾
    target_dir = "data"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"📁 已建立資料夾: {target_dir}")

    #起始資料設定
    files_env = os.getenv('STOCK_FILES', 'data/TW50.csv')
    
    # 1. 建立台灣時區 (UTC+8)
    tz_tw = timezone(timedelta(hours=8))

    # 2. 設定初始時間（預設為你的測試日期）
    # 當你在本機執行時，會直接採用這個時間
    tw_time = datetime.now(tz_tw)
   
    # 3. 環境判定：取得觸發事件名稱
    event_name = os.getenv('GITHUB_EVENT_NAME')
    
    # 邏輯判定：只有在「定時排程」時才切換到今日時間
    if event_name == 'schedule':
        #tw_time = datetime.now(tz_tw)
        # 2. 讀取.csv檔
        # 從系統環境變數讀取，若讀不到則給予預設值
        files_env = os.getenv('STOCK_FILES', 'data/MID100.csv')
       
        print(f"【定時排程模式】自動切換至今日：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")
    else:
        print(f"\n【GitHub 手動模式】執行程式內設定日期：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")

    finmindtoken = os.getenv("FINMIND_ACCESS_TOKEN")
    
    # 1. 初始化 FinMind (建議去官網申請免費 Token 速度更快，沒 Token 每日限額較少)
    dl = DataLoader(token=finmindtoken)
    # 1. 先抓一次全市場基本資訊
    df_info = dl.taiwan_stock_info()

    print("df_info...\n")
    # 建立一個字典，方便快速查找名稱：{ "2317": "鴻海", ... }
    stock_name_dict = dict(zip(df_info['stock_id'], df_info['stock_name']))

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

    print(f"🔍 正在透過 yfinance 取得 {len(stock_ids)} 檔成分股 (原始數據)...") 

    # 1. 計算日期區間
    end_date = tw_time.strftime("%Y-%m-%d")
    start_date = (tw_time.replace(year=tw_time.year - 20)).strftime("%Y-01-01")

    print(f"🚀 [Batch] 開始抓取 {len(stock_ids)} 檔股票資料 (從 {start_date} 起)...")

    results = []

    # 5. 開始迴圈抓取
    for i, stock_id in enumerate(stock_ids):
        try:
            # 檢查是否已有該股票的任何 CSV (避免重複抓取)
            existing_files = [f for f in os.listdir(target_dir) if f.startswith(f"{stock_id}_")]
            if existing_files:
                print(f"⏩ [{i+1}/{len(stock_ids)}] {stock_id} 已存在，跳過。")
                continue

            print(f"🚀 [{i+1}/{len(stock_ids)}] 正在抓取 {stock_id} (從 {start_date} 起)...")
            
        
            # 2. 呼叫歷史 K 線接口
            # 下載歷史資料 (包含 Open, High, Low, Close, Volume, Dividends, Stock Splits)
            # interval 可以設定為 '1d', '1wk', '1mo' 等
            # 建立 Ticker 物件
            stock = yf.Ticker(f"{stock_id}.TW")

            df = stock.history(start=start_date, end=end_date)
          
            # 3. 判斷資料是否為空 (關鍵邏輯)    
            if not df.empty:
                # 1. 確保時區正確（台灣為 +8），並移除時區資訊使其變為「純時間」
                df.index = df.index.tz_convert('Asia/Taipei').tz_localize(None)

                # 2. 將索引轉換為純日期 (YYYY-MM-DD)
                df.index = df.index.date

                # 3. (選用) 如果你希望日期變成一個欄位，而不是索引
                df = df.reset_index().rename(columns={'index': 'Date'})

                # 新增一個欄位叫 'Volume_K' (張數)
                # 使用 // 是整數除法，若要精確到小數點可用 /
                df['Volume_K'] = df['Volume'] / 1000
                
                # 取得最後一筆資料的日期
                last_date = df['Date'].iloc[-1]
                
                # 設定檔名: 代號_最後日期.csv
                file_name = f"{stock_id}_{last_date}.csv"
                file_path = os.path.join(target_dir, file_name)
                
                # 儲存 CSV
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                print(f"💾 已存檔: {file_path} (共 {len(df)} 筆)")
            else:
                print(f"⚠️ {stock_id} 無資料返回。")

            # 💡 關鍵：防封鎖機制 (每抓一檔停 2 秒)
            time.sleep(2)

        except Exception as e:
            print(f"❌ 處理 {stock_id} 時發生錯誤: {e}")
            time.sleep(5) # 發生錯誤時停久一點

    print("\n✨ 所有任務執行完畢！")


def fetch_finmind_data():
    
    # 2. 設定存檔資料夾
    target_dir = "data"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"📁 已建立資料夾: {target_dir}")

    #起始資料設定
    files_env = os.getenv('STOCK_FILES', 'data/TW50.csv')
    
    # 1. 建立台灣時區 (UTC+8)
    tz_tw = timezone(timedelta(hours=8))

    # 2. 設定初始時間（預設為你的測試日期）
    # 當你在本機執行時，會直接採用這個時間
    tw_time = datetime.now(tz_tw)
   
    # 3. 環境判定：取得觸發事件名稱
    event_name = os.getenv('GITHUB_EVENT_NAME')
    
    # 邏輯判定：只有在「定時排程」時才切換到今日時間
    if event_name == 'schedule':
        #tw_time = datetime.now(tz_tw)
        # 2. 讀取.csv檔
        # 從系統環境變數讀取，若讀不到則給予預設值
        files_env = os.getenv('STOCK_FILES', 'data/MID100.csv')
       
        print(f"【定時排程模式】自動切換至今日：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")
    else:
        print(f"\n【GitHub 手動模式】執行程式內設定日期：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")
        
    finmindtoken = os.getenv("FINMIND_ACCESS_TOKEN")    
    
    # 1. 初始化 FinMind (建議去官網申請免費 Token 速度更快，沒 Token 每日限額較少)
    dl = DataLoader(token=finmindtoken)
    # 1. 先抓一次全市場基本資訊
    df_info = dl.taiwan_stock_info()

    print("df_info...\n")
    # 建立一個字典，方便快速查找名稱：{ "2317": "鴻海", ... }
    stock_name_dict = dict(zip(df_info['stock_id'], df_info['stock_name']))

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

    print(f"🔍 正在透過 FinMind 取得 {len(stock_ids)} 檔成分股 (原始數據)...") 

    # 1. 計算日期區間
    end_date = tw_time.strftime("%Y-%m-%d")
    start_date = (tw_time.replace(year=tw_time.year - 20)).strftime("%Y-01-01")

    print(f"🚀 [Batch] 開始抓取 {len(stock_ids)} 檔股票資料 (從 {start_date} 起)...")
    
    results = []

    # 5. 開始迴圈抓取
    for i, stock_id in enumerate(stock_ids):
        try:
            # 檢查是否已有該股票的任何 CSV (避免重複抓取)
            existing_files = [f for f in os.listdir(target_dir) if f.startswith(f"{stock_id}_")]
            if existing_files:
                print(f"⏩ [{i+1}/{len(stock_ids)}] {stock_id} 已存在，跳過。")
                continue

            print(f"🚀 [{i+1}/{len(stock_ids)}] 正在抓取 {stock_id} (從 {start_date} 起)...")
            
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
                print(f"💾 已存檔: {file_path} (共 {len(df)} 筆)")
            else:
                print(f"⚠️ {stock_id} 無資料返回。")

            # 💡 關鍵：防封鎖機制 (每抓一檔停 2 秒)
            time.sleep(2)

            # 抓取還原股價成交資料
            df = dl.taiwan_stock_daily_adj(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date
            )

            if not df.empty:
                # 取得最後一筆資料的日期
                last_date = df['date'].iloc[-1]
                
                # 設定檔名: 代號_最後日期.csv
                file_name = f"{stock_id}_daily_adj_{last_date}.csv"
                file_path = os.path.join(target_dir, file_name)
                
                # 儲存 CSV
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                print(f"💾 已存檔: {file_path} (共 {len(df)} 筆)")
            else:
                print(f"⚠️ {stock_id} 無資料返回。")

            # 💡 關鍵：防封鎖機制 (每抓一檔停 2 秒)
            time.sleep(2)

        except Exception as e:
            print(f"❌ 處理 {stock_id} 時發生錯誤: {e}")
            time.sleep(5) # 發生錯誤時停久一點

    print("\n✨ 所有任務執行完畢！")


def fetch_fugle_data():
    
    # 2. 設定存檔資料夾
    target_dir = "data"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"📁 已建立資料夾: {target_dir}")

    #起始資料設定
    files_env = os.getenv('STOCK_FILES_TEST', 'data/TW50.csv')
    
    # 1. 建立台灣時區 (UTC+8)
    tz_tw = timezone(timedelta(hours=8))

    # 2. 設定初始時間（預設為你的測試日期）
    # 當你在本機執行時，會直接採用這個時間
    tw_time = datetime.now(tz_tw)
   
    # 3. 環境判定：取得觸發事件名稱
    event_name = os.getenv('GITHUB_EVENT_NAME')
    
    # 邏輯判定：只有在「定時排程」時才切換到今日時間
    if event_name == 'schedule':
        #tw_time = datetime.now(tz_tw)
        # 2. 讀取.csv檔
        # 從系統環境變數讀取，若讀不到則給予預設值
        files_env = os.getenv('STOCK_FILES', 'data/MID100.csv')
       
        print(f"【定時排程模式】自動切換至今日：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")
    else:
        print(f"\n【GitHub 手動模式】執行程式內設定日期：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")

    finmindtoken = os.getenv("FINMIND_ACCESS_TOKEN")
    
    # 1. 初始化 FinMind (建議去官網申請免費 Token 速度更快，沒 Token 每日限額較少)
    dl = DataLoader(token=finmindtoken)
    # 1. 先抓一次全市場基本資訊
    df_info = dl.taiwan_stock_info()

    print("df_info...\n")
    # 建立一個字典，方便快速查找名稱：{ "2317": "鴻海", ... }
    stock_name_dict = dict(zip(df_info['stock_id'], df_info['stock_name']))

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

    print(f"🔍 正在透過 Fugle 取得 {len(stock_ids)} 檔成分股 (原始數據)...") 

    # 1. 計算日期區間
    to_date = "2025-12-31" #結束日期
    from_date = "2025-01-01" #開始日期
    
    #to_date = tw_time.strftime("%Y-%m-%d")
    #from_date = "2000-01-01"

    print(f"🚀 [Batch] 開始抓取 {len(stock_ids)} 檔股票資料 (從 {from_date} 起)...")

    # 1. 初始化 Fugle
    fugletoken = os.getenv("FUGLE_ACCESS_TOKEN")  
    client = RestClient(api_key=fugletoken)
    stock = client.stock
    
    results = []

    # 5. 開始迴圈抓取
    for i, stock_id in enumerate(stock_ids):
        try:
            # 檢查是否已有該股票的任何 CSV (避免重複抓取)
            existing_files = [f for f in os.listdir(target_dir) if f.startswith(f"{stock_id}_")]
            if existing_files:
                print(f"⏩ [{i+1}/{len(stock_ids)}] {stock_id} 已存在，跳過。")
                continue

            print(f"🚀 [{i+1}/{len(stock_ids)}] 正在抓取 {stock_id} (從 {from_date} 起)...")
            
        
            # 2. 呼叫歷史 K 線接口
            # is_adjusted=True：自動計算除權息還原
            # from_date：富果個股資料最遠支援至 2010-01-01
            raw_data = stock.historical.candles(
                symbol=stock_id,
                **{"from": from_date, "to": to_date},
                fields="open,high,low,close,volume,change",
                is_adjusted=True 
            )

            # 3. 判斷資料是否為空 (關鍵邏輯)
            # 富果回傳通常是字典，資料清單在 'data' 鍵值中
            if not raw_data.get('data'):
                print(f"錯誤：{symbol} 在指定區間內沒有抓到任何資料。")
                return None
        
            # 4. 轉換為 Pandas DataFrame
            df = pd.DataFrame(raw_data['data'])
        
            # 再次確認 DataFrame 是否為空
            if not df.empty:
                # 5. 格式化處理
                df['date'] = pd.to_datetime(df['date'])
                numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'change']
                df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)
        
                # 依照日期排序（由舊到新，對計算 MA240 至關重要）
                df = df.sort_values('date').reset_index(drop=True)

                # 取得最後一筆資料的日期
                last_date = df['date'].iloc[-1]        
            
                # 6. 存入檔案
                file_name = f"{stock_id}_{last_date.strftime('%Y-%m-%d')}_history_adj.csv"
                file_path = os.path.join(target_dir, file_name)
        
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                print(f"資料處理完成！已成功存入檔案: {file_name} (共 {len(df)} 筆)")
            else :       
                print(f"⚠️ 轉換後的 DataFrame 是空的, {stock_id} 無資料返回。")
                        
            # 💡 關鍵：防封鎖機制 (每抓一檔停 2 秒)
            time.sleep(2)

        except Exception as e:
            print(f"❌ 處理 {stock_id} 時發生錯誤: {e}")
            time.sleep(5) # 發生錯誤時停久一點

    print("\n✨ 所有任務執行完畢！")

if __name__ == "__main__":
    #fetch_yfinance_data()
    fetch_fugle_data()
    #fetch_finmind_data()
