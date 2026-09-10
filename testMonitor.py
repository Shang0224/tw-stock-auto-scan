#testMonitor.py
import os
import pandas as pd

from datetime import datetime, timedelta, timezone
from scanstock.scanstock import scan_stocks_df_list

# 匯入您要測試的策略
from monitor.monitor import mon_high_vol_exit
#from strategy.bottom_rebound import st_bottom_v_turn, st_u_bottom, st_bottom_v_turn_2026072602
#from strategy.advanced_ma240 import st_advanced_ma240_df_up
#from strategy.near_ma240 import st_near_ma240_df

# 🌟 完美導入你專屬的 utils 程式庫工具
from utils import (
    get_stock_name_dict,
    parse_stock_ids,
    yf_fetch_all_stocks,
    fm_fetch_all_stocks,
    save_multi_day_report, # 🌟 新增：專門處理多日格式化的存檔函數
    archive_and_cleanup,   # 負責排程專用的備份與清理
    send_email_report,
    save_multi_day_report,
    calculate_one_year_extremes,
    align_and_normalize_results,
    get_fm_trading_days,
    process_monitor_stock_data,
    yf_fetch_monitor_stocks
)

# =====================================================================
# 🎛️ 測試環境控制面板
# =====================================================================
CHOSEN_SOURCE = 'yf' 
#CHOSEN_SOURCE = 'fm' 
TEST_START_DATE = '2024-01-01'
TEST_END_DATE   = '2025-09-30'  # 設為 None 則只跑單日測試

STOCK_MODE = 'csv' 
STOCK_INPUT = os.getenv('MONITOR_STOCK_FILES', 'data/MonitorTestingData.csv')

#STOCK_MODE = 'noncsv' 
#STOCK_INPUT = ['6191', '2377', '2408', '2449', '3044', '2353', '2404']

TEST_MONITOR = [mon_high_vol_exit]

DAYS_BEFORE = 365
DAYS_AFTER = 548

def run_monitor_test(source, stock_source, monitor_stock_data, strategies):
    """通用策略測試器（支援單日/連續區間自動回測）"""
    tz_tw = timezone(timedelta(hours=8))
    
    if stock_source == 'csv':
        monitor_stocks = process_monitor_stock_data(monitor_stock_data)
        source_label = os.path.basename(monitor_stock_data)
    #else:
    #    stock_ids = stock_data if stock_data else ['2377', '2357']
    #    source_label = f"CustomList({len(stock_ids)}檔)"
   
    # 直接取得最早與最晚的觸發日期字串（使用 datetime 確保未補零的日期格式能正確比較）
    earliest_date_str = min(monitor_stocks, key=lambda x: datetime.strptime(x['觸發日期'], '%Y/%m/%d'))['觸發日期']
    latest_date_str = max(monitor_stocks, key=lambda x: datetime.strptime(x['觸發日期'], '%Y/%m/%d'))['觸發日期']
  

    mode_label = f"區間測試 ({earliest_date_str} ~ {latest_date_str})"
    print(f"🧪 [測試啟動] 模式：{mode_label} | 來源：{source.upper()} | 標的：{source_label}")

    stock_name_dict, dl = get_stock_name_dict()
    
    #fetch_end_str = end_date.strftime("%Y-%m-%d")

    # 用以下區間取得大盤資料的時間區間
    latest_dt = datetime.strptime(latest_date_str.replace('/', '-'), "%Y-%m-%d")
    earliest_dt = datetime.strptime(earliest_date_str.replace('/', '-'), "%Y-%m-%d")

    # 2. 加上 timedelta 後再格式化為字串
    fetch_end_str = (latest_dt + timedelta(days=DAYS_AFTER)).strftime("%Y-%m-%d")   
    fetch_start_str = (earliest_dt - timedelta(days=DAYS_BEFORE)).strftime("%Y-%m-%d")
    
    # ----------------------------------------------------
    # 1. 在抓取個股歷史數據時，同時抓取大盤指數 (以 Yahoo Finance ^TWII 為例)
    # ----------------------------------------------------
    print(f"📡 正在抓取全段歷史數據緩衝與大盤指數 ({fetch_start_str} ~ {fetch_end_str})...")
    if source.lower() == 'yf':
        global_df = yf_fetch_monitor_stocks(monitor_stocks, days_before=DAYS_BEFORE, days_after=DAYS_AFTER)
        # 🌟 同步抓取台股加權指數 (^TWII) 作為大盤基準
        market_df = yf_fetch_all_stocks(['^TWII'], fetch_start_str, fetch_end_str)
    elif source.lower() == 'fm':
        #global_df = yf_fetch_monitor_stocks(dl, stock_ids, fetch_start_str, fetch_end_str)
        # FinMind 對應的大盤代碼，可依你的 FinMind 資料源調整（例如 'TAIEX' 或指數代碼）
        market_df = fm_fetch_all_stocks(dl, ['TAIEX'], fetch_start_str, fetch_end_str)
    else:
        raise ValueError("❌ 未知的資料來源設定，僅支援 'yf' 或 'fm'")
    
    if global_df.empty:
        print(f"❌ [{source.upper()} 測試失敗] 抓取歷史資料為空！")
        return

    # 🌟 【關鍵優化】在迴圈外一次性計算完整大盤的 MA240 與布林值
    market_df = market_df.copy()
    market_df['date_str'] = pd.to_datetime(market_df['date']).dt.strftime("%Y-%m-%d")
    market_df['MA240'] = market_df['close'].rolling(240).mean()
    
    # 預先算好每一天是否在年線之上 (若 MA240 為 NaN 則預設為 True 或 False 視需求而定)
    market_df['market_above_ma240'] = market_df['close'] > market_df['MA240']
    
    # 建立一個「日期字串 -> 是否在年線之上」的快速查詢字典（Dictionary Look-up）
    # 如果資料量大，用字典查閱的速度極快
    market_dict = market_df.set_index('date_str')['market_above_ma240'].to_dict()
    market_ma_dict = market_df.set_index('date_str')['MA240'].to_dict()

    # 🌟 【新增】先批次取得 FinMind 交易日清單（涵蓋歷史區間 + 400天緩衝）
    print("📡 正在向 FinMind 取得台股交易日歷行事曆...")
    trading_days_set = get_fm_trading_days(fetch_start_str, fetch_end_str)
    
    if trading_days_set:
        print(f"✅ 成功載入 FinMind 交易日清單，共 {len(trading_days_set)} 個交易日。")
    else:
        print("⚠️ 無法取得 FinMind 交易日，將自動退回僅過濾週末（Saturday/Sunday）的預設機制。")
    
    if not global_df.empty:
        # 依照股票代號與觸發日期進行分組（因為同一檔股票可能在不同年份都有觸發紀錄）
        grouped = final_df.groupby(['stock_id', 'trigger_date'])
    
        for (stock_id, trigger_date), group_df in grouped:
            print("=" * 60)
            print(f"📊 股票代號: {stock_id} | 觸發日期: {trigger_date} | 共 {len(group_df)} 筆交易日資料")
            print("=" * 60)
        
            # 印出該股票該區間的資料（此處印出前 5 筆示範，若要全部印出可移除 .head()）
            print(group_df.head())
            print("\n" + "-" * 60 + "\n")

    print(f"\n🎉 所有的測試任務已全部執行完畢！")

if __name__ == "__main__":
    print("=== 進入本機自動化測試環境 ===")
    
    run_monitor_test(
        source=CHOSEN_SOURCE,
        stock_source=STOCK_MODE,
        monitor_stock_data=STOCK_INPUT,
        strategies=TEST_MONITOR
    )

