#testMonitor.py
import os
import pandas as pd

from datetime import datetime, timedelta, timezone
from scanstock.scanstock import scan_stocks_df_list

# 匯入您要測試的策略
from monitor.monitor import mon_high_vol_exit, mon_ma5_break_advanced
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
    calculate_one_year_extremes,
    align_and_normalize_results,
    get_fm_trading_days,
    process_monitor_stock_data,
    yf_fetch_monitor_stocks,
    calculate_forward_horizon_returns
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

TEST_MONITOR = [mon_high_vol_exit, mon_ma5_break_advanced]

DAYS_BEFORE = 365
DAYS_AFTER = 548

def run_single_strategy(strategy_func, global_df):
    """將單一策略的完整回測與迴圈邏輯獨立為乾淨的子函數"""
    strat_name = strategy_func.__name__
    print("\n" + "=" * 70)
    print(f"🚀 [策略開始執行] 函數名稱：{strat_name}")
    print("=" * 70)

    collected_range_results = {}
    grouped = global_df.groupby(['stock_id', 'trigger_date'])

    for (stock_id, trigger_date), group_df in grouped:
        print("-" * 60)
        print(f"📊 股票代號: {stock_id} | 觸發日期: {trigger_date} | 執行策略: {strat_name}")
        print("-" * 60)
    
        trigger_dt = datetime.strptime(str(trigger_date).replace('-', '/'), '%Y/%m/%d')
        one_year_later_dt = trigger_dt + timedelta(days=365)
    
        mask = (group_df['date_dt'] >= trigger_dt) & (group_df['date_dt'] <= one_year_later_dt)
        trigger_period_df = group_df.loc[mask].sort_values('date_dt')
    
        stock_hits = []
    
        for _, row in trigger_period_df.iterrows():
            current_dt = row['date_dt']
            current_date_str = row['date']
        
            history_slice = group_df[group_df['date_dt'] <= current_dt].copy()
        
            # 透過函數指標動態呼叫當前策略
            is_hit, detail_info = strategy_func(history_slice)
        
            if is_hit:
                print(f"  ⚡ 於 {current_date_str} 符合條件 ({strat_name})")
                print(f"{detail_info}\n\n")
            
                hit_record = {
                    "觸發日期": str(trigger_date),
                    "代號": str(stock_id),
                    "名稱": str(group_df['name'].iloc[0]) if 'name' in group_df.columns else "",
                    "符合條件日期": str(current_date_str),
                    "策略名稱": strat_name,
                }
            
                if isinstance(detail_info, dict):
                    hit_record.update(detail_info)
                else:
                    hit_record["詳細資訊"] = str(detail_info)

                # 計算觸發後多個時間視野的前瞻績效並加入紀錄
                horizon_perf = calculate_forward_horizon_returns(stock_id, current_date_str, global_df, horizons=[3, 5, 10, 20])
                hit_record.update(horizon_perf)
            
                stock_hits.append(hit_record)
        
        if stock_hits:
            key_str = str(trigger_date)
            if key_str not in collected_range_results:
                collected_range_results[key_str] = []
            collected_range_results[key_str].extend(stock_hits)
        
    print("\n" + "-" * 60 + "\n")
    return collected_range_results

