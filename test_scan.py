# test_scan.py
import os
from datetime import datetime, timedelta, timezone
from scanstock.scanstock import scan_stocks_df_list

# 匯入您要測試的策略
from strategy.strat_right_side import st_bottom_u_turn
from strategy.advanced_ma240 import st_advanced_ma240_df_up
from strategy.near_ma240 import st_near_ma240_df

# =====================================================================
# 🎛️ 測試環境控制面板（本機測試直接在這裡修改參數）
# =====================================================================

# 1. 一鍵切換資料源：可輸入 'yf' (yfinance) 或 'fm' (FinMind)
CHOSEN_SOURCE = 'yf' 

# 2. 設定測試日期
#    - 🔍 測試單日：START 填日期，END 填 None
#    - 📈 測試區間：START 填起始日，END 填結束日（會逐日掃描，自動跳過週末）
TEST_START_DATE = '2026-03-01'
TEST_END_DATE   = '2026-04-30'  # 設為 None 則只跑單日測試

# 3. 設定股票來源：可選 'list' (自訂代號列表) 或 'csv' (讀取指定的檔案)
STOCK_MODE = 'list'
STOCK_INPUT = ['2377', '4583', '2357', '5269', '2330']  
# STOCK_INPUT = 'data/TW50.csv'                          # 若想吃 CSV 請取消註解此行

# 4. 勾選這次要加入測試的策略列表
TEST_STRATEGIES = [st_bottom_u_turn]

# =====================================================================

from utils import (
    get_stock_name_dict,
    parse_stock_ids,
    send_report,
    yf_fetch_all_stocks,
    fm_fetch_all_stocks,
    archive_and_cleanup
)

def run_strategy_test(source, start_date_str, end_date_str, stock_source, stock_data, strategies):
    """通用策略測試器（支援單日/連續區間自動回測）"""
    tz_tw = timezone(timedelta(hours=8))
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)
        if end_date < start_date:
            raise ValueError("❌ 結束日期不能小於開始日期！")
        is_range_test = True
    else:
        end_date = start_date
        is_range_test = False

    if stock_source == 'csv':
        stock_ids = parse_stock_ids(stock_data)
        source_label = os.path.basename(stock_data)
    else:
        stock_ids = stock_data if stock_data else ['2377', '2357']
        source_label = f"CustomList({len(stock_ids)}檔)"

    mode_label = f"區間測試 ({start_date_str} ~ {end_date_str})" if is_range_test else f"單日測試 ({start_date_str})"
    print(f"🧪 [測試啟動] 模式：{mode_label} | 來源：{source.upper()} | 標的：{source_label}")

    stock_name_dict, dl = get_stock_name_dict()
    
    fetch_end_str = end_date.strftime("%Y-%m-%d")
    fetch_start_str = (start_date - timedelta(days=500)).strftime("%Y-%m-%d")
    
    print(f"📡 正在抓取全段歷史數據緩衝 ({fetch_start_str} ~ {fetch_end_str})...")
    if source.lower() == 'yf':
        global_df = yf_fetch_all_stocks(stock_ids, fetch_start_str, fetch_end_str)
        status_col = '策略狀態'
    elif source.lower() == 'fm':
        global_df = fm_fetch_all_stocks(dl, stock_ids, fetch_start_str, fetch_end_str)
        status_col = '觸發策略'
    else:
        raise ValueError("❌ 未知的資料來源設定，僅支援 'yf' 或 'fm'")

    if global_df.empty:
        print(f"❌ [{source.upper()} 測試失敗] 抓取歷史資料為空！")
        return

    # 逐日歷算與傳輸流程
    current_day = start_date
    while current_day <= end_date:
        if current_day.weekday() >= 5: # 自動跳過週六、週日
            current_day += timedelta(days=1)
            continue
            
        day_str = current_day.strftime("%Y-%m-%d")
        print(f"\n⚡ 正在分析日期: {day_str}...")

        day_data_cutoff = current_day.replace(hour=23, minute=59, second=59)
        all_df_slice = global_df[global_df['date'] <= day_data_cutoff.strftime("%Y-%m-%d")]

        if all_df_slice.empty:
            print(f"⚠️ {day_str} 數據切片為空，跳過本交易日。")
            current_day += timedelta(days=1)
            continue

        run_single_day_core(
            test_time=current_day,
            stock_ids=stock_ids,
            stock_name_dict=stock_name_dict,
            all_df=all_df_slice,
            strategies=strategies,
            source=source,
            status_col=status_col
        )

        current_day += timedelta(days=1)
        
    print(f"\n🎉 所有的測試任務已全部執行完畢！")

def run_single_day_core(test_time, stock_ids, stock_name_dict, all_df, strategies, source, status_col):
    """單日掃描核心：計算策略、生本地 CSV、發 LINE，並透過正式架構封存與上傳"""
    results = scan_stocks_df_list(stock_ids, strategies, all_df, stock_name_dict)
    
    output_name = f"{source.lower()}_test"
    csv_path = send_report(results, output_name, test_time, status_col_name=status_col)
    
    # 🟢 完全沿用正式環境的生命週期（上傳、移轉、清理）
    if csv_path and os.path.exists(csv_path):
        current_time_str = test_time.strftime("%Y%m%d_%H%M")
        remote_filename = f"{output_name}_report_{current_time_str}.csv"
        
        # 將遠端目標導向測試專用資料夾 test_reports
        remote_test_path = f"{os.getenv('NAS_SFTP_PATH')}/test_reports/{remote_filename}"
        
        try:
            print(f"📦 啟動自動化封存與清理流程 (目標：測試資料夾)...")
            archive_and_cleanup(
                local_file_path=csv_path,
                remote_path=remote_test_path
            )
            print(f"🚀 [NAS 同步成功] 檔案已安全送達遠端：test_reports/{remote_filename}")
        except Exception as e:
            print(f"⚠️ [自動封存/上傳失敗] 請檢查 .env 設定或連線。錯誤: {e}")
    else:
        print(f"ℹ️ 本日無符合策略股票，不產出報表。")


if __name__ == "__main__":
    print("=== 進入本機自動化測試環境 ===")
    
    run_strategy_test(
        source=CHOSEN_SOURCE,
        start_date_str=TEST_START_DATE,
        end_date_str=TEST_END_DATE,
        stock_source=STOCK_MODE,
        stock_data=STOCK_INPUT,
        strategies=TEST_STRATEGIES
    )
