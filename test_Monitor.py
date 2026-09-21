import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# 🌟 1. 匯入 monitor 配置檔與策略
from monitor.config import PARAM_PROFILES
from monitor.qiantang_monitor import (
    mon_qiantang_ni_diu_wo_jian,   # 你丟我撿
    mon_qiantang_tian_nv_san_hua,  # 天女散花
    mon_qiantang_jin_ji_du_li,     # 金雞獨立
)

# 🌟 2. 匯入 utils 工具庫 (包含重構後的 parse_monitor_stocks)
from utils import (
    get_stock_name_dict,
    parse_monitor_stocks,        # 統一股票清單解析器
    fm_get_complete_stock_data,
    save_multi_day_report,
    archive_and_cleanup,
    send_email_report,
    align_and_normalize_results,
    calculate_forward_horizon_returns
)

# =====================================================================
# 🎛️ 測試環境控制面板
# =====================================================================
CHOSEN_SOURCE = 'fm' 

TEST_START_DATE = '2024-01-01'
TEST_END_DATE   = '2025-09-30'

# ---------------------------------------------------------------------
# 模式 A：CSV 檔案載入模式
# STOCK_MODE = 'csv'
# STOCK_INPUT = 'watch_list.csv'

# 模式 B：自訂 List[dict] 載入模式
STOCK_MODE = 'noncsv'
STOCK_INPUT = [
    {'stock_id': '2330', 'name': '台積電', 'category': 'TW50'},
    {'stock_id': '3706', 'name': '神達', 'category': 'MID100'},
    {'stock_id': '2317', 'name': '鴻海', 'category': 'TW50'}
]
# ---------------------------------------------------------------------

TEST_MONITOR = [
    mon_qiantang_ni_diu_wo_jian,   # 🔥 當前測試：你丟我撿
]

DAYS_BEFORE = 365  # 歷史計算指標用的緩衝天數


def run_single_strategy_in_range(strategy_func, global_df, start_date_str, end_date_str, profiles_map=None):
    """在指定日期區間內，逐日監控並找出觸發訊號"""
    strat_name = strategy_func.__name__
    profiles_map = profiles_map or PARAM_PROFILES

    print("\n" + "=" * 70)
    print(f"🚀 [策略開始執行] 策略名稱：{strat_name} | 監控區間：{start_date_str} ~ {end_date_str}")
    print("=" * 70)

    collected_range_results = {}
    start_dt = pd.to_datetime(start_date_str)
    end_dt = pd.to_datetime(end_date_str)

    grouped = global_df.groupby('stock_id')

    for stock_id, group_df in grouped:
        stock_name = group_df['name'].iloc[0]
        stock_cat = group_df['category'].iloc[0]
        
        # 依據 category 匹配對應 profile 字典
        target_profile = profiles_map.get(stock_cat, profiles_map.get('default', {}))

        print("-" * 60)
        print(f"📊 正在監控個股: {stock_id} ({stock_name}) | category: {stock_cat} | 套用 Profile: {target_profile.get('name', '未命名')}")
        print("-" * 60)

        test_period_mask = (group_df['date_dt'] >= start_dt) & (group_df['date_dt'] <= end_dt)
        test_period_df = group_df.loc[test_period_mask].sort_values('date_dt')

        stock_hits = []

        for _, row in test_period_df.iterrows():
            current_dt = row['date_dt']
            current_date_str = row['date']

            history_slice = group_df[group_df['date_dt'] <= current_dt].copy()

            # 帶入 target_profile 進行檢測
            is_hit, detail_info = strategy_func(history_slice, profile=target_profile)

            if is_hit:
                print(f"  ⚡ 於 {current_date_str} 符合觸發條件 ({strat_name})")

                hit_record = {
                    "date": current_date_str,
                    "stock_id": str(stock_id),
                    "name": str(stock_name),
                    "category": str(stock_cat),
                    "strategy_name": strat_name,
                }

                if isinstance(detail_info, dict):
                    hit_record.update(detail_info)
                else:
                    hit_record["detail"] = str(detail_info)

                # 前瞻績效計算
                horizon_perf = calculate_forward_horizon_returns(stock_id, current_date_str, global_df, horizons=[3, 5, 10, 20])
                hit_record.update(horizon_perf)

                stock_hits.append(hit_record)

        if stock_hits:
            for hit in stock_hits:
                t_date = hit["date"]
                if t_date not in collected_range_results:
                    collected_range_results[t_date] = []
                collected_range_results[t_date].append(hit)

    print("\n" + "-" * 60 + "\n")
    return collected_range_results


