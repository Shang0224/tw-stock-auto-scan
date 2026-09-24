# test_qiantang_Strategy.py
"""
錢塘潮選股系統 - 多方選股策略測試進入點與 Excel 儀表板匯出
說明：對齊 test_Monitor.py 架構，讀取 watch_list.csv 執行錢塘潮 7 大多方選股公式，
並產出 openpyxl 多工作表 (Multi-Sheet) Excel 報告。
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
    st_qiantang_f1_spt_growth,       # 筆張現形
    st_qiantang_f2_volume_breakout,  # 出量上輕
    st_qiantang_f3_after_shakeout,   # 洗盤後
    st_qiantang_f4_strong_rise,      # 強力上
    st_qiantang_f5_major_buy_easy,   # 主外上輕
    st_qiantang_f6_flower,           # 一朵花
    st_qiantang_f7_super_stock,      # 飆股
)

# 3. 匯入資料抓取與工具庫
from utils import (
    archive_and_cleanup,
    fm_get_complete_stock_data,
    get_stock_name_dict,
    parse_monitor_stocks,
)

# =====================================================================
# 🎛️ 多方策略測試控制面板
# =====================================================================
CHOSEN_SOURCE = "fm"
TEST_START_DATE = "2024-01-01"
TEST_END_DATE = "2025-09-30"

# ---------------------------------------------------------------------
# 模式 A：CSV 檔案載入模式 (與 test_Monitor.py 相同，預設讀取 watch_list.csv)
STOCK_MODE = "csv"
STOCK_INPUT = os.getenv("STOCK_FILES", "data/MID100.csv")

# 模式 B：自訂 List[dict] 載入模式
# STOCK_MODE = "noncsv"
# STOCK_INPUT = [
#     {"stock_id": "3706", "name": "神達", "category": "MID100"},
#     {"stock_id": "2330", "name": "台積電", "category": "TW50"},
#     {"stock_id": "2317", "name": "鴻海", "category": "TW50"},
# ]
# ---------------------------------------------------------------------

# 測試策略清單：加/減 # 註解即可自由切換想測試的策略
TEST_QIANTANG_STRATEGY = [
    st_qiantang_f1_spt_growth,       # 筆張現形
    st_qiantang_f2_volume_breakout,  # 出量上輕
    st_qiantang_f3_after_shakeout,   # 洗盤後
    st_qiantang_f4_strong_rise,      # 強力上
    st_qiantang_f5_major_buy_easy,   # 主外上輕
    st_qiantang_f6_flower,           # 一朵花
    st_qiantang_f7_super_stock,      # 飆股
]


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


def run_qiantang_strategy_excel_scan(
    stock_source=STOCK_MODE,
    stock_input=STOCK_INPUT,
    strategies=TEST_QIANTANG_STRATEGY,
):
    """執行錢塘潮多方選股掃描並產出 Excel 儀表板"""
    if not strategies:
        raise ValueError("❌ [錯誤] 未指定 TEST_QIANTANG_STRATEGY 策略清單，請至少取消註解一個選股公式！")

    # 1. 時間設定 (UTC+8 台灣時間)
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    today_str = tw_time.strftime("%Y-%m-%d")
    start_str = (tw_time.date() - timedelta(days=120)).strftime("%Y-%m-%d")

    # 2. 解析股票清單與抓取名稱字典
    monitor_stocks = parse_monitor_stocks(stock_source, stock_input)
    if not monitor_stocks:
        print(f"❌ [錯誤] 無法解析股票清單檔 ({stock_input})，請確認檔案是否存在。")
        return

    unique_stock_ids = list(set([str(s["stock_id"]) for s in monitor_stocks]))
    stock_name_dict, dl = get_stock_name_dict()

    print("🚀 【錢塘潮選股系統】啟動掃描...")
    print(f"📡 讀取來源：{stock_input} | 批量抓取 {len(unique_stock_ids)} 檔股票資料 ({start_str} ~ {today_str})...")

    # 3. 批量抓取日 K 線與籌碼資料
    global_df = fm_get_complete_stock_data(dl, unique_stock_ids, start_str, today_str)
    if global_df.empty:
        print("❌ [錯誤] FinMind 數據抓取為空，結束執行。")
        return

    # 4. 全域指標預處理 (KD、輕鬆線、SPT、VTR、MSR 等)
    print("⚡ 正在執行全域技術面與籌碼替代指標預處理...")
    global_df = preprocess_all_technical_indicators(global_df)
    print("✅ 全域指標預處理完成！")

    # 5. 初始化 Excel 分頁資料收集結構
    results_by_formula = {strat.__name__: [] for strat in strategies}
    stock_dashboard = {}

    print("⚡ 開始進行多方策略邏輯檢測...\n")
    stock_meta_map = {str(s["stock_id"]): s for s in monitor_stocks}
    grouped = global_df.groupby("stock_id")

    for stock_id, group_df in grouped:
        sid = str(stock_id)
        if sid not in stock_meta_map:
            continue

        meta = stock_meta_map[sid]
        stock_name = meta.get("name", stock_name_dict.get(sid, sid))
        stock_cat = meta.get("category", "MID100")

        sorted_df = group_df.sort_values("date").copy()
        if sorted_df.empty or len(sorted_df) < 5:
            continue

        # 呼叫核心檢測引擎
        hits = scan_single_stock_monitors(
            df_single=sorted_df,
            category=stock_cat,
            monitor_list=strategies,
            param_profiles=PARAM_PROFILES,
        )

        if hits:
            latest_row = sorted_df.iloc[-1]
            close_price = round(float(latest_row["close"]), 2)
            vol_today = float(latest_row.get("Trading_Volume", 0))
            vol_lots = int(vol_today / 1000)

            hit_formula_names = []

            for hit in hits:
                strat_func_name = hit.get("strategy_name", "")
                formula_label = hit.get("選股公式", strat_func_name)
                hit_formula_names.append(formula_label)

                # 寫入單一策略 Sheet 結果
                detail_record = {
                    "股票代號": sid,
                    "名稱": stock_name,
                    "今日收盤": close_price,
                    "今日成交量(張)": vol_lots,
                    "選股公式": formula_label,
                    "操作建議": hit.get("操作建議", hit.get("detail", "")),
                }
                if strat_func_name in results_by_formula:
                    results_by_formula[strat_func_name].append(detail_record)

            # 寫入儀表板 (Dashboard) 數據
            stock_dashboard[sid] = {
                "股票代號": sid,
                "名稱": stock_name,
                "收盤": close_price,
                "成交量(張)": vol_lots,
                "符合公式總數": len(hit_formula_names),
                "符合公式明細": "、".join(hit_formula_names),
            }

            print(f"🎯 {stock_name}({sid}) 觸發訊號！符合：{', '.join(hit_formula_names)}")

    # =====================================================================
    # 📊 產出 Excel 多工作表 (Multi-Sheet) 報告
    # =====================================================================
    file_name = f"錢塘潮選股報告_{tw_time.strftime('%Y%m%d_%H%M')}.xlsx"
    file_path = os.path.abspath(file_name)

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        # Sheet 1: 綜合強勢股儀表板
        if stock_dashboard:
            dashboard_df = pd.DataFrame(stock_dashboard.values()).sort_values(
                by="符合公式總數", ascending=False
            )
        else:
            dashboard_df = pd.DataFrame(
                columns=["股票代號", "名稱", "收盤", "成交量(張)", "符合公式總數", "符合公式明細"]
            )
        dashboard_df.to_excel(writer, sheet_name="🎯 綜合強勢股儀表板", index=False)

        # Sheet 2~N: 個別策略詳細結果
        for strat in strategies:
            func_name = strat.__name__
            data_list = results_by_formula.get(func_name, [])
            sheet_df = pd.DataFrame(data_list)

            if sheet_df.empty:
                sheet_df = pd.DataFrame(
                    columns=["股票代號", "名稱", "今日收盤", "今日成交量(張)", "選股公式", "操作建議"]
                )

            sheet_label = data_list["選股公式"] if data_list else func_name
            sheet_df.to_excel(writer, sheet_name=sheet_label, index=False)

    print(f"\n🎉 掃描完成！終極選股報告已成功匯出至：【{file_path}】")

    # 自動備份與同步至 NAS (若環境變數已設定)
    if os.path.exists(file_path) and os.getenv("NAS_SFTP_PATH"):
        remote_path = f"{os.getenv('NAS_SFTP_PATH')}/qiantang_strategy/{file_name}"
        try:
            archive_and_cleanup(file_path, remote_path)
            print(f"📦 已同步將 Excel 報告備份至 NAS 遠端：{remote_path}")
        except Exception as e:
            print(f"⚠️ NAS 備份跳過或失敗: {e}")


if __name__ == "__main__":
    run_qiantang_strategy_excel_scan()
