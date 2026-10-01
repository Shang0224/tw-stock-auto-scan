# test_qiantang_Strategy.py
"""
錢塘潮選股系統 - 多方選股策略指定天期區間歷史掃描 (含未來前瞻與極值績效追蹤)
說明：對齊 test_Monitor.py 逐日推進與交易日過濾架構，執行錢塘潮 7 大多方選股公式，
     並自動計算觸發後 T+3/T+5/T+10/T+20 報酬率與未來 1 年內最高/最低極值報酬，支援 Excel 與 CSV 獨立控制匯出與上傳。
"""

import os
from datetime import datetime, timedelta, timezone
import pandas as pd

from strategy.engine import scan_single_stock
from strategy.config import BUY_PARAM_PROFILES

# 1. 匯入核心執行引擎與預處理
from monitor.engine import (
    preprocess_all_technical_indicators,
)

# 2. 匯入 7 大多方選股策略
from strategy.qiantang_strategies import (
    st_qiantang_f1_spt_growth,      # 筆張現形
    st_qiantang_f2_volume_breakout, # 出量上輕
    st_qiantang_f3_after_shakeout,  # 洗盤後
    st_qiantang_f4_strong_rise,     # 強力上
    st_qiantang_f5_major_buy_easy,  # 主外上輕
    st_qiantang_f6_flower,          # 一朵花
    st_qiantang_f7_super_stock,     # 飆股
)

TEST_QIANTANG_STRATEGY = [
    st_qiantang_f1_spt_growth,      # 筆張現形, 不需籌碼指標
    #st_qiantang_f2_volume_breakout, # 出量上輕, 不需籌碼指標
    #st_qiantang_f3_after_shakeout,  # 洗盤後, 不需籌碼指標
    #st_qiantang_f4_strong_rise,     # 強力上, 不需籌碼指標
    #st_qiantang_f5_major_buy_easy,  # 主外上輕
    #st_qiantang_f6_flower,          # 一朵花
    #st_qiantang_f7_super_stock,     # 飆股
]

# 3. 匯入資料抓取與工具庫 (包含雙績效分析工具)
from utils import (
    archive_and_cleanup,
    fm_get_complete_stock_data,
    get_stock_name_dict,
    parse_monitor_stocks,
    parse_stock_ids,
    get_fm_trading_days,
    calculate_forward_horizon_returns, # 前瞻固定天數報酬
    calculate_one_year_extremes,       # 一年內最高與最低極值報酬
    load_stocks_from_csv,
)

# =====================================================================
# 🎛 多方策略測試控制面板 (指定天期區間)
# =====================================================================
CHOSEN_SOURCE = "fm"
TEST_START_DATE = "2015-01-01"  # 測試起始日期 (YYYY-MM-DD)
TEST_END_DATE = "2025-09-30"    # 測試結束日期 (YYYY-MM-DD)
DAYS_BEFORE = 365               # 歷史技術指標計算緩衝天數

# 🌟 檔案輸出控制開關
EXPORT_EXCEL = False            # 是否輸出與上傳 Excel 報告
EXPORT_CSV = True               # 是否輸出與上傳綜合儀表板 CSV 檔

# 模式 A：CSV 檔案載入模式
STOCK_MODE = "csv"
STOCK_INPUT = "data/TestData/qiantang_mid100_hot.csv"
#STOCK_INPUT = "data/TestData/qiantang_ICDesign_hot.csv,data/TestData/qiantang_mid100_hot.csv,data/TestData/qiantang_tw50_hot.csv"
#STOCK_INPUT = os.getenv("STOCK_FILES", "data/MID100.csv")

# 模式 B：自訂 List[dict] 載入模式
#STOCK_MODE = "noncsv"
#STOCK_INPUT = [
#    {"stock_id": "3706", "name": "神達", "category": "MID100"},
#    {"stock_id": "2330", "name": "台積電", "category": "TW50"},
#    {"stock_id": "2317", "name": "鴻海", "category": "TW50"},
#    {"stock_id": "3227", "name": "原相", "category": "ICDesign"},
#]


