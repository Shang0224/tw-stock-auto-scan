import yfinance as yf
import pandas as pd
import time
import os
import requests

from FinMind.data import DataLoader
from datetime import datetime, timedelta, timezone
from untils.untils import send_line_message, fm_fetch_all_stocks, yf_fetch_all_stocks, send_email_with_csv, upload_to_nas, cleanup_local_file
from strategy.near_ma240 import st_near_ma240, st_near_ma240_df
from scanstock.scanstock import scan_stocks_df, scan_stocks_df_list
from strategy.advanced_ma240 import st_advanced_ma240, st_advanced_ma240_df, st_advanced_ma240_df_up

def yfinance_Scan_ma240():
    #起始資料設定
    #files_env = os.getenv('STOCK_FILES', 'data/TW50.csv')
    files_env = os.getenv('STOCK_FILES_TEST', 'data/TW50_Test.csv')

    #my_strategies = [st_near_ma240_df, st_advanced_ma240_df, st_advanced_ma240_df_up]
    my_strategies = [st_advanced_ma240_df_up]
   
    # 1. 建立台灣時區 (UTC+8)
    tz_tw = timezone(timedelta(hours=8))

    # 2. 設定初始時間（預設為你的測試日期）
    # 當你在本機執行時，會直接採用這個時間
    tw_time = datetime(2024, 1, 9, tzinfo=tz_tw)
   
    # 3. 環境判定：取得觸發事件名稱
    event_name = os.getenv('GITHUB_EVENT_NAME')
    
    # 邏輯判定：只有在「定時排程」時才切換到今日時間
    if event_name == 'schedule':
        tw_time = datetime.now(tz_tw)
        # 2. 讀取.csv檔
        # 從系統環境變數讀取，若讀不到則給予預設值
        files_env = os.getenv('STOCK_FILES', 'data/MID100.csv')
        my_strategies = [st_near_ma240_df, st_advanced_ma240_df]
        print(f"【定時排程模式】自動切換至今日：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")
    else:
        print(type(files_env), files_env)
        print(f"\n【GitHub 手動模式】執行程式內設定日期：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")
        
    finmindtoken = os.getenv("FINMIND_ACCESS_TOKEN")    
    
    # 1. 初始化 FinMind (建議去官網申請免費 Token 速度更快，沒 Token 每日限額較少)
    dl = DataLoader(token=finmindtoken)
    # 1. 先抓一次全市場基本資訊
    df_info = dl.taiwan_stock_info()

    print("df_info...\n")
    # 建立一個字典，方便快速查找名稱：{ "2317": "鴻海", ... }
    stock_name_dict = dict(zip(df_info['stock_id'], df_info['stock_name']))

    #files_env = 'data/TW50.csv'
    
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

    print(f"🔍 正在透過 yfinance 掃描 {len(stock_ids)} 檔成分股 (原始數據)...")

    # 1. 計算日期區間
    end_date = tw_time.strftime("%Y-%m-%d")
    start_date = (tw_time - timedelta(days=500)).strftime("%Y-%m-%d")

    print(f"🚀 [Batch] 開始抓取 {len(stock_ids)} 檔股票資料 (從 {start_date} 起)...")
    
    # 1. 先獲取完整的大表
    all_df = yf_fetch_all_stocks(stock_ids, start_date, end_date)

    # 2. 檢查大表內容
    if not all_df.empty and not all_df.empty:
        print(f"📊 成功整合資料：共有 {all_df['stock_id'].nunique()} 檔股票，總計 {len(all_df)} 筆資料")
        print(f"✅ 成功抓取資料！")
        print(f"   - 總列數: {len(all_df)}")
        print(f"   - 欄位名稱: {list(all_df.columns)}")
        print(f"   - 涵蓋股票數: {all_df['stock_id'].nunique()}")
    else:
        print("❌ 嚴重錯誤：抓回來的資料是空的！請檢查 Token 或網路。")
    
    results = []

    # 3. 逐一抓取並計算
    try:
        # --- D. 執行 scan_stocks 呼叫敘述 ---
        # 這裡就是你問的「呼叫敘述」
        results = scan_stocks_df_list(
                            stock_ids=stock_ids, 
                            algo_func_list=my_strategies, 
                            all_df=all_df, 
                            stock_map=stock_name_dict)

        # --- E. 處理結果 ---
        print("\n=== 掃描完成，符合條件的標的如下 ===")
        for item in results:
            print(item['代號'])
    except Exception as e:
        print(f"❌ 處理掃描時出錯: {e}")

    # 4. 輸出報告, 
    now_str = tw_time.strftime('%Y-%m-%d %H:%M')

    # 取得目前時間並格式化
    # %Y:年, %m:月, %d:日, %H:時, %M:分
    current_time = tw_time.now().strftime("%Y%m%d_%H%M")
    file_name = f'data/yfinance/scan_report_yf_{current_time}.csv'

    if results:
        report = pd.DataFrame(results)
    
        # 1. 先進行排序 (假設按 '觸發策略' 排序)
        report = report.sort_values(by=['觸發策略', '代號'], ascending=[False, True])

        # 2. 【核心步驟】選取你想傳送到 LINE 的欄位
        # 假設你只想傳：代號、名稱、收盤價、觸發策略
        #short_report = report[['代號', '名稱', '收盤', '年線位置', '觸發策略']]
        short_report = report[['代號', '名稱', '收盤', '觸發策略']]

        # 3. 建立訊息標頭
        message_text = f"📅 掃描完成: {now_str}\n"
        message_text += "=== 靠近年線精選名單 ===\n\n"
    
        # 4. 使用簡化後的表格轉成文字
        message_text += short_report.to_string(index=False)
    
        # 儲存 CSV（原本的邏輯保留）
        report.to_csv(file_name, index=False, encoding='utf-8-sig')

    else:
        message_text = f"📅 {now_str}\n今日無符合條件之股票。"

    # 原本的 print 輸出也可以保留在 Console 方便除錯
    #print(message_text)
    
    # 傳出訊息
    # 確保您的 send_line_message 函數已經設定好 Channel Access Token    
    send_line_message(message_text)

    # 2. 從環境變數讀取帳密 (安全性考量)
    SENDER = os.getenv("SENDER_EMAIL")
    RECEIVER = os.getenv("RECIPIENT_EMAIL")
    
    # 這是 16 位元的應用程式密碼，非登入密碼
    PASSWORD = os.getenv("EMAIL_APP_PASSWORD") 

    # 3. 執行寄送
    #send_email_with_csv(file_name, RECEIVER, SENDER, PASSWORD)

    #print(f"NAS_SFTP_PATH: {os.getenv('NAS_SFTP_PATH')}, loaclpath: {file_name}")

    # 邏輯判定：只有在「定時排程」時才做上傳與清除檔案的動作
    if event_name == 'schedule':
        # 使用 Tailscale 分配給 NAS 的私有 IP
        upload_to_nas(
            host=os.getenv("NAS_VPN_IP"),  # 填入你 NAS 的 Tailscale IP
            port=int(os.getenv("NAS_SFTP_PORT")),
            username=os.getenv("NAS_ACCOUNT"),
            password=os.getenv("NAS_PASSWORD"),
            local_path=file_name,
            remote_path=f"{os.getenv('NAS_SFTP_PATH')}/scan_report_{current_time}.csv")

        cleanup_local_file(file_name)