def run_monitor_test(source, stock_source, monitor_stock_data, strategies):
    """通用策略測試器（支援單日/連續區間自動回測）"""
    tz_tw = timezone(timedelta(hours=8))
    
    if stock_source == 'csv':
        monitor_stocks = process_monitor_stock_data(monitor_stock_data)
        source_label = os.path.basename(monitor_stock_data)
    else:
        source_label = "CustomList"
   
    earliest_date_str = min(monitor_stocks, key=lambda x: datetime.strptime(x['觸發日期'], '%Y/%m/%d'))['觸發日期']
    latest_date_str = max(monitor_stocks, key=lambda x: datetime.strptime(x['觸發日期'], '%Y/%m/%d'))['觸發日期']
  
    mode_label = f"區間測試 ({earliest_date_str} ~ {latest_date_str})"
    print(f"🧪 [測試啟動] 模式：{mode_label} | 來源：{source.upper()} | 標的：{source_label}")

    stock_name_dict, dl = get_stock_name_dict()
    
    latest_dt = datetime.strptime(latest_date_str.replace('/', '-'), "%Y-%m-%d")
    earliest_dt = datetime.strptime(earliest_date_str.replace('/', '-'), "%Y-%m-%d")

    fetch_end_str = (latest_dt + timedelta(days=DAYS_AFTER)).strftime("%Y-%m-%d")   
    fetch_start_str = (earliest_dt - timedelta(days=DAYS_BEFORE)).strftime("%Y-%m-%d")
    
    # ----------------------------------------------------
    # 1. 在抓取個股歷史數據時，同時抓取大盤指數
    # ----------------------------------------------------
    print(f"📡 正在抓取全段歷史數據緩衝與大盤指數 ({fetch_start_str} ~ {fetch_end_str})...")
    if source.lower() == 'yf':
        global_df = yf_fetch_monitor_stocks(monitor_stocks, days_before=DAYS_BEFORE, days_after=DAYS_AFTER)
        market_df = yf_fetch_all_stocks(['^TWII'], fetch_start_str, fetch_end_str)
    elif source.lower() == 'fm':
        market_df = fm_fetch_all_stocks(dl, ['TAIEX'], fetch_start_str, fetch_end_str)
    else:
        raise ValueError("❌ 未知的資料來源設定，僅支援 'yf' 或 'fm'")
    
    if global_df.empty:
        print(f"❌ [{source.upper()} 測試失敗] 抓取歷史資料為空！")
        return

    global_df['date_dt'] = pd.to_datetime(global_df['date'])

    # 透過迴圈調用子函數執行每一個策略
    for strategy_func in strategies:
        strat_name = strategy_func.__name__
        
        # 🌟 呼叫獨立的單一策略回測函數
        collected_range_results = run_single_strategy(strategy_func, global_df)

        # =====================================================================
        # 📊 產出 CSV 報表、發送郵件與上傳 NAS 區段
        # =====================================================================
        if collected_range_results:
            priority_keys_testscan = [
                "觸發日期",
                "代號",
                "名稱",
                "符合條件日期",
                "策略名稱",
                "收盤",
                "策略狀態",
                "停損價",
                "1Y內最高績效",
                "1Y內最低績效"
            ]
        
            collected_range_results = align_and_normalize_results(collected_range_results, priority_keys=priority_keys_testscan)
        
            output_name = f"{strat_name}_report"
            now_time = datetime.now(timezone(timedelta(hours=8)))
        
            csv_path = save_multi_day_report(collected_range_results, output_name, now_time)
            print(f"✅ [{strat_name} 報表產出成功] 已輸出：{csv_path}")

            send_email_report(csv_path)

            if csv_path and os.path.exists(csv_path):
                current_time_str = now_time.strftime("%Y%m%d_%H%M")
                remote_filename = f"{output_name}_{current_time_str}.csv"
                remote_test_path = f"{os.getenv('NAS_SFTP_PATH')}/monitor_reports/{remote_filename}"
            
                try:
                    print(f"📦 啟動 [{strat_name}] 遠端封存與清理流程...")
                    archive_and_cleanup(
                        local_file_path=csv_path,
                        remote_path=remote_test_path
                    )
                    print(f"🚀 [{strat_name} NAS 同步成功] 檔案已送達遠端：{remote_filename}")
                except Exception as e:
                    print(f"⚠️ [{strat_name} 自動封存/上傳失敗] 錯誤: {e}")
        else:
            print(f"ℹ️ 策略 [{strat_name}] 在整個測試期間內皆無符合之股票，不產出報表與上傳。")

    print(f"\n🎉 所有的測試任務已全部執行完畢！")

if __name__ == "__main__":
    print("=== 進入本機自動化測試環境 ===")
    
    run_monitor_test(
        source=CHOSEN_SOURCE,
        stock_source=STOCK_MODE,
        monitor_stock_data=STOCK_INPUT,
        strategies=TEST_MONITOR
    )