def scan_qiantang_strategy_day(
    day_str: str,
    all_df_slice: pd.DataFrame,
    global_df: pd.DataFrame,
    monitor_stocks: list,
    strategies: list,
    profiles_map: dict = BUY_PARAM_PROFILES,
) -> list:
    """單日個股選股掃描核心，並於觸發時附加前瞻與極值績效"""
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
        if df_single.empty or len(df_single) < 5:
            continue

        # 呼叫引擎執行策略檢測
        hits = scan_single_stock(
            df_single=df_single,
            category=stock_cat,
            func_list=strategies,
            param_profiles=profiles_map,
        )

        if hits:
            latest_row = df_single.iloc[-1]
            close_price = round(float(latest_row["close"]), 2)
            vol_today = float(latest_row.get("Trading_Volume", 0))
            vol_lots = int(vol_today / 1000)

            # 🌟 1. 計算 T+3, T+5, T+10, T+20 (預設)前瞻區間報酬
            fwd_perf = calculate_forward_horizon_returns(
                stock_id=sid,
                trigger_date_str=day_str,
                global_df=global_df
            )

            # 🌟 2. 計算未來 1 年內的最高與最低極值報酬
            extreme_perf = calculate_one_year_extremes(
                stock_id=sid,
                trigger_date_str=day_str,
                global_df=global_df
            )

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

                # 寫入前瞻與極值績效欄位
                hit_record.update(fwd_perf)
                hit_record.update(extreme_perf)

                day_hits.append(hit_record)

                print(f"hit_record : {hit_record}")
    return day_hits