def finmind_scan_ma240():
    #起始資料設定
    files_env = os.getenv('STOCK_FILES', 'data/TW50.csv')
    #files_env = os.getenv('STOCK_FILES_TEST', 'data/TW50_Test.csv')

    #my_strategies = [st_near_ma240_df, st_advanced_ma240_df, st_advanced_ma240_df_up]
    my_strategies = [st_advanced_ma240_df_up]

    
    # 1. 建立台灣時區 (UTC+8)
    tz_tw = timezone(timedelta(hours=8))

    # 2. 設定初始時間（預設為你的測試日期）
    # 當你在本機執行時，會直接採用這個時間
    tw_time = datetime(2024, 1, 9, tzinfo=tz_tw)
   
    # 3. 環境判定：取得觸發事件名稱
    event_name = os.getenv('GITHUB_EVENT_NAME')
    
    # 邏輯判定：只有在「定時排程」時才切換到今日時間
    if event_name == 'schedule':
        tw_time = datetime.now(tz_tw)
        # 2. 讀取.csv檔
        # 從系統環境變數讀取，若讀不到則給予預設值
        files_env = os.getenv('STOCK_FILES', 'data/MID100.csv')
        my_strategies = [st_near_ma240_df, st_advanced_ma240_df]
        print(f"【定時排程模式】自動切換至今日：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")
    else:
        print(type(files_env), files_env)
        print(f"\n【GitHub 手動模式】執行程式內設定日期：{tw_time.strftime('%Y-%m-%d')}, 資料來源：{files_env}")
        
    finmindtoken = os.getenv("FINMIND_ACCESS_TOKEN")    
    
    # 1. 初始化 FinMind (建議去官網申請免費 Token 速度更快，沒 Token 每日限額較少)
    dl = DataLoader(token=finmindtoken)
    # 1. 先抓一次全市場基本資訊
    df_info = dl.taiwan_stock_info()

    print("df_info...\n")
    # 建立一個字典，方便快速查找名稱：{ "2317": "鴻海", ... }
    stock_name_dict = dict(zip(df_info['stock_id'], df_info['stock_name']))

    #files_env = 'data/TW50.csv'
    
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

    # 1. 計算日期區間
    end_date = tw_time.strftime("%Y-%m-%d")
    start_date = (tw_time - timedelta(days=500)).strftime("%Y-%m-%d")

    print(f"🚀 [Batch] 開始抓取 {len(stock_ids)} 檔股票資料 (從 {start_date} 起)...")
    
    # 1. 先獲取完整的大表
    all_df = fm_fetch_all_stocks(dl, stock_ids, start_date, end_date)

    # 2. 檢查大表內容
    if not all_df.empty and not all_df.empty:
        print(f"📊 成功整合資料：共有 {all_df['stock_id'].nunique()} 檔股票，總計 {len(all_df)} 筆資料")
        print(f"✅ 成功抓取資料！")
        print(f"   - 總列數: {len(all_df)}")
        print(f"   - 欄位名稱: {list(all_df.columns)}")
        print(f"   - 涵蓋股票數: {all_df['stock_id'].nunique()}")
    else:
        print("❌ 嚴重錯誤：抓回來的資料是空的！請檢查 Token 或網路。")
    
    results = []

    # 3. 逐一抓取並計算
    try:
        # --- D. 執行 scan_stocks 呼叫敘述 ---
        # 這裡就是你問的「呼叫敘述」
        #results = scan_stocks_new(            
         #                   stock_ids=stock_ids, 
          #                  algo_func=st_near_ma240, 
           #                 dl=dl)

        #results = scan_stocks(
         #                   stock_ids=stock_ids, 
          #                  algo_func=st_near_ma240, 
           #                 dl=dl)
        results = scan_stocks_df_list(
                            stock_ids=stock_ids, 
                            algo_func_list=my_strategies, 
                            all_df=all_df, 
                            stock_map=stock_name_dict)

        # --- E. 處理結果 ---
        print("\n=== 掃描完成，符合條件的標的如下 ===")
        for item in results:
            print(item['代號'])
    except Exception as e:
        print(f"❌ 處理掃描時出錯: {e}")

    # 4. 輸出報告, 
    now_str = tw_time.strftime('%Y-%m-%d %H:%M')

    # 取得目前時間並格式化
    # %Y:年, %m:月, %d:日, %H:時, %M:分
    current_time = tw_time.now().strftime("%Y%m%d_%H%M")
    file_name = f'data/finmind/scan_report_fm_{current_time}.csv'

    if results:
        report = pd.DataFrame(results)
    
        # 1. 先進行排序 (假設按 '觸發策略' 排序)
        report = report.sort_values(by=['觸發策略', '代號'], ascending=[False, True])

        # 2. 【核心步驟】選取你想傳送到 LINE 的欄位
        # 假設你只想傳：代號、名稱、收盤價、觸發策略
        #short_report = report[['代號', '名稱', '收盤', '年線位置', '觸發策略']]
        short_report = report[['代號', '名稱', '收盤', '觸發策略']]

        # 3. 建立訊息標頭
        message_text = f"📅 掃描完成: {now_str}\n"
        message_text += "=== 靠近年線精選名單 ===\n\n"
    
        # 4. 使用簡化後的表格轉成文字
        message_text += short_report.to_string(index=False)
    
        # 儲存 CSV（原本的邏輯保留）
        report.to_csv(file_name, index=False, encoding='utf-8-sig')

    else:
        message_text = f"📅 {now_str}\n今日無符合條件之股票。"

    # 原本的 print 輸出也可以保留在 Console 方便除錯
    #print(message_text)
    
    # 傳出訊息
    # 確保您的 send_line_message 函數已經設定好 Channel Access Token    
    send_line_message(message_text)

    # 2. 從環境變數讀取帳密 (安全性考量)
    SENDER = os.getenv("SENDER_EMAIL")
    RECEIVER = os.getenv("RECIPIENT_EMAIL")
    
    # 這是 16 位元的應用程式密碼，非登入密碼
    PASSWORD = os.getenv("EMAIL_APP_PASSWORD") 

    # 3. 執行寄送
    #send_email_with_csv(file_name, RECEIVER, SENDER, PASSWORD)

    #print(f"NAS_SFTP_PATH: {os.getenv('NAS_SFTP_PATH')}, loaclpath: {file_name}")

    # 邏輯判定：只有在「定時排程」時才做上傳與清除檔案的動作
    if event_name == 'schedule':
        # 使用 Tailscale 分配給 NAS 的私有 IP
        upload_to_nas(
            host=os.getenv("NAS_VPN_IP"),  # 填入你 NAS 的 Tailscale IP
            port=int(os.getenv("NAS_SFTP_PORT")),
            username=os.getenv("NAS_ACCOUNT"),
            password=os.getenv("NAS_PASSWORD"),
            local_path=file_name,
            remote_path=f"{os.getenv('NAS_SFTP_PATH')}/scan_report_{current_time}.csv")

        cleanup_local_file(file_name)

if __name__ == "__main__":
    finmind_Scan_ma240()
    #yfinance_Scan_ma240()
