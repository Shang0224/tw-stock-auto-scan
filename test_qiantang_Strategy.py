# test_qiantang_Strategy.py
"""
錢塘潮選股系統 - 多方選股策略指定天期區間歷史掃描
說明：完全對齊 test_Monitor.py 之逐日推進 (Date-centric Loop) 與交易日過濾架構，
     支援指定 start_date ~ end_date 進行多日歷史選股，並匯出 Multi-Sheet Excel 選股儀表板。
"""

import os
from datetime import datetime, timedelta, timezone
import pandas as pd

# 1. 匯入核心執行引擎與預處理
from monitor.engine import (
    PARAM_PROFILES,
    preprocess_all_technical_indicators,
    scan_single_stock_monitors,
)

# 2. 匯入 7 大多方選股策略 (來自 strategy 套件)
from strategy.qiantang_strategies import (
    st_qiantang_f1_spt_growth,      # 筆張現形
    st_qiantang_f2_volume_breakout, # 出量上輕
    st_qiantang_f3_after_shakeout,  # 洗盤後
    st_qiantang_f4_strong_rise,     # 強力上
    st_qiantang_f5_major_buy_easy,  # 主外上輕
    st_qiantang_f6_flower,          # 一朵花
    st_qiantang_f7_super_stock,     # 飆股
)

# 測試策略清單：加/減 # 註解即可自由切換想測試的策略
TEST_QIANTANG_STRATEGY = [
    st_qiantang_f1_spt_growth,      # 筆張現形
    st_qiantang_f2_volume_breakout, # 出量上輕
    st_qiantang_f3_after_shakeout,  # 洗盤後
    st_qiantang_f4_strong_rise,     # 強力上
    st_qiantang_f5_major_buy_easy,  # 主外上輕
    st_qiantang_f6_flower,          # 一朵花
    st_qiantang_f7_super_stock,     # 飆股
]

# 3. 匯入資料抓取與工具庫
from utils import (
    archive_and_cleanup,
    fm_get_complete_stock_data,
    get_stock_name_dict,
    parse_monitor_stocks,
    parse_stock_ids,
    get_fm_trading_days,
)

# =====================================================================
# 🎛 多方策略測試控制面板 (指定天期區間)
# =====================================================================
CHOSEN_SOURCE = "fm"
TEST_START_DATE = "2024-01-01"  # 測試起始日期 (YYYY-MM-DD)
TEST_END_DATE = "2024-06-30"    # 測試結束日期 (YYYY-MM-DD)
DAYS_BEFORE = 365               # 歷史技術指標計算緩衝天數

# ---------------------------------------------------------------------
# 模式 A：CSV 檔案載入模式 (預設讀取 watch_list.csv)
# STOCK_MODE = "csv"
# STOCK_INPUT = os.getenv("STOCK_FILES", "data/MID100.csv")

# 模式 B：自訂 List[dict] 載入模式
STOCK_MODE = "noncsv"
STOCK_INPUT = [
    {"stock_id": "3706", "name": "神達", "category": "MID100"},
    {"stock_id": "2330", "name": "台積電", "category": "TW50"},
    {"stock_id": "2317", "name": "鴻海", "category": "TW50"},
    {"stock_id": "3227", "name": "原相", "category": "ICDesign"},
]
# ---------------------------------------------------------------------


def scan_qiantang_strategy_day(
    day_str: str,
    all_df_slice: pd.DataFrame,
    stock_ids: list,
    strategies: list,
    profiles_map: dict = PARAM_PROFILES,
) -> list:
    """單日個股選股掃描核心 (模仿 test_Monitor.py 的 scan_monitor_day)"""
    day_hits = []
    stock_meta_map = {str(s["stock_id"]): s for s in stock_ids}
    grouped = all_df_slice.groupby("stock_id")

    for stock_id, group_df in grouped:
        sid = str(stock_id)
        if sid not in stock_meta_map:
            continue

        meta = stock_meta_map[sid]
        stock_name = meta.get("name", sid)
        stock_cat = meta.get("category", "MID100")

        df_single = group_df.sort_values("date").copy()
        if df_single.empty or len(df_single) < 5:
            continue

        # 呼叫引擎執行策略檢測
        hits = scan_single_stock_monitors(
            df_single=df_single,
            category=stock_cat,
            monitor_list=strategies,
            param_profiles=profiles_map,
        )

        if hits:
            latest_row = df_single.iloc[-1]
            close_price = round(float(latest_row["close"]), 2)
            vol_today = float(latest_row.get("Trading_Volume", 0))
            vol_lots = int(vol_today / 1000)

            for hit in hits:
                strat_func_name = hit.get("strategy_name", "")
                formula_label = hit.get("選股公式", strat_func_name)

                hit_record = {
                    "日期": day_str,
                    "股票代號": sid,
                    "名稱": stock_name,
                    "今日收盤": close_price,
                    "今日成交量(張)": vol_lots,
                    "選股公式": formula_label,
                    "strategy_name": strat_func_name,
                    "操作建議": hit.get("操作建議", hit.get("detail", "")),
                }
                day_hits.append(hit_record)

    return day_hits