def run_monitor_test(source, stock_source, stock_input, strategies, start_date_str, end_date_str):
    """固定區間個股監控測試器"""
    # 🌟 直接呼叫 utils 裡面的 parse_monitor_stocks
    monitor_stocks = parse_monitor_stocks(stock_source, stock_input)

    if not monitor_stocks:
        print("❌ [錯誤] 無有效的監控股票資料。")
        return

    source_label = os.path.basename(stock_input) if stock_source == 'csv' else "自訂個股清單 (List)"
    unique_stock_ids = list(set([s['stock_id'] for s in monitor_stocks]))

    print(f"🧪 [測試啟動] 模式：固定區間監控 ({start_date_str} ~ {end_date_str})")
    print(f"📡 資料來源：{source.upper()} | 監控數量：{len(unique_stock_ids)} 檔個股 ({source_label})")

    stock_name_dict, dl = get_stock_name_dict()

    fetch_start_str = (pd.to_datetime(start_date_str) - timedelta(days=DAYS_BEFORE)).strftime("%Y-%m-%d")
    fetch_end_str = (pd.to_datetime(end_date_str) + timedelta(days=60)).strftime("%Y-%m-%d")

    # ----------------------------------------------------
    # 1. 抓取價量與籌碼數據，並對齊 category
    # ----------------------------------------------------
    print(f"📡 正在抓取全段歷史與籌碼資料 ({fetch_start_str} ~ {fetch_end_str})...")

    if source.lower() == 'fm':
        global_df = fm_get_complete_stock_data(dl, unique_stock_ids, fetch_start_str, fetch_end_str)

        # 併入 category
        df_meta = pd.DataFrame(monitor_stocks)
        if not global_df.empty:
            global_df = pd.merge(global_df, df_meta[['stock_id', 'category']], on='stock_id', how='left')
            print("🏷️ [類別載入成功] category 欄位已完美對齊至交易資料中！")
    else:
        raise ValueError("❌ 測試錢塘潮策略請務必將 CHOSEN_SOURCE 設定為 'fm'")

    if global_df.empty:
        print(f"❌ [{source.upper()} 測試失敗] 抓取歷史資料為空！")
        return

    global_df['date_dt'] = pd.to_datetime(global_df['date'])

    # ----------------------------------------------------
    # 2. 執行監控與產出報表
    # ----------------------------------------------------
    for strategy_func in strategies:
        strat_name = strategy_func.__name__

        collected_range_results = run_single_strategy_in_range(
            strategy_func, global_df, start_date_str, end_date_str, profiles_map=PARAM_PROFILES
        )

        if collected_range_results:
            priority_keys = ["date", "stock_id", "name", "category", "strategy_name"]
            collected_range_results = align_and_normalize_results(collected_range_results, priority_keys=priority_keys)

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
                    archive_and_cleanup(local_file_path=csv_path, remote_path=remote_test_path)
                    print(f"🚀 [{strat_name} NAS 同步成功] 檔案已送達遠端：{remote_filename}")
                except Exception as e:
                    print(f"⚠️ [{strat_name} 自動封存/上傳失敗] 錯誤: {e}")
        else:
            print(f"ℹ️ 策略 [{strat_name}] 在 {start_date_str} ~ {end_date_str} 區間內皆無符合之股票。")

    print(f"\n🎉 監控測試任務已全部執行完畢！")


if __name__ == "__main__":
    print("=== 進入固定區間個股監控測試環境 ===")

    run_monitor_test(
        source=CHOSEN_SOURCE,
        stock_source=STOCK_MODE,
        stock_input=STOCK_INPUT,
        strategies=TEST_MONITOR,
        start_date_str=TEST_START_DATE,
        end_date_str=TEST_END_DATE
    )
