# main_qiantang_Strategy.py
"""
===============================================================================
錢塘潮選股系統 - 每日實盤/測試掃描主程式 (main_qiantang_Strategy.py)
===============================================================================

【核心設計說明與參數機制】：
1. 傳入參數 (Passed Arguments) vs. 預設參數 (Default Parameters)：https://github.com/Shang0224/tw-stock-auto-scan/blob/main/main_qiantang_Strategy.py
   - CLI 命令行傳入 (-d, -s, -m) 具備最高優先權。
   - 若未傳入參數，系統自動備退採用控制面板預設值 (STOCK_MODE, STOCK_INPUT, GLOBAL_TEST_DATE)。

2. 自動環境感知與日期雙軌決策 (is_schedule 自動判斷)：
   - 函數內部直接讀取 `os.getenv("GITHUB_EVENT_NAME") == "schedule"` 判斷執行環境，無需手動傳遞開關參數。
   
   - 【🧪 測試模式 (is_schedule = False)】:
     - 若使用者明確傳入 -d 指定日期 (如 '2024-05-20')：系統 100% 採用該指定歷史日期進行掃描，
       並自動將資料擷取區間回溯 150 天，不強制歸位至大盤最新交易日，確保歷史回測精準性。
     - 若未傳入日期 (None)：自動採用大盤最新已收盤交易日 (max_market_date)。

   - 【📅 排程模式 (is_schedule = True)】:
     - 由 GitHub Actions Cron 自動發動。
     - 自動比對傳入之 create_day (target_date) 與大盤資料庫 (TAIEX)。
     - 若傳入日期無大盤資料 (如颱風假休市、週末，或 GitHub Actions 跨夜延遲至隔日凌晨)：
       啟動「大盤最新日期自動校正機制」，自動將掃描日期歸位至大盤最後一個已收盤交易日 (max_market_date)，
       確保 Excel 標籤、K 線價量與大盤指標三方 100% 精準對齊，防止數據空白。

3. 雙重日期觀察與報表輸出：
   - 在 Console 控制台印出「日期對比觀察區塊」。
   - 在 Excel 報表中同時輸出「掃描交易日」與「傳入建立日(create_day)」欄位，方便比對記錄。
===============================================================================
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
import pandas as pd
from utils.notifier import send_line_message, send_email_with_attachment


# -----------------------------------------------------------------------------
# 1. 匯入核心執行引擎與預處理
# -----------------------------------------------------------------------------
from strategy.engine import (
    scan_single_stock,
    preprocess_all_technical_indicators,
)
from strategy.config import BUY_PARAM_PROFILES

# -----------------------------------------------------------------------------
# 2. 匯入多方選股策略
# -----------------------------------------------------------------------------
from strategy.qiantang_strategies import (
    st_qiantang_f1_spt_growth,              # F1: 筆張現形
    st_qiantang_f2_volume_breakout,         # F2: 出量上輕
    st_qiantang_f3_after_shakeout_mid100,  # F3: MID100 雙策略共振實戰總控旗艦版
    #st_qiantang_f4_strong_rise,             # F4: 強力上
    #st_qiantang_f5_major_buy_easy,          # F5: 主外上輕
    #st_qiantang_f6_flower,                  # F6: 一朵花
    #st_qiantang_f7_super_stock,             # F7: 飆股
)

# -----------------------------------------------------------------------------
# 3. 匯入資料抓取與工具庫 (含大盤 EMA 快查工具)
# -----------------------------------------------------------------------------
from utils import (
    archive_and_cleanup,
    fm_get_complete_stock_data,
    get_stock_name_dict,
    parse_and_validate_stocks,
    fetch_market_ema_dict,                 # 大盤數據與 EMA 秒查字典工具
)

# =============================================================================
# 🎛️ 全域預設參數與控制面板 (Default Configuration)
# =============================================================================
# 說明：當外部 CLI 命令列或函式未傳入指定參數時，系統預設採用的控制變數

TEST_QIANTANG_STRATEGY = [
    st_qiantang_f1_spt_growth,              # F1: 筆張現形
    st_qiantang_f2_volume_breakout,         # F2: 出量上輕
    st_qiantang_f3_after_shakeout_mid100,  # F3: 洗盤後 MID100 雙策略共振實戰版
    #st_qiantang_f4_strong_rise,             # F4: 強力上
    #st_qiantang_f5_major_buy_easy,          # F5: 主外上輕
    #st_qiantang_f6_flower,                  # F6: 一朵花
    #st_qiantang_f7_super_stock,             # F7: 飆股
]

STOCK_MODE = "csv"                          # 預設股票池讀取模式 ('csv' 或 'noncsv')
#STOCK_INPUT = "data/MID100.csv"             # 預設股票池輸入檔案路徑
#STOCK_INPUT = "data/ICDesignList.csv,data/MID100.csv"
STOCK_INPUT = "data/TestData/qiantang_ICDesign_test.csv,data/TestData/qiantang_mid100_test.csv,data/TestData/qiantang_tw50_test.csv"
#STOCK_INPUT = "data/ICDesignList.csv,data/MID100.csv,data/TW50.csv"
#STOCK_INPUT = "data/ICDesignList.csv,data/TW50.csv"
GLOBAL_TEST_DATE = "2016-07-26" #None                     # 預設單機測試指定日期 (None 代表自動定位大盤最新交易日)


# =============================================================================
# 🛠️ 輔助工具：籌碼股數安全轉換為張數
# =============================================================================
def safe_lots_from_shares(val) -> int:
    """將股數 (Shares) 安全轉換為整數張數 (Lots, 1張=1000股)"""
    if val is None or pd.isna(val):
        return 0
    try:
        return int(round(float(val) / 1000.0))
    except (ValueError, TypeError):
        return 0


# =============================================================================
# 🔍 單日個股掃描與觸發紀錄組裝核心
# =============================================================================
def scan_qiantang_strategy_day(
    day_str: str,
    global_df: pd.DataFrame,
    stocks_dict: dict[str, dict],
    strategies: list,
    profiles_map: dict = BUY_PARAM_PROFILES,
    market_info: dict = None,
    create_day_str: str = None,
) -> list[dict]:
    """
    單日個股選股掃描核心
    
    【參數說明】：
    - day_str (str): 實際進行掃描與數據對齊的交易日 (YYYY-MM-DD)
    - global_df (pd.DataFrame): 包含所有個股的歷史日 K 線與籌碼特徵 DataFrame
    - stocks_dict (dict): 經解析驗證後的目標股票清單字典
    - strategies (list): 欲執行檢測的策略函數清單
    - profiles_map (dict): 策略買入參數設定檔
    - market_info (dict): 當日大盤 (TAIEX) 的風控與 EMA 均線特徵字典
    - create_day_str (str): 外部傳入之原始建立日期 (create_day)，用於記錄與比對
    """
    day_hits = []
    stock_name_dict, _ = get_stock_name_dict()
    grouped = global_df.groupby("stock_id")

    for stock_id, group_df in grouped:
        sid = str(stock_id)
        if sid not in stocks_dict:
            continue

        meta = stocks_dict[sid]
        #stock_name = meta.get("name", stock_name_dict.get(sid, sid))
        stock_name = meta.get("name")
        stock_cat = meta.get("category", "MID100")

        sorted_df = group_df.sort_values("date").copy()
        if sorted_df.empty or len(sorted_df) < 60:
            continue

        # 🌟 核心修正：將選股池分類寫入 Dataframe，供 MID100 / TW50 / ICDesign 策略模組讀取
        sorted_df["category"] = stock_cat
       
        if not market_info:
            print(f"\n\n{sys._getframe().f_code.co_name} [{sid}] {stock_name} ({stock_cat}) {day_str} 日無大盤資料終止" )
      
        print(f"\n\n{sys._getframe().f_code.co_name} [{sid}] {stock_name} ({stock_cat}) 開始掃描************************************" )
       
        # 呼叫核心策略檢測引擎
        hits = scan_single_stock(
            df_single=sorted_df,
            func_list=strategies,
            param_profiles=profiles_map,
            market_info=market_info,
        )

        if hits:
            # 1. 取得確認日 (Confirmation Date / Tbase) 基礎 K 線價格與成交量
            latest_row = sorted_df.iloc[-1]
            close_price = round(float(latest_row["close"]), 2)
            vol_today = float(latest_row.get("Trading_Volume", 0))
            vol_lots = int(vol_today / 1000)
            amount_100m = round(float(vol_today * close_price / 100_000_000.0), 2)

            for hit in hits:
                strat_name = hit.get("選股策略", hit.get("選股公式", hit.get("strategy_name", "未知策略")))

                # 2. 精準定位 T0 發動日相對資料列 row_t0 (考量 delay_days 機制)
                try:
                    delay_days_val = int(hit.get("delay_days", 0))
                except (ValueError, TypeError):
                    delay_days_val = 0

                t0_pos = -(1 + delay_days_val)
                if len(sorted_df) >= abs(t0_pos):
                    row_t0 = sorted_df.iloc[t0_pos]
                else:
                    row_t0 = latest_row

                # -------------------------------------------------------------
                # 📌 欄位 1: 基礎標的識別與雙日期觀察對照
                # -------------------------------------------------------------
                hit_record = {
                    "掃描交易日": day_str,
                    "傳入建立日(create_day)": create_day_str if create_day_str else day_str,
                    "股票代號": sid,
                    "名稱": stock_name,
                    "選股池分類": stock_cat,
                    "今日收盤": close_price,
                    "今日成交量(張)": vol_lots,
                    "成交金額(億元)": amount_100m,
                    "選股策略": strat_name,
                }

                # -------------------------------------------------------------
                # 🌟 欄位 2: 策略動態回傳資料 (由策略自主掌控欄位輸出)
                # -------------------------------------------------------------
                for key, value in hit.items():
                    if key in ["strategy_name", "選股公式", "選股策略"]:
                        continue
                    if key not in hit_record and value not in ("N/A", "", None):
                        hit_record[key] = value

                # -------------------------------------------------------------
                # 🛡️ 欄位 3: 當日大盤風控資訊 (維持確認日大盤對齊)
                # -------------------------------------------------------------
                if market_info and isinstance(market_info, dict):
                    m_close = float(market_info.get("taiex_close", 0))
                    m_ma60 = float(market_info.get("taiex_MA60", 0))

                    hit_record.update({
                        "大盤位階": ("大盤>MA60" if (m_close > 0 and m_ma60 > 0 and m_close > m_ma60) else "大盤<=MA60"),
                        "大盤當日漲跌幅(%)": round(float(market_info.get("taiex_change_pct", 0)), 2),
                        "大盤EMA60斜率": round(float(market_info.get("taiex_EMA60_slope", 0)), 4),
                        "大盤季線乖離率(%)": round(float(market_info.get("taiex_ma60_bias_pct", 0)), 2),
                        "大盤年線乖離率(%)": round(float(market_info.get("taiex_ma240_bias_pct", 0)), 2),
                    })

                # -------------------------------------------------------------
                # 🧬 欄位 4: T0 發動日技術面與籌碼基因特徵 (根據 row_t0 提取)
                # -------------------------------------------------------------
                hit_record.update({
                    "實體K棒比例(%)": round(float(row_t0.get("body_ratio", 0)), 2),
                    "上影線比例(%)": round(float(row_t0.get("upper_shadow_ratio", 0)), 2),
                    "是否紅K": bool(row_t0.get("is_red_k", True)),
                    "距52週高點(%)": round(float(row_t0["dist_to_52w_high_pct"]), 2) if ("dist_to_52w_high_pct" in row_t0 and pd.notnull(row_t0["dist_to_52w_high_pct"])) else "N/A",
                    "打底沉澱天數": int(row_t0.get("base_consolidation_days", 0)),

                    "單筆均張(SPT)": round(float(row_t0.get("shares_per_trans", 0)), 2),
                    "輕鬆線乖離率(%)": round(float(row_t0.get("easy_line_bias", 0)), 2),
                    "輕鬆線OLS斜率": round(float(row_t0.get("easy_line_slope", 0)), 4),
                    "季線乖離率(%)": round(float(row_t0.get("ma60_bias", 0)), 2),
                    "年線乖離率(%)": round(float(row_t0["ma240_bias"]), 2) if ("ma240_bias" in row_t0 and pd.notnull(row_t0["ma240_bias"])) else "N/A",
                    "年線扣抵位置(%)": round(float(row_t0["ma240_deduct_bias"]), 2) if ("ma240_deduct_bias" in row_t0 and pd.notnull(row_t0["ma240_deduct_bias"])) else "N/A",
                    "均線多頭排列": bool(row_t0.get("is_bull_alignment", False)),
                    "均線糾結度(%)": round(float(row_t0["ma_tangle_ratio"]), 2) if ("ma_tangle_ratio" in row_t0 and pd.notnull(row_t0["ma_tangle_ratio"])) else "N/A",

                    "外資買超(張)": safe_lots_from_shares(row_t0.get("Foreign_Investor")),
                    "投信買超(張)": safe_lots_from_shares(row_t0.get("Investment_Trust")),
                    "主力買超(張)": safe_lots_from_shares(row_t0.get("major_net")),
                    "外資近5日累計(張)": safe_lots_from_shares(row_t0.get("foreign_5d_shares_sum")),
                    "投信近5日累計(張)": safe_lots_from_shares(row_t0.get("trust_5d_shares_sum")),
                    "主力近5日累計(張)": safe_lots_from_shares(row_t0.get("major_5d_shares_sum")),
                    "融資當日增減(張)": safe_lots_from_shares(row_t0.get("margin_diff_shares")),
                })

                day_hits.append(hit_record)

    return day_hits


# =============================================================================
# 🚀 每日實盤掃描與匯出主函式 (含環境感知與雙軌日期校正)
# =============================================================================
def run_qiantang_strategy_excel_scan(
    stock_mode: str = STOCK_MODE,
    stock_data: str = STOCK_INPUT,
    strategies: list = TEST_QIANTANG_STRATEGY,
    target_date: str = None,
):
    """
    執行錢塘潮多方選股掃描並產出包含 MID100 評等之 Excel 儀表板
    
    【傳入參數說明 (Function Parameters)】：
    - stock_mode (str): 股票池讀取模式，預設採用 STOCK_MODE ("csv")
    - stock_data (str): 股票池檔案路徑，預設採用 STOCK_INPUT ("data/MID100.csv")
    - strategies (list): 欲檢測之策略清單，預設採用 TEST_QIANTANG_STRATEGY
    - target_date (str): 傳入之掃描/建立日期 (create_day)，形式為 "YYYY-MM-DD"。
                         若未傳入 (None)，將根據執行環境自動決策。
    """
    if not strategies:
        raise ValueError("❌ [錯誤] 未指定 TEST_QIANTANG_STRATEGY 策略清單！")

    # 1. 自動感知 GitHub Actions 執行環境
    # 說明：若 GITHUB_EVENT_NAME 環境變數等於 "schedule"，代表由 GitHub 伺服器定時 Cron 排程觸發
    is_schedule = (os.getenv("GITHUB_EVENT_NAME") == "schedule")

    # 2. 時間設定 (UTC+8 台灣時間)
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    today_str = tw_time.strftime("%Y-%m-%d")

    # 3. 解析股票清單
    stock_records = parse_and_validate_stocks(
        stock_mode=stock_mode, 
        stock_data=stock_data
    )

    if not stock_records:
        print(f"❌ [錯誤] 無法解析股票清單 ({stock_data})。")
        return

    stock_ids = list(stock_records.keys())
    _, dl = get_stock_name_dict()

    print("🚀 【錢塘潮選股系統】啟動選股掃描流程...")

    # =========================================================================
    # 🌟 4. 雙軌日期決策機制 (測試模式強制採用 vs 排程模式自動校正)
    # =========================================================================
    passed_in_create_day = target_date

    if not is_schedule and passed_in_create_day:
        # 🧪 【情境 A：測試模式且明確傳入指定日期 (Non-Schedule + target_date)】
        # 邏輯：使用者手動或測試時指定特定日期 (如 '2024-05-20')，100% 採用該日期進行歷史回測，
        #       資料擷取區間自動設為 [指定日期 - 400天 ~ 指定日期]，不強制歸位至最新交易日。
        scan_date_str = passed_in_create_day
        target_dt = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
        start_str = (target_dt - timedelta(days=400)).strftime("%Y-%m-%d")

        print("📡 正在擷取指定測試日期之大盤 (TAIEX) 均線與風控數據...")
        market_dict = fetch_market_ema_dict(dl, start_str, scan_date_str)
        calib_status = f"🧪 [測試模式] 強制採用傳入指定日期 [{scan_date_str}] 作為掃描交易日 (歷史回測模式)"

    else:
        # 📅 【情境 B：排程模式 或 未指定日期 (Schedule 或 target_date=None)】
        # 邏輯：由排程觸發或未傳入日期時，擷取近 150 天大盤資料，並進行大盤最新收盤日歸位校正。
        start_str = (tw_time.date() - timedelta(days=400)).strftime("%Y-%m-%d")

        print("📡 正在擷取大盤 (TAIEX) 均線與風控數據以進行日期校正...")
        market_dict = fetch_market_ema_dict(dl, start_str, today_str)
        latest_market_date = max(market_dict.keys()) if market_dict else today_str

        # 檢視傳入日期是否有效且包含於大盤資料庫中
        if passed_in_create_day and market_dict and (passed_in_create_day in market_dict):
            scan_date_str = passed_in_create_day
            calib_status = f"✅ 傳入日期有效且存在於大盤交易日，採用傳入日期 [{scan_date_str}]"
        else:
            scan_date_str = latest_market_date
            if passed_in_create_day:
                calib_status = f"⚠️ 傳入日期 [{passed_in_create_day}] 無大盤資料 (可能為假日或跨夜延遲)，自動歸位至大盤最新交易日 [{scan_date_str}]"
            else:
                calib_status = f"🎯 未指定傳入日期，自動採用大盤最新收盤交易日 [{scan_date_str}]"

    # 輸出 Console 日誌比對區塊
    print("\n" + "=" * 75)
    print("🔍 【日期對比與環境感知觀察區塊】")
    print(f"  ► 執行環境感知 (is_schedule)       : 【{'📅 定時排程模式 (Schedule)' if is_schedule else '🧪 單機/測試模式 (Non-Schedule)'}】")
    print(f"  ► 傳入之 create_day (target_date) : 【{passed_in_create_day if passed_in_create_day else '未指定 (None)'}】")
    print(f"  ► 最終定案之掃描交易日 (scan_date) : 【{scan_date_str}】")
    print(f"  ► 日期校正狀態說明                 : {calib_status}")
    print(f"  ► 模式 - 檔案                 : {stock_mode} - {stock_data}")
    print("=" * 75 + "\n")

    # 5. 批量抓取個股日 K 線與籌碼資料 (抓取至 scan_date_str)
    print(f"📡 讀取來源：{stock_data} | 監控 {len(stock_ids)} 檔股票數據 ({start_str} ~ {scan_date_str})...")
    global_df = fm_get_complete_stock_data(dl, stock_records, start_str, scan_date_str)
    if global_df.empty:
        print("❌ [錯誤] FinMind 數據抓取為空，結束執行。")
        return

    # 6. 全域技術指標與籌碼特徵預處理
    print("⚡ 正在執行全域技術面與籌碼特徵預處理...")
    global_df = preprocess_all_technical_indicators(global_df)
    print("✅ 全域指標預處理完成！\n")

    # 7. 取得當日大盤風控資料
    market_info = market_dict.get(scan_date_str) if market_dict else None

    # 8. 呼叫單日掃描核心組裝當日觸發紀錄
    print("⚡ 呼叫 scan_qiantang_strategy_day 進行策略邏輯檢測與資料組裝...\n")
    day_hits = scan_qiantang_strategy_day(
        day_str=scan_date_str,
        global_df=global_df,
        stocks_dict=stock_records,
        strategies=strategies,
        profiles_map=BUY_PARAM_PROFILES,
        market_info=market_info,
        create_day_str=passed_in_create_day,
    )

    # 9. 無觸發結果防呆保護
    if not day_hits:
        print("ℹ️ [提示] 今日無任何策略觸發符合條件之個股，安全結束 Excel 報表產出。")
        return

    # 10. 彙整 Dashboard 儀表板與各策略獨立分頁
    results_by_strat = {}
    stock_dashboard = {}

    for hit in day_hits:
        sid = hit["股票代號"]
        strat_name = hit["選股策略"]

        if strat_name not in results_by_strat:
            results_by_strat[strat_name] = []
        results_by_strat[strat_name].append(hit)

        if sid not in stock_dashboard:
            stock_dashboard[sid] = {
                "掃描交易日": hit["掃描交易日"],
                "傳入建立日(create_day)": hit["傳入建立日(create_day)"],
                "股票代號": sid,
                "名稱": hit["名稱"],
                "收盤": hit["今日收盤"],
                "成交量(張)": hit["今日成交量(張)"],
                "符合策略清單": [strat_name],
            }
        else:
            if strat_name not in stock_dashboard[sid]["符合策略清單"]:
                stock_dashboard[sid]["符合策略清單"].append(strat_name)

    dashboard_rows = []
    for item in stock_dashboard.values():
        strats = item["符合策略清單"]
        row = {
            "掃描交易日": item["掃描交易日"],
            "傳入建立日(create_day)": item["傳入建立日(create_day)"],
            "股票代號": item["股票代號"],
            "名稱": item["名稱"],
            "收盤": item["收盤"],
            "成交量(張)": item["成交量(張)"],
            "符合策略總數": len(strats),
            "符合策略明細": "、".join(strats),
        }
        dashboard_rows.append(row)

    # 11. 產出 Excel 多工作表 (Multi-Sheet) 報告
    # 判斷是否為自動排程執行 (GitHub Actions 排程事件為 'schedule')
    is_scheduled = os.getenv("GITHUB_EVENT_NAME") == "schedule"
    prefix = "" if is_scheduled else "測試_"

    file_name = f"{prefix}錢塘潮選股報告_{tw_time.strftime('%Y%m%d_%H%M')}.xlsx"
    file_path = os.path.abspath(file_name)
   
    # 11. 產出 Excel 多工作表 (Multi-Sheet) 報告
    file_name = f"錢塘潮選股報告_{tw_time.strftime('%Y%m%d_%H%M')}.xlsx"
    file_path = os.path.abspath(file_name)

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        dashboard_df = pd.DataFrame(dashboard_rows).sort_values(
            by="符合策略總數", ascending=False
        )
        dashboard_df.to_excel(writer, sheet_name="🎯 綜合強勢股儀表板", index=False)

        for strat_name, data_list in results_by_strat.items():
            if data_list:
                sheet_df = pd.DataFrame(data_list)
                safe_sheet_name = str(strat_name)[-31:]
                sheet_df.to_excel(writer, sheet_name=safe_sheet_name, index=False)

    print(f"🎉 掃描完成！選股報告已匯出至：【{file_path}】")


    # =========================================================================
    # 🌟 12. 發送 LINE 簡報與 Email 詳細報告 (LINE 與 Email 共用卡片訊息)
    # =========================================================================
    print("📡 正在發送選股結果通知 (LINE & Email)...")
    try:
        # ---------------------------------------------------------------------
        # 📝 A. 建立共用之卡片式精簡訊息 (含 6 大風控特徵與操作建議)
        # ---------------------------------------------------------------------
        card_lines = [
            f"📅 【錢塘潮選股】觸發速報 ({scan_date_str})",
            f"=== 🎯 觸發個股清單 (共 {len(day_hits)} 筆訊號) ===\n"
        ]

        for idx, hit in enumerate(day_hits, start=1):
            sid = hit.get("股票代號", "")
            sname = hit.get("名稱", "")
            strat = hit.get("選股策略", "")
            close_px = hit.get("今日收盤", "")
            cat = hit.get("選股池分類", "")

            # 提取 6 大關鍵策略風控資訊 (若缺值自動補 N/A)
            pos = hit.get("建議部位", "N/A")
            sl = hit.get("停損價格", "N/A")
            win = hit.get("最佳績效", "N/A")
            dd = hit.get("最大回檔", "N/A")
            adv = hit.get("操作建議", "N/A")
            doc = hit.get("策略文件", "N/A")

            card = (
                f"🔹 [{sid}] {sname} ({cat})\n"
                f"   • 觸發策略: {strat}\n"
                f"   • 今日收盤: ${close_px}\n"
                f"   • 建議部位: {pos}\n"
                f"   • 停損價格: {sl}\n"
                f"   • 最佳績效: {win}\n"
                f"   • 最大回檔: {dd}\n"
                f"   • 操作建議: {adv}\n"
                f"   • 策略文件: {doc}\n"
            )
            card_lines.append(card)

        formatted_content = "\n".join(card_lines)

        # ---------------------------------------------------------------------
        # 📱 B. 發送 LINE 訊息 (加上 4500 字上限防呆截斷)
        # ---------------------------------------------------------------------
        line_msg = formatted_content
        if len(line_msg) > 4500:
            line_msg = line_msg[:4400] + "\n\n⚠️ (訊息內容較長，完整資料請參閱 Email 與 Excel 附件)"
        
        send_line_message(line_msg)

        # ---------------------------------------------------------------------
        # 📧 C. 發送 Email (內文帶入同樣訊息 + 附帶 Excel 附件)
        # ---------------------------------------------------------------------
        sender_email = os.getenv("SENDER_EMAIL")
        recipient_email = os.getenv("RECIPIENT_EMAIL")
        app_password = os.getenv("EMAIL_APP_PASSWORD")

        if sender_email and recipient_email and app_password:
            email_subject = f"📊 錢塘潮選股每日報告 - {scan_date_str} (共 {len(day_hits)} 筆觸發)"
            
            email_body = (
                f"您好：\n\n"
                f"【錢塘潮選股系統】已完成 {scan_date_str} 交易日之選股掃描。\n\n"
                f"{formatted_content}\n"
                f"=================================================================\n"
                f"💡 完整的綜合儀表板與各策略獨立 Sheet 分頁，請參閱隨信附帶之 Excel 附件：\n"
                f"   【{file_name}】\n\n"
                f"祝 投資順利！\n"
                f"錢塘潮自動選股系統 敬上"
            )

            send_email_with_attachment(
                file_paths=file_path,
                recipient_email=recipient_email,
                sender_email=sender_email,
                app_password=app_password,
                subject=email_subject,
                body=email_body,
            )
        else:
            print("⚠️ [Email 提示] 缺少 SENDER_EMAIL / RECIPIENT_EMAIL / EMAIL_APP_PASSWORD 環境變數，跳過 Email 發送。")

    except Exception as notify_err:
        print(f"⚠️ [通知發送失敗] 發生預期外錯誤: {notify_err}")

    # 12. 自動同步至 NAS 遠端備份
    if os.path.exists(file_path) and os.getenv("NAS_SFTP_PATH"):
        remote_path = f"{os.getenv('NAS_SFTP_PATH')}/qiantang_daily_scan/{file_name}"
        try:
            archive_and_cleanup(file_path, remote_path)
            print(f"📦 已成功將 Excel 報告備份至 NAS 遠端：{remote_path}")
        except Exception as e:
            print(f"⚠️ NAS 備份過程跳過或失敗: {e}")

# =============================================================================
# 🏁 程式執行進入點 (CLI Entry Point)
# =============================================================================
if __name__ == "__main__":
    print("🚀 正在啟動 main_qiantang_Strategy.py 主選股程式...")
    
    # 解析 CLI 命令列傳入參數 (Passed Arguments)
    parser = argparse.ArgumentParser(description="錢塘潮選股系統 CLI 介面")
    parser.add_argument("-d", "--target_date", type=str, default=None, help="指定掃描日期 (YYYY-MM-DD)")
    parser.add_argument("-s", "--stock_file", type=str, default=None, help="指定股票池 CSV 檔案路徑")
    parser.add_argument("-m", "--mode", type=str, default=None, help="指定執行模式 (csv / noncsv)")

    args = parser.parse_args()

    # 判斷是否為 GitHub Actions 排程模式
    is_sched = (os.getenv("GITHUB_EVENT_NAME") == "schedule")

    # -------------------------------------------------------------------------
    # ⚖️ 傳入參數 (CLI Passed) vs. 預設參數 (Default Config) 決策流程
    # -------------------------------------------------------------------------
    if is_sched:
        # 排程模式：優先採用 CLI -d 傳入值；若無，則採用環境變數中的 TW_CREATED_DATE
        target_date = args.target_date.strip() if args.target_date else (
            os.getenv("TW_CREATED_DATE", os.getenv("CREATED_AT_DATE"))
        )
    else:
        # 測試模式：優先採用 CLI -d 傳入值；若無，採用全域測試預設值 GLOBAL_TEST_DATE
        target_date = args.target_date.strip() if args.target_date else GLOBAL_TEST_DATE

    # 模式與股票池檔案：優先採用 CLI -m / -s 傳入值；若無，採用全域預設值 STOCK_MODE / STOCK_INPUT
    mode = args.mode.strip() if args.mode else STOCK_MODE
    stock_file = args.stock_file.strip() if args.stock_file else STOCK_INPUT

    # 呼叫主掃描函式 (無需傳遞 is_schedule，內部會自動感測)
    run_qiantang_strategy_excel_scan(
        stock_mode=mode,
        stock_data=stock_file,
        target_date=target_date,
    )
