# test_qiantang_Strategy.py
"""
錢塘潮選股系統 - 多方選股策略測試進入點 (test_qiantang_Strategy.py)
說明：對齊 test_Monitor.py 架構，支援傳參控制與單點測試錢塘潮 7 大多方選股公式。
"""

import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# 1. 匯入核心執行引擎
from monitor.engine import (
    preprocess_all_technical_indicators,
    scan_single_stock_monitors,
    PARAM_PROFILES,
)

# 2. 匯入錢塘潮多方選股策略 (來自 strategy 套件)
from strategy.qiantang_strategies import (
    st_qiantang_f1_spt_growth,       # 筆張現形
    st_qiantang_f2_volume_breakout,  # 出量上輕
    st_qiantang_f3_after_shakeout,   # 洗盤後
    st_qiantang_f4_strong_rise,      # 強力上
    st_qiantang_f5_major_buy_easy,   # 主外上輕
    st_qiantang_f6_flower,           # 一朵花
    st_qiantang_f7_super_stock,      # 飆股
)

# 3. 匯入工具庫
from utils import (
    get_stock_name_dict,
    parse_monitor_stocks,
    fm_get_complete_stock_data,
    save_multi_day_report,
    archive_and_cleanup,
    align_and_normalize_results,
    calculate_forward_horizon_returns,
    get_fm_trading_days,
)

# =====================================================================
# 🎛️ 多方策略測試控制面板 (加/減 # 註解即可自由切換想測試的策略)
# =====================================================================
CHOSEN_SOURCE = "fm"
TEST_START_DATE = "2024-01-01"
TEST_END_DATE = "2025-09-30"

STOCK_MODE = "noncsv"
STOCK_INPUT = [
    {"stock_id": "3706", "name": "神達", "category": "MID100"},
    {"stock_id": "2330", "name": "台積電", "category": "TW50"},
    {"stock_id": "2317", "name": "鴻海", "category": "TW50"},
]

# 測試策略清單：直接註解/取消註解即可切換開關
TEST_QIANTANG_STRATEGY = [
    st_qiantang_f1_spt_growth,       # 筆張現形
    st_qiantang_f2_volume_breakout,  # 出量上輕
    st_qiantang_f3_after_shakeout,   # 洗盤後
    st_qiantang_f4_strong_rise,      # 強力上
    st_qiantang_f5_major_buy_easy,   # 主外上輕
    st_qiantang_f6_flower,           # 一朵花
    st_qiantang_f7_super_stock,      # 飆股
]

DAYS_BEFORE = 365


def scan_qiantang_strategy_day(day_str, all_df_slice, monitor_stocks, strategies, profiles_map=PARAM_PROFILES):
    """單日選股掃描核心"""
    day_hits = []
    stock_meta_map = {str(s["stock_id"]): s for s in monitor_stocks}
    grouped = all_df_slice.groupby("stock_id")

    for stock_id, group_df in grouped:
        sid = str(stock_id)
        if sid not in stock_meta_map:
            continue
        meta = stock_meta_map[sid]
        stock_name = meta.get("name", sid)
        stock_cat = meta.get("category", "MID100")

        df_single = group_df.sort_values("date").copy()

        # 呼叫引擎執行策略檢測
        hits = scan_single_stock_monitors(
            df_single=df_single,
            category=stock_cat,
            monitor_list=strategies,
            param_profiles=profiles_map,
        )

        for hit in hits:
            hit_record = {
                "date": day_str,
                "stock_id": sid,
                "name": str(stock_name),
            }
            hit_record.update(hit)
            day_hits.append(hit_record)

    return day_hits


def run_qiantang_strategy_test(source, stock_source, stock_input, strategies, start_date_str, end_date_str):
    """錢塘潮多方選股測試主流程"""
    if not strategies:
        raise ValueError("❌ [錯誤] 未指定 TEST_QIANTANG_STRATEGY 策略清單，請至少取消註解一個選股公式！")

    tz_tw = timezone(timedelta(hours=8))
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)

    monitor_stocks = parse_monitor_stocks(stock_source, stock_input)
    unique_stock_ids = list(set([str(s["stock_id"]) for s in monitor_stocks]))

    print(f"🧪 [錢塘潮選股測試啟動] 區間：{start_date_str} ~ {end_date_str}")
    print(f"📡 監控個股數量：{len(unique_stock_ids)} 檔 | 執行策略數：{len(strategies)} 個")

    fetch_start_str = (start_date - timedelta(days=DAYS_BEFORE)).strftime("%Y-%m-%d")
    fetch_end_str = (end_date + timedelta(days=60)).strftime("%Y-%m-%d")

    stock_name_dict, dl = get_stock_name_dict()
    global_df = fm_get_complete_stock_data(dl, unique_stock_ids, fetch_start_str, fetch_end_str)

    if global_df.empty:
        print("❌ 資料抓取失敗，全域 DataFrame 為空！")
        return

    print("⚡ 正在執行全域技術面與籌碼替代指標預處理...")
    global_df = preprocess_all_technical_indicators(global_df)
    print("✅ 指標預處理完全成功！")

    trading_days_set = get_fm_trading_days(fetch_start_str, fetch_end_str)

    collected_range_results = {}
    current_day = start_date

    while current_day <= end_date:
        day_str = current_day.strftime("%Y-%m-%d")

        if trading_days_set and day_str not in trading_days_set:
            current_day += timedelta(days=1)
            continue

        day_data_cutoff = current_day.replace(hour=23, minute=59, second=59)
        all_df_slice = global_df[global_df["date"] <= day_data_cutoff.strftime("%Y-%m-%d")].copy()

        if all_df_slice.empty:
            current_day += timedelta(days=1)
            continue

        day_hits = scan_qiantang_strategy_day(
            day_str=day_str,
            all_df_slice=all_df_slice,
            monitor_stocks=monitor_stocks,
            strategies=strategies,
        )

        if day_hits:
            print(f"⚡ [{day_str}] 觸發 {len(day_hits)} 筆選股訊號。")
            for hit in day_hits:
                horizon_perf = calculate_forward_horizon_returns(
                    hit["stock_id"], day_str, global_df, horizons=[3, 5, 10, 20]
                )
                hit.update(horizon_perf)
            collected_range_results[day_str] = day_hits

        current_day += timedelta(days=1)

    if collected_range_results:
        priority_keys = ["date", "stock_id", "name", "category", "strategy_name"]
        collected_range_results = align_and_normalize_results(collected_range_results, priority_keys=priority_keys)

        output_name = "qiantang_strategy_scan"
        now_time = datetime.now(tz_tw)
        csv_path = save_multi_day_report(collected_range_results, output_name, now_time)
        print(f"🎉 測試完成！選股結果報表已匯出至：{csv_path}")


if __name__ == "__main__":
    run_qiantang_strategy_test(
        source=CHOSEN_SOURCE,
        stock_source=STOCK_MODE,
        stock_input=STOCK_INPUT,
        strategies=TEST_QIANTANG_STRATEGY,
        start_date_str=TEST_START_DATE,
        end_date_str=TEST_END_DATE,
    )
