# main_qiantang_Strategy.py
"""
錢塘潮選股系統 - 多方選股策略測試進入點與 Excel 儀表板匯出
說明：對齊 test_Monitor.py 架構，讀取 watch_list.csv 執行錢塘潮 7 大多方選股公式，
並產出 openpyxl 多工作表 (Multi-Sheet) Excel 報告。
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
import pandas as pd

from strategy.engine import (
    scan_single_stock,
    preprocess_all_technical_indicators,   
)

# 1. 匯入核心執行引擎與預處理
from monitor.engine import (
    PARAM_PROFILES,
    #preprocess_all_technical_indicators,
    #scan_single_stock_monitors,
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

# 3. 匯入資料抓取與工具庫
from utils import (
    archive_and_cleanup,
    fm_get_complete_stock_data,
    get_stock_name_dict,
    parse_monitor_stocks,
    load_stocks_from_csv,
    align_and_normalize_results,
    archive_and_cleanup,
    fm_get_complete_stock_data,
    get_stock_name_dict,
    #parse_stock_ids,
    #preprocess_all_technical_indicators,  # 來自 utils/indicators.py
    send_qiantang_7in1_line_summary,
    parse_and_validate_stocks,
)

# 本地手動測試且未帶參數時使用的全域測試日期
GLOBAL_TEST_DATE = "2026-11-03"

# ---------------------------------------------------------------------
# 模式 A：CSV 檔案載入模式 (與 test_Monitor.py 相同，預設讀取 watch_list.csv)
STOCK_MODE = "csv"
#STOCK_INPUT = "data/TestData/qiantang_mid100_test.csv"
STOCK_INPUT = "data/MID100.csv"
#STOCK_INPUT = os.getenv("STOCK_FILES", "data/MID100.csv")
#STOCK_INPUT = "data/TestData/qiantang_ICDesign_hot.csv"
#STOCK_INPUT = "data/TestData/qiantang_ICDesign_hot.csv,data/TestData/qiantang_mid100_hot.csv,data/TestData/qiantang_tw50_hot.csv"
#STOCK_INPUT = "data/TestData/qiantang_mid100_hot.csv"

# =====================================================================
# 🎛️ 多方策略測試控制面板
# =====================================================================

CHOSEN_SOURCE = "fm"
TEST_START_DATE = "2024-01-01"
TEST_END_DATE = "2025-09-30"


# 模式 B：自訂 dict[str, dict] 載入模式
"""
STOCK_MODE = "noncsv"
STOCK_INPUT = {
    "3661": {"yf_suffix": "TW", "name": "世芯-KY", "category": "ICDesign", "market": "上市", "note": "ASIC晶片設計服務與矽智財"},
    "3035": {"yf_suffix": "TW", "name": "智原", "category": "ICDesign", "market": "上市", "note": "ASIC晶片設計服務與矽智財"},
    "3529": {"yf_suffix": "TWO", "name": "力旺", "category": "ICDesign", "market": "上櫃", "note": "ASIC晶片設計服務與矽智財"},
    "6643": {"yf_suffix": "TWO", "name": "M31", "category": "ICDesign", "market": "上櫃", "note": "ASIC晶片設計服務與矽智財"},
}
"""


# ---------------------------------------------------------------------

def scan_qiantang_strategy_day(day_str, all_df_slice, stocks_dict, strategies, profiles_map=PARAM_PROFILES):
    """單日選股掃描核心"""
    day_hits = []
    
    grouped = all_df_slice.groupby("stock_id")

    for stock_id, group_df in grouped:
        sid = str(stock_id)
        if sid not in stocks_dict:
            continue

        stock_info = stocks_dict[sid]
        stock_name = stock_info.get("name", "未知股票")
        stock_cat = stock_info.get("category", "MID100")

        df_single = group_df.sort_values("date").copy()

        # 呼叫引擎執行策略檢測
        hits = scan_single_stock(
            df_single=df_single,https://github.com/Shang0224/tw-stock-auto-scan/blob/main/main_qiantang_Strategy.py
            category=stock_cat,
            func_list=strategies,
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
    stock_mode=STOCK_MODE,
    stock_data=STOCK_INPUT,
    strategies=TEST_QIANTANG_STRATEGY,
    target_date: str = None,  # 未傳入時由內部自動判定    
):
    """執行錢塘潮多方選股掃描並產出 Excel 儀表板"""
    if not strategies:
        raise ValueError("❌ [錯誤] 未指定 TEST_QIANTANG_STRATEGY 策略清單，請至少取消註解一個選股公式！")

    # 1. 時間設定 (UTC+8 台灣時間)
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    today_str = tw_time.strftime("%Y-%m-%d")
    start_str = (tw_time.date() - timedelta(days=120)).strftime("%Y-%m-%d")

    # 1. 呼叫函數，傳入模式與數據
    stock_records = parse_and_validate_stocks(
        stock_mode=stock_mode, 
        stock_data=stock_data
    )
   
    if not stock_records:
        print(f"❌ [錯誤] 無照解析股票清單 ({stock_data})。")
        return

    # 2. 提煉純數字代號串列與 Log 標籤
    stock_ids = list(stock_records.keys())

    # 清理並提取股票代號清單 (一步到位)
    """
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
    """
    stock_name_dict, dl = get_stock_name_dict()

    print("🚀 【錢塘潮選股系統】啟動掃描...")
    print(f"📡 讀取來源：{stock_data} | 批量抓取 {len(stock_ids)} 檔股票資料 ({start_str} ~ {today_str})...")

    # 3. 批量抓取日 K 線與籌碼資料
    global_df = fm_get_complete_stock_data(dl, stock_records, start_str, today_str)
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
    
    grouped = global_df.groupby("stock_id")

    for stock_id, group_df in grouped:
        sid = str(stock_id)
        if sid not in stock_records:
            continue

        meta = stock_records[sid]
        stock_name = meta.get("name", stock_name_dict.get(sid, sid))
        stock_cat = meta.get("category", "MID100")

        sorted_df = group_df.sort_values("date").copy()
        if sorted_df.empty or len(sorted_df) < 5:
            continue

        # 呼叫核心檢測引擎
        hits = scan_single_stock(
            df_single=sorted_df,
            category=stock_cat,
            func_list=strategies,
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

    # ====================================================
    # 1. 檢查今日是否有任何策略觸發個股
    # ====================================================
    if not stock_dashboard:
        print("ℹ️ [提示] 今日無任何策略觸發符合條件之個股，終止 Excel 報表匯出與 NAS 備份。")
        return  # 若這段程式碼在函數內請用 return；若在主程式層級可用 sys.exit(0)

    
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

            #sheet_label = data_list["選股公式"] if data_list else func_name
            sheet_label = data_list[0].get("選股公式", func_name) if data_list else func_name
            sheet_df.to_excel(writer, sheet_name=sheet_label, index=False)

    print(f"\n🎉 掃描完成！終極選股報告已成功匯出至：【{file_path}】")

    # 自動備份與同步至 NAS (若環境變數已設定)
    if os.path.exists(file_path) and os.getenv("NAS_SFTP_PATH"):
        remote_path = f"{os.getenv('NAS_SFTP_PATH')}/qiantang_daily_scan/{file_name}"
        try:
            archive_and_cleanup(file_path, remote_path)
            print(f"📦 已同步將 Excel 報告備份至 NAS 遠端：{remote_path}")
        except Exception as e:
            print(f"⚠️ NAS 備份跳過或失敗: {e}")

if __name__ == "__main__":
    print("mian_qiantang_Strategy.py")
    
    parser = argparse.ArgumentParser(description="錢塘潮選股系統 CLI 介面")
    parser.add_argument("-d", "--target_date", type=str, default=None, help="指定掃描日期 (YYYY-MM-DD)")
    parser.add_argument("-s", "--stock_file", type=str, default=None, help="指定股票池 CSV 檔案路徑")
    parser.add_argument("-m", "--mode", type=str, default=None, help="指定執行模式 (csv / noncsv)")

    args = parser.parse_args()

    # 判斷觸發來源是否為 GitHub Actions 自動排程
    is_schedule = (os.getenv("GITHUB_EVENT_NAME") == "schedule")

    # =====================================================================
    # 🎯 核心邏輯：自動排程 (3個參數缺一不可) vs 手動執行 (支援免傳參預設值)
    # =====================================================================
    if is_schedule:
        # 1. 解析三大參數 (日期可備援讀取環境變數 CREATED_AT_DATE)
        target_date = args.target_date.strip() if args.target_date else os.getenv("CREATED_AT_DATE")
        mode = args.mode.strip() if args.mode else None
        stock_file = args.stock_file.strip() if args.stock_file else None

        # 🛑【排程嚴格防呆】檢查 3 個參數是否齊全
        missing_params = []
        if not target_date:
            missing_params.append("日期 (-d / CREATED_AT_DATE)")
        if not mode:
            missing_params.append("模式 (-m)")
        if not stock_file:
            missing_params.append("股票池檔案 (-s)")

        # 只要缺少任意一個參數，立即中止執行
        if missing_params:
            print(f"❌ [安全攔截] 自動排程執行失敗！缺少必要參數：{', '.join(missing_params)}，安全終止。")
            sys.exit(1)

        print(f"⏰ [自動排程] 三大參數傳入成功 ➔ 日期: {target_date} | 模式: {mode} | 檔案: {stock_file}")

    else:
        # 2. 手動執行 (本機 IDE / 終端機 / GitHub UI 點擊)
        # 未帶參數時，自動使用全域預設值
        target_date = args.target_date.strip() if args.target_date else GLOBAL_TEST_DATE
        mode = args.mode if args.mode else STOCK_MODE
        stock_file = args.stock_file if args.stock_file else STOCK_INPUT

        print(f"🧪 [手動執行] 參數載入完成 ➔ 日期: {target_date} | 模式: {mode} | 檔案: {stock_file}")

    # =====================================================================
    # 🚀 打包參數並啟動選股引擎
    # =====================================================================
    scan_kwargs = {
        "target_date": target_date,
        "stock_mode": mode,
        "stock_data": stock_file
    }

    print(f"🚀 啟動選股流程，最終傳入參數: {scan_kwargs}")
    run_qiantang_strategy_excel_scan(**scan_kwargs)
    
"""
if __name__ == "__main__":

    print("mian_qiantang_Strategy.py")
    
    # 若 CLI 命令有傳入檔名參數（如 python test_qiantang_Strategy.py data/watch_list.csv）
    # sys.argv[1] 即可拿到第一個參數，否則退回預設值
    if len(sys.argv) > 1: #自動排程會傳入檔案, 執行此敘述
        print(f"🚀 排程執行，讀取 CSV 檔案：{csv_file_path}")
        
        csv_file_path = sys.argv[1]
        run_qiantang_strategy_range_scan(
            stock_source="csv",
            stock_input=csv_file_path
        )
        
    else:
        print(f"🚀 手動強制測試或者自動排成未傳入檔案")
        
        run_qiantang_strategy_excel_scan() #手動強制執行, 則執行此段, 執行那些股票由程式開頭的STOCK_INPUT決定
"""
