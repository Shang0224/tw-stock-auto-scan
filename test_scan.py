# test_scan.py
import os
from datetime import datetime, timedelta, timezone
from scanstock.scanstock import scan_stocks_df_list

# 匯入您要測試的策略
from strategy.strat_right_side import st_bottom_u_turn, st_bottom_u_turn_v20260703, st_bottom_u_turn_v2026070301, st_bottom_u_turn_2026070302, st_bottom_u_turn_with_memory
from strategy.bottom_rebound import st_bottom_v_turn, st_bottom_consolidation, st_bottom_breakout
from strategy.advanced_ma240 import st_advanced_ma240_df_up
from strategy.near_ma240 import st_near_ma240_df

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
    calculate_forward_performance
)

# =====================================================================
# 🎛️ 測試環境控制面板
# =====================================================================
CHOSEN_SOURCE = 'yf' 
TEST_START_DATE = '2022-10-01'
TEST_END_DATE   = '2023-05-08'  # 設為 None 則只跑單日測試

STOCK_MODE = 'csv' 
STOCK_INPUT = os.getenv('STOCK_FILES', 'data/MID100.csv')

#STOCK_MODE = 'noncsv' 
#STOCK_INPUT = ['3005', '2353', '6191']

TEST_STRATEGIES = [st_bottom_u_turn_with_memory]
#TEST_STRATEGIES = [st_bottom_u_turn, st_bottom_u_turn_v20260703] #, st_bottom_v_turn, st_bottom_consolidation, st_bottom_breakout]
#TEST_STRATEGIES = [st_bottom_u_turn_v2026070301, st_bottom_u_turn_2026070302]

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
    
    #fetch_end_str = end_date.strftime("%Y-%m-%d")
    # 建議將遠端抓取資料的結束時間往後推 400 天，確保完整的未來績效能被計算到
    fetch_end_str = (end_date + timedelta(days=400)).strftime("%Y-%m-%d")
    
    fetch_start_str = (start_date - timedelta(days=500)).strftime("%Y-%m-%d")
    
    print(f"📡 正在抓取全段歷史數據緩衝 ({fetch_start_str} ~ {fetch_end_str})...")
    if source.lower() == 'yf':
        global_df = yf_fetch_all_stocks(stock_ids, fetch_start_str, fetch_end_str)
    elif source.lower() == 'fm':
        global_df = fm_fetch_all_stocks(dl, stock_ids, fetch_start_str, fetch_end_str)
    else:
        raise ValueError("❌ 未知的資料來源設定，僅支援 'yf' 或 'fm'")

    if global_df.empty:
        print(f"❌ [{source.upper()} 測試失敗] 抓取歷史資料為空！")
        return

    # 用於儲存每日結果的字典
    collected_range_results = {}

    # 逐日歷算迴圈
    current_day = start_date
    while current_day <= end_date:
        if current_day.weekday() >= 5:  # 自動跳過週末
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

        day_results = scan_stocks_df_list(stock_ids, strategies, all_df_slice, stock_name_dict)

        #if day_results:
         #   print(f"🔍 {day_str} 掃描完成，找到 {len(day_results)} 檔符合標的。")
          #  collected_range_results[day_str] = day_results
        #else:         
        #    print(f"🔍 {day_str} 掃描完成，無符合標的。")

        if day_results:
            # 💡 這裡直接調用來自 utils 的績效計算工具
            for hit in day_results:
                perf = calculate_forward_performance(hit["代號"], day_str, global_df)
                hit.update(perf)

            print(f"🔍 {day_str} 掃描完成，找到 {len(day_results)} 檔符合標的（已完成績效追蹤）。")
            collected_range_results[day_str] = day_results
        else:
            print(f"🔍 {day_str} 掃描完成，無符合標的。")

        current_day += timedelta(days=1)
        
    print(f"\n📊 [分析完畢] 開始整合數據、產出報表並準備上船...")

    # =====================================================================
    # 🌟 呼叫全新的工具函數
    # =====================================================================
    if collected_range_results:
        output_name = f"{source.lower()}_test"
        now_time = datetime.now(timezone(timedelta(hours=8)))
        
        # 1. 🌟 直接調用 utils 的新函數，一行程式碼搞定格式化產檔
        csv_path = save_multi_day_report(collected_range_results, output_name, now_time)
        print(f"✅ [報表產出成功] 已透過 utils.save_multi_day_report 格式化輸出：{csv_path}")

        # 2. 訊息派發：Email 發送完整報告
        send_email_report(csv_path)

        # 3. 🟢 呼叫 utils 內的封存與清理工具上傳 NAS
        if os.path.exists(csv_path):
            current_time_str = now_time.strftime("%Y%m%d_%H%M")
            if is_range_test:
                remote_filename = f"{output_name}_range_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
            else:
                remote_filename = f"{output_name}_report_{current_time_str}.csv"
                
            remote_test_path = f"{os.getenv('NAS_SFTP_PATH')}/test_reports/{remote_filename}"
            
            try:
                print(f"📦 啟動 utils 遠端封存與清理流程...")
                archive_and_cleanup(
                    local_file_path=csv_path,
                    remote_path=remote_test_path
                )
                print(f"🚀 [NAS 同步成功] 檔案已送達遠端：test_reports/{remote_filename}")
            except Exception as e:
                print(f"⚠️ [自動封存/上傳失敗] 錯誤: {e}")
    else:
        print(f"ℹ️ 整個測試期間內皆無符合策略之股票，不產出報表與上傳。")

    print(f"\n🎉 所有的測試任務已全部執行完畢！")

def run_strategy_test_old(source, start_date_str, end_date_str, stock_source, stock_data, strategies):
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

    #2. 產出本地 CSV 檔案 (有股票才會產檔並回傳路徑，沒股票回傳 None)
    csv_path = save_scan_report(results, output_name, test_time)       
    
    #csv_path = send_report(results, output_name, test_time, status_col_name=status_col)

    # 3. 訊息派發：LINE 發送即時摘要 (純文字，每日必發)
    #-------------------超過line免費限制-+------暫時註解
    #send_line_summary(results, source_name, tw_time, status_col_name='策略狀態')
        
    # 4. 訊息派發：Email 發送完整報告 (依賴實體 CSV 檔案)
    send_email_report(csv_path)
        
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
