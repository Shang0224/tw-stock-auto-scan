# main.py
import os
from datetime import datetime, timedelta, timezone
from scanstock.scanstock import scan_stocks_df_list

# 🌟 從 utils 匯入全新整理好的工具
from utils import (
    yf_fetch_all_stocks,
    fm_fetch_all_stocks,
    parse_stock_ids,
    get_stock_name_dict,
    send_report,          # 變精簡了，只負責生報表、發 LINE
    archive_and_cleanup   # 新增這個：負責排程專用的備份與清理
)

from strategy.near_ma240 import st_near_ma240_df
# ... 其他策略匯入省略 ...

def yfinance_scan_ma240():
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

    try:
        results = scan_stocks_df_list(stock_ids, my_strategies, all_df, stock_name_dict)
        
        # 🟢 步驟 1：產出報告、發 LINE、拿到本地產出的 CSV 檔案路徑
        csv_path = send_report(results, 'yfinance', tw_time, status_col_name='策略狀態')
        
        # 🟢 步驟 2：正式排程環境下，順著把檔案丟上 NAS 並清除本地暫存
        archive_and_cleanup(csv_path, 'yfinance', tw_time)
        
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

    try:
        results = scan_stocks_df_list(stock_ids, my_strategies, all_df, stock_name_dict)
        
        # 🟢 步驟 1：產出報告、發 LINE
        csv_path = send_report(results, 'finmind', tw_time, status_col_name='觸發策略')
        
        # 🟢 步驟 2：歸檔清理
        archive_and_cleanup(csv_path, 'finmind', tw_time)
        
    except Exception as e:
        print(f"❌ [FM 排程例外] {e}")


if __name__ == "__main__":
    finmind_scan_ma240()
    yfinance_scan_ma240()

