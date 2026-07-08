# main.py
import yfinance as yf
import pandas as pd
import os
import requests

from FinMind.data import DataLoader
from datetime import datetime, timedelta, timezone
from untils.untils import send_line_message, fm_fetch_all_stocks, yf_fetch_all_stocks, send_email_with_csv, upload_to_nas, cleanup_local_file
from strategy.near_ma240 import st_near_ma240, st_near_ma240_df
from scanstock.scanstock import scan_stocks_df_list
from strategy.advanced_ma240 import st_advanced_ma240, st_advanced_ma240_df, st_advanced_ma240_df_up
from strategy.bottom_rebound import st_bottom_v_turn, st_bottom_breakout, st_bottom_consolidation
from strategy.strat_right_side import st_bottom_u_turn


# 🌟 從 utils 匯入全新整理好的工具
from utils import (
    yf_fetch_all_stocks,
    fm_fetch_all_stocks,
    parse_stock_ids,
    get_stock_name_dict,
    send_report,          # 變精簡了，只負責生報表、發 LINE
    archive_and_cleanup,   # 新增這個：負責排程專用的備份與清理
    save_scan_report,
    send_line_summary,
    send_email_report
)

from strategy.near_ma240 import st_near_ma240_df
# ... 其他策略匯入省略 ...

def yfinance_scan_ma240():
    """yfinance 雲端定時排程主程式 (測試環境：多日結果合併單一檔案，加分隔線上傳)"""
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    
    files_env = os.getenv('STOCK_FILES', 'data/MID100.csv')
    my_strategies = [st_near_ma240_df, st_bottom_v_turn, st_bottom_breakout] # 策略列表
    
    print(f"⏰ [YF 排程啟動] 日期：{tw_time.strftime('%Y-%m-%d')}, 來源：{files_env}")

    stock_name_dict, _ = get_stock_name_dict()
    stock_ids = parse_stock_ids(files_env)

    end_date = tw_time.strftime("%Y-%m-%d") 
    start_date = (tw_time - timedelta(days=500)).strftime("%Y-%m-%d")
    
    all_df = yf_fetch_all_stocks(stock_ids, start_date, end_date)  
    if all_df.empty: 
        print("⚠️ [YF 結束] 未抓取到任何資料。")
        return

    source_name = 'yfinance'

    try:        
        # 這裡會吐出所有掃描結果 (單日或多日)
        results = scan_stocks_df_list(stock_ids, my_strategies, all_df, stock_name_dict)
        
        if not results:
            print("💡 [YF 測試提示] 無符合策略標的，不產出 CSV 與上傳。")
            return

        # 🌟 建立本地輸出的 CSV 檔案路徑
        current_time = tw_time.strftime("%Y%m%d_%H%M")
        os.makedirs(f"data/{source_name}", exist_ok=True)
        csv_path = f"data/{source_name}/{source_name}_scan_report_{current_time}.csv"

        # 🌟 核心：將結果轉為 DataFrame，並依據日期分組寫入檔案
        df_all = pd.DataFrame(results)
        
        # 💡 自動偵測你的日期欄位名稱 (請依據你 results 實際的 key 修改，例如 'date', '日期' 或 '掃描日期')
        # 這裡假設欄位叫做 'date' 或 '日期'
        date_col = 'date' if 'date' in df_all.columns else ('日期' if '日期' in df_all.columns else None)

        with open(csv_path, 'w', encoding='utf-8-sig') as f:
            if date_col and len(df_all[date_col].unique()) > 1:
                # 【多日模式】：依日期分組，每組加上橫線、空行、獨立日期行
                is_first_group = True
                for date_val, group_df in df_all.groupby(date_col):
                    if not is_first_group:
                        f.write("\n\n")
                    f.write(f"==================== {date_val} ====================\n")
                    group_df.to_csv(f, index=False, header=True)
                    is_first_group = False
            else:
                # 【單日模式 / 或找不到日期欄位】：直接標準輸出
                df_all.to_csv(f, index=False, header=True)

        print(f"✅ [YF 測試成功] 報告已成功格式化輸出至：{csv_path}")

        # 🌟 修正：還是要上傳至 NAS
        prod_remote_path = f"{os.getenv('NAS_SFTP_PATH')}/{source_name}/{source_name}_scan_report_{current_time}.csv"
        print(f"📦 [備份啟動] 開始上傳至 NAS...\n遠端路徑：{prod_remote_path}")
        archive_and_cleanup(csv_path, prod_remote_path)
        
        # 測試環境下，通知（LINE、Email）保持註解關閉
        # send_line_summary(results, source_name, tw_time, status_col_name='策略狀態')
        # send_email_report(csv_path)
        
    except Exception as e:
        print(f"❌ [YF 排程例外] {e}")