def run_qiantang_strategy_range_scan(
    source=CHOSEN_SOURCE,
    stock_source=STOCK_MODE,
    stock_input=STOCK_INPUT,
    strategies=TEST_QIANTANG_STRATEGY,
    start_date_str=TEST_START_DATE,
    end_date_str=TEST_END_DATE,
):
    """執行錢塘潮多方選股指定天期歷史掃描並產出報表"""
    tz_tw = timezone(timedelta(hours=8))
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)

    if end_date < start_date:
        raise ValueError("❌ 結束日期不能小於開始日期！")

    if not strategies:
        raise ValueError("❌ [錯誤] 未指定 TEST_QIANTANG_STRATEGY 策略清單！")

    # 1. 解析監控股票清單
    monitor_stocks = load_stocks_from_csv(stock_input)
    if not monitor_stocks:
        print(f"❌ [錯誤] 無法解析股票清單 ({stock_input})。")
        return

    # 清理股票代號清單
    unique_stock_ids = list(
        set(
            [
                str(s["stock_id"] if isinstance(s, dict) else s)
                .replace(".TWO", "")
                .replace(".TW", "")
                .replace("^", "")
                for s in monitor_stocks
            ]
        )
    )

    print(f"🧪 [測試啟動] 錢塘潮多方策略歷史掃描 ({start_date_str} ~ {end_date_str})")
    print(f"📡 監控數量：{len(unique_stock_ids)} 檔個股 ({unique_stock_ids})\n")

    # 2. 準備歷史資料抓取區間
    fetch_start_str = (start_date - timedelta(days=DAYS_BEFORE)).strftime("%Y-%m-%d")
    fetch_end_str = (end_date + timedelta(days=365)).strftime("%Y-%m-%d")

    print(f"📡 正在向 FinMind 批量抓取歷史與未來 K 線資料 ({fetch_start_str} ~ {fetch_end_str})...")
    stock_name_dict, dl = get_stock_name_dict()

    global_df = fm_get_complete_stock_data(dl, unique_stock_ids, fetch_start_str, fetch_end_str)
    if global_df.empty:
        print("❌ [錯誤] FinMind 數據抓取為空，結束執行。")
        return

    # 3. 全域指標預處理
    print("⚡ 正在執行全域技術面與籌碼替代指標預處理...")
    global_df = preprocess_all_technical_indicators(global_df)
    print("✅ 全域指標預處理完成！\n")

    # 4. 取得台股交易日清單
    print("📡 正在向 FinMind 取得台股交易日曆行事曆...")
    trading_days_set = get_fm_trading_days(fetch_start_str, fetch_end_str)
    if trading_days_set:
        print(f"✅ 成功載入 FinMind 交易日清單，共 {len(trading_days_set)} 個交易日。\n")
    else:
        print("⚠ 無法取得 FinMind 交易日，將自動退回僅過濾週末機制。\n")

    # 5. 逐日推進監控掃描
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
            global_df=global_df,
            monitor_stocks=monitor_stocks,
            strategies=strategies,
            profiles_map=BUY_PARAM_PROFILES,
        )

        if day_hits:
            print(f"⚡ [{day_str}] 選股掃描完成，共觸發 {len(day_hits)} 筆訊號。")
            for record in day_hits:
                all_hits_list.append(record)
                s_name = record["strategy_name"]
                if s_name in results_by_formula:
                    results_by_formula[s_name].append(record)

        current_day += timedelta(days=1)

    # =====================================================================
    # 6. 彙整數據與產出報表
    # =====================================================================
    tw_time = datetime.now(tz_tw)
    current_time_str = tw_time.strftime('%Y%m%d_%H%M')
    
    file_name = f"錢塘潮選股歷史報告_含績效分析_{start_date_str}_to_{end_date_str}_{current_time_str}.xlsx"
    file_path = os.path.abspath(file_name)

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
                "T+3日績效": hit.get("T+3日績效", "N/A"),
                "T+5日績效": hit.get("T+5日績效", "N/A"),
                "T+10日績效": hit.get("T+10日績效", "N/A"),
                "T+20日績效": hit.get("T+20日績效", "N/A"),
                "1Y內最高績效": hit.get("1Y內最高績效", "N/A"),
                "1Y內最低績效": hit.get("1Y內最低績效", "N/A"),
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
            "T+3日績效": item["T+3日績效"],
            "T+5日績效": item["T+5日績效"],
            "T+10日績效": item["T+10日績效"],
            "T+20日績效": item["T+20日績效"],
            "1Y內最高績效": item["1Y內最高績效"],
            "1Y內最低績效": item["1Y內最低績效"],
        })

    dashboard_df = (
        pd.DataFrame(dashboard_rows).sort_values(by=["日期", "符合公式總數"], ascending=[False, False])
        if dashboard_rows
        else pd.DataFrame(
            columns=[
                "日期", "股票代號", "名稱", "收盤", "成交量(張)", "符合公式總數", "符合公式明細",
                "T+3日績效", "T+5日績效", "T+10日績效", "T+20日績效", "1Y內最高績效", "1Y內最低績效"
            ]
        )
    )

    # 🌟 條件式輸出 Excel 報表 (依 EXPORT_EXCEL 決定)
    if EXPORT_EXCEL:
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            dashboard_df.to_excel(writer, sheet_name="🎯 區間綜合強勢股儀表板", index=False)

            for strat in strategies:
                func_name = strat.__name__
                data_list = results_by_formula.get(func_name, [])
                sheet_df = pd.DataFrame(data_list)
                if sheet_df.empty:
                    sheet_df = pd.DataFrame(
                        columns=[
                            "日期", "股票代號", "名稱", "今日收盤", "今日成交量(張)", "選股公式", "操作建議",
                            "T+3日績效", "T+5日績效", "T+10日績效", "T+20日績效", "1Y內最高績效", "1Y內最低績效"
                        ]
                    )
                else:
                    sheet_df = sheet_df.drop(columns=["strategy_name"], errors="ignore")

                sheet_label = data_list[0].get("選股公式", func_name) if data_list else func_name
                sheet_df.to_excel(writer, sheet_name=sheet_label, index=False)

        print(f"\n🎉 區間掃描完成！包含績效分析之終極選股 Excel 報告已成功匯出至：【{file_path}】")
    else:
        print("\nℹ [提示] EXPORT_EXCEL 為 False，已略過 Excel 報表的本地產出。")

    # 🌟 條件式輸出綜合儀表板 CSV 檔 (依 EXPORT_CSV 決定)
    csv_file_path = None
    if EXPORT_CSV:
        source_folder_name = "qiantang_test_report"
        os.makedirs(f"data/{source_folder_name}", exist_ok=True)
        csv_file_name = f"dashboard_summary_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
        csv_file_path = os.path.abspath(f"data/{source_folder_name}/{csv_file_name}")
        
        dashboard_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
        print(f"📊 綜合儀表板 CSV 檔已成功匯出至：【{csv_file_path}】")
    else:
        print("ℹ [提示] EXPORT_CSV 為 False，已略過 CSV 檔的本地產出。")

    # =====================================================================
    # 7. 自動備份至 NAS
    # =====================================================================
    if os.getenv("NAS_SFTP_PATH"):
        # Excel 備份 (受 EXPORT_EXCEL 控制)
        if EXPORT_EXCEL and os.path.exists(file_path):
            remote_excel_path = f"{os.getenv('NAS_SFTP_PATH')}/qiantang_test_report/{file_name}"
            try:
                archive_and_cleanup(file_path, remote_excel_path)
                print(f"📦 Excel 報告已備份至 NAS：{remote_excel_path}")
            except Exception as e:
                print(f"⚠ Excel NAS 備份失敗: {e}")

        # 儀表板 CSV 備份 (受 EXPORT_CSV 控制)
        if EXPORT_CSV and csv_file_path and os.path.exists(csv_file_path):
            remote_csv_path = f"{os.getenv('NAS_SFTP_PATH')}/qiantang_test_report/{csv_file_name}"
            try:
                archive_and_cleanup(csv_file_path, remote_csv_path)
                print(f"📦 儀表板 CSV 已成功備份至 NAS 並清理本地：{remote_csv_path}")
            except Exception as e:
                print(f"⚠ CSV NAS 備份失敗: {e}")


if __name__ == "__main__":
    print("test_qiantang_Strategy.py")
    run_qiantang_strategy_range_scan()