def run_qiantang_strategy_range_scan(
    source=CHOSEN_SOURCE,
    stock_source=STOCK_MODE,
    stock_input=STOCK_INPUT,
    strategies=TEST_QIANTANG_STRATEGY,
    start_date_str=TEST_START_DATE,
    end_date_str=TEST_END_DATE,
):
    """執行錢塘潮多方選股指定天期歷史掃描並產出 Excel 儀表板"""
    tz_tw = timezone(timedelta(hours=8))
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)

    if end_date < start_date:
        raise ValueError("❌ 結束日期不能小於開始日期！")

    if not strategies:
        raise ValueError("❌ [錯誤] 未指定 TEST_QIANTANG_STRATEGY 策略清單！")

    # 1. 解析監控股票清單
    stock_ids = parse_monitor_stocks(stock_source, stock_input)
    if not stock_ids:
        print(f"❌ [錯誤] 無法解析股票清單 ({stock_input})。")
        return

    # 清理並提取股票代號清單 (一步到位)
    unique_stock_ids = list(
        set(
            [
                str(s["stock_id"] if isinstance(s, dict) else s)
                .replace(".TWO", "")
                .replace(".TW", "")
                .replace("^", "")
                for s in stock_ids
            ]
        )
    )

    print(f"🧪 [測試啟動] 錢塘潮多方策略歷史掃描 ({start_date_str} ~ {end_date_str})")
    print(f"📡 監控數量：{len(unique_stock_ids)} 檔個股 ({unique_stock_ids})\n")

    # 2. 準備歷史資料抓取區間 (往前推 DAYS_BEFORE 天計算指標)
    fetch_start_str = (start_date - timedelta(days=DAYS_BEFORE)).strftime("%Y-%m-%d")
    fetch_end_str = end_date.strftime("%Y-%m-%d")

    print(f"📡 正在向 FinMind 批量抓取歷史與籌碼資料 ({fetch_start_str} ~ {fetch_end_str})...")
    stock_name_dict, dl = get_stock_name_dict()

    global_df = fm_get_complete_stock_data(dl, unique_stock_ids, fetch_start_str, fetch_end_str)
    if global_df.empty:
        print("❌ [錯誤] FinMind 數據抓取為空，結束執行。")
        return

    # 3. 全域指標預處理 (一次計算全歷史輕鬆線、KD、SPT、VTR 等)
    print("⚡ 正在執行全域技術面與籌碼替代指標預處理...")
    global_df = preprocess_all_technical_indicators(global_df)
    print("✅ 全域指標預處理完成！\n")

    # 4. 取得台股交易日清單 (跳過非交易日)
    print("📡 正在向 FinMind 取得台股交易日曆行事曆...")
    trading_days_set = get_fm_trading_days(fetch_start_str, fetch_end_str)
    if trading_days_set:
        print(f"✅ 成功載入 FinMind 交易日清單，共 {len(trading_days_set)} 個交易日。\n")
    else:
        print("⚠ 無法取得 FinMind 交易日，將自動退回僅過濾週末機制。\n")

    # 5. 逐日推進監控掃描 (Date-centric Range Loop)
    results_by_formula = {strat.__name__: [] for strat in strategies}
    all_hits_list = []
    current_day = start_date

    while current_day <= end_date:
        day_str = current_day.strftime("%Y-%m-%d")

        # 交易日過濾
        if trading_days_set:
            if day_str not in trading_days_set:
                current_day += timedelta(days=1)
                continue
        else:
            if current_day.weekday() >= 5:
                current_day += timedelta(days=1)
                continue

        # 切出截至當日為止的歷史切片
        day_data_cutoff = current_day.replace(hour=23, minute=59, second=59)
        all_df_slice = global_df[
            global_df["date"] <= day_data_cutoff.strftime("%Y-%m-%d")
        ].copy()

        if all_df_slice.empty:
            current_day += timedelta(days=1)
            continue

        # 執行當日選股掃描
        day_hits = scan_qiantang_strategy_day(
            day_str=day_str,
            all_df_slice=all_df_slice,
            stock_ids=stock_ids,
            strategies=strategies,
            profiles_map=PARAM_PROFILES,
        )

        if day_hits:
            print(f"⚡ [{day_str}] 選股掃描完成，共觸發 {len(day_hits)} 筆訊號。")
            for record in day_hits:
                all_hits_list.append(record)
                s_name = record["strategy_name"]
                if s_name in results_by_formula:
                    results_by_formula[s_name].append(record)

        current_day += timedelta(days=1)

    # 6. 彙整數據與產出 Multi-Sheet Excel 報告
    tw_time = datetime.now(tz_tw)
    file_name = f"錢塘潮選股歷史報告_{start_date_str}_to_{end_date_str}_{tw_time.strftime('%Y%m%d_%H%M')}.xlsx"
    file_path = os.path.abspath(file_name)

    # 建立儀表板統計 (按 股票代號 + 日期 彙整觸發公式)
    dashboard_dict = {}
    for hit in all_hits_list:
        key = (hit["日期"], hit["股票代號"])
        if key not in dashboard_dict:
            dashboard_dict[key] = {
                "日期": hit["日期"],
                "股票代號": hit["股票代號"],
                "名稱": hit["名稱"],
                "收盤": hit["今日收盤"],
                "成交量(張)": hit["今日成交量(張)"],
                "符合公式清單": [hit["選股公式"]],
            }
        else:
            dashboard_dict[key]["符合公式清單"].append(hit["選股公式"])

    dashboard_rows = []
    for item in dashboard_dict.values():
        formulas = list(set(item["符合公式清單"]))
        dashboard_rows.append({
            "日期": item["日期"],
            "股票代號": item["股票代號"],
            "名稱": item["名稱"],
            "收盤": item["收盤"],
            "成交量(張)": item["成交量(張)"],
            "符合公式總數": len(formulas),
            "符合公式明細": "、".join(formulas),
        })

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        # Sheet 1: 綜合儀表板
        dashboard_df = (
            pd.DataFrame(dashboard_rows).sort_values(by=["日期", "符合公式總數"], ascending=[False, False])
            if dashboard_rows
            else pd.DataFrame(columns=["日期", "股票代號", "名稱", "收盤", "成交量(張)", "符合公式總數", "符合公式明細"])
        )
        dashboard_df.to_excel(writer, sheet_name="🎯 區間綜合強勢股儀表板", index=False)

        # Sheet 2+: 個別策略 Sheet
        for strat in strategies:
            func_name = strat.__name__
            data_list = results_by_formula.get(func_name, [])
            sheet_df = pd.DataFrame(data_list)
            if sheet_df.empty:
                sheet_df = pd.DataFrame(
                    columns=["日期", "股票代號", "名稱", "今日收盤", "今日成交量(張)", "選股公式", "操作建議"]
                )
            else:
                sheet_df = sheet_df.drop(columns=["strategy_name"], errors="ignore")

            sheet_label = data_list.get("選股公式", func_name) if data_list else func_name
            sheet_df.to_excel(writer, sheet_name=sheet_label, index=False)

    print(f"\n🎉 區間掃描完成！報告已成功匯出至：【{file_path}】")

    # 7. 自動備份至 NAS (選擇性)
    if os.getenv("NAS_SFTP_PATH") and os.path.exists(file_path):
        remote_path = f"{os.getenv('NAS_SFTP_PATH')}/qiantang_strategy/{file_name}"
        try:
            archive_and_cleanup(file_path, remote_path)
            print(f"📦 已備份至 NAS 遠端：{remote_path}")
        except Exception as e:
            print(f"⚠ NAS 備份跳過或失敗: {e}")


if __name__ == "__main__":
    run_qiantang_strategy_range_scan()