def yfinance_scan_ma240_old():
    """yfinance 雲端定時排程主程式"""
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    
    files_env = os.getenv('STOCK_FILES', 'data/MID100.csv')
    my_strategies = [st_near_ma240_df, st_bottom_v_turn, st_bottom_breakout] # 策略列表
    
    print(f"⏰ [YF 排程啟動] 日期：{tw_time.strftime('%Y-%m-%d')}, 來源：{files_env}")

    stock_name_dict, _ = get_stock_name_dict()
    stock_ids = parse_stock_ids(files_env)

    end_date = tw_time.strftime("%Y-%m-%d") 
    start_date = (tw_time - timedelta(days=500)).strftime("%Y-%m-%d")
    
    all_df = yf_fetch_all_stocks(stock_ids, start_date, end_date)  
    if all_df.empty: return

    source_name = 'yfinance'

    try:        
        results = scan_stocks_df_list(stock_ids, my_strategies, all_df, stock_name_dict)
        
        # 2. 產出本地 CSV 檔案 (有股票才會產檔並回傳路徑，沒股票回傳 None)
        csv_path = save_scan_report(results, source_name, tw_time)
        
        # 3. 訊息派發：LINE 發送即時摘要 (純文字，每日必發)
        #-------------------超過line免費限制-+------暫時註解
        #send_line_summary(results, source_name, tw_time, status_col_name='策略狀態')
        
        # 4. 訊息派發：Email 發送完整報告 (依賴實體 CSV 檔案)
        send_email_report(csv_path)
        
        # 5. 後續備份與清理 (依賴實體 CSV 檔案)
        if csv_path and os.path.exists(csv_path):
            current_time = tw_time.strftime("%Y%m%d_%H%M")
            prod_remote_path = f"{os.getenv('NAS_SFTP_PATH')}/{source_name}/{source_name}_scan_report_{current_time}.csv"
            
            print(f"📦 [備份啟動] 偵測到實體報告，開始上傳至 NAS...")
            archive_and_cleanup(csv_path, prod_remote_path)
        else:
            print("💡 [備份提示] 今日無實體檔案，跳過 NAS 上傳與清理。")
        
    except Exception as e:
        print(f"❌ [YF 排程例外] {e}")


def finmind_scan_ma240():
    """FinMind 雲端定時排程主程式"""
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    
    files_env = os.getenv('STOCK_FILES', 'data/MID100.csv')
    my_strategies = [st_near_ma240_df]
    
    print(f"⏰ [FM 排程啟動] 日期：{tw_time.strftime('%Y-%m-%d')}, 來源：{files_env}")

    stock_name_dict, dl = get_stock_name_dict()
    stock_ids = parse_stock_ids(files_env)

    end_date = tw_time.strftime("%Y-%m-%d")
    start_date = (tw_time - timedelta(days=500)).strftime("%Y-%m-%d")
    
    all_df = fm_fetch_all_stocks(dl, stock_ids, start_date, end_date)
    if all_df.empty: return
        
    source_name = 'finmind'

    try:
        results = scan_stocks_df_list(stock_ids, my_strategies, all_df, stock_name_dict)
        
        # 🟢 步驟 1：產出報告、發 LINE
        csv_path = send_report(results, 'finmind', tw_time, status_col_name='觸發策略')
        
        # 🟢 步驟 2：歸檔清理
        #archive_and_cleanup(csv_path, source_name, tw_time)
        
        current_time = tw_time.strftime("%Y%m%d_%H%M")
        prod_remote_path = f"{os.getenv('NAS_SFTP_PATH')}/{source_name}/{source_name}_scan_report_{current_time}.csv"

        #         2-2. 乾乾淨淨地丟給工具執行
        archive_and_cleanup(csv_path, prod_remote_path)
        
    except Exception as e:
        print(f"❌ [FM 排程例外] {e}")


if __name__ == "__main__":
    #finmind_scan_ma240()
    yfinance_scan_ma240()

