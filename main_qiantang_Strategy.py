# main_qiantang_Strategy.py
"""
錢塘潮選股系統 - 每日實盤/測試掃描進入點與 Excel 儀表板匯出
說明：讀取指定股票池 CSV 或 Dict 執行錢塘潮多方選股策略，
      內部封裝 scan_qiantang_strategy_day 進行單日資料掃描，
      對 hit 回傳資料採用迴圈動態合流，並由策略自主掌控輸出欄位，
      同時導入 test_qiantang_Strategy.py 具備實戰參考價值之技術與籌碼特徵。
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
import pandas as pd

# 1. 匯入核心執行引擎與預處理
from strategy.engine import (
    scan_single_stock,
    preprocess_all_technical_indicators,
)
from strategy.config import BUY_PARAM_PROFILES

# 2. 匯入多方選股策略 (包含 MID100 專用共振旗艦策略)
from strategy.qiantang_strategies import (
    st_qiantang_f1_spt_growth,              # F1: 筆張現形
    st_qiantang_f2_volume_breakout,         # F2: 出量上輕
    st_qiantang_f3_after_shakeout_mid100,  # 🌟 F3: MID100 雙策略共振實戰總控旗艦版
    st_qiantang_f4_strong_rise,             # F4: 強力上
    st_qiantang_f5_major_buy_easy,          # F5: 主外上輕
    st_qiantang_f6_flower,                  # F6: 一朵花
    st_qiantang_f7_super_stock,             # F7: 飆股
)

# 3. 匯入資料抓取與工具庫 (含大盤 EMA 快查工具)
from utils import (
    archive_and_cleanup,
    fm_get_complete_stock_data,
    get_stock_name_dict,
    parse_and_validate_stocks,
    fetch_market_ema_dict,                 # 大盤數據與 EMA 秒查字典工具
)

# =====================================================================
# 🎛️ 多方策略測試控制面板
# =====================================================================

TEST_QIANTANG_STRATEGY = [
    st_qiantang_f1_spt_growth,              # F1: 筆張現形
    st_qiantang_f2_volume_breakout,         # F2: 出量上輕
    st_qiantang_f3_after_shakeout_mid100,  # 🌟 F3: 洗盤後 MID100 雙策略共振實戰版
    st_qiantang_f4_strong_rise,             # F4: 強力上
    st_qiantang_f5_major_buy_easy,          # F5: 主外上輕
    st_qiantang_f6_flower,                  # F6: 一朵花
    st_qiantang_f7_super_stock,             # F7: 飆股
]

STOCK_MODE = "csv"
STOCK_INPUT = "data/MID100.csv"             # 預設掃描 MID100 股票池
GLOBAL_TEST_DATE = None                     # 未指定日期時自動取最新營業日

# =====================================================================
# 🛠️ 輔助工具：籌碼股數安全轉張數
# =====================================================================
def safe_lots_from_shares(val) -> int:
    """將股數安全轉換為整數張數"""
    if val is None or pd.isna(val):
        return 0
    try:
        return int(round(float(val) / 1000.0))
    except (ValueError, TypeError):
        return 0

# =====================================================================
# 🔍 單日個股掃描與觸發紀錄組裝核心 (完全對齊 test_qiantang_Strategy.py 架構)
# =====================================================================
def scan_qiantang_strategy_day(
    day_str: str,
    global_df: pd.DataFrame,
    stocks_dict: dict[str, dict],
    strategies: list,
    profiles_map: dict = BUY_PARAM_PROFILES,
    market_info: dict = None,
) -> list[dict]:
    """
    單日個股選股掃描核心
    職責：走訪個股、呼叫 scan_single_stock 檢測策略。
          - 基礎標的資訊與大盤資料：保持為確認日 (Confirmation Date) 數據。
          - 技術面與籌碼基因特徵：若有 delay_days 自動精準定位至 T0 發動日數據列。
          - 策略 hit 回傳資料：由策略完全自主掌控迴圈動態輸出。
    """
    day_hits = []
    stock_name_dict, _ = get_stock_name_dict()
    grouped = global_df.groupby("stock_id")

    for stock_id, group_df in grouped:
        sid = str(stock_id)
        if sid not in stocks_dict:
            continue

        meta = stocks_dict[sid]
        stock_name = meta.get("name", stock_name_dict.get(sid, sid))
        stock_cat = meta.get("category", "MID100")

        sorted_df = group_df.sort_values("date").copy()
        if sorted_df.empty or len(sorted_df) < 60:
            continue

        # 呼叫核心檢測引擎
        hits = scan_single_stock(
            df_single=sorted_df,
            func_list=strategies,
            param_profiles=profiles_map,
            market_info=market_info,
        )

        if hits:
            # 1. 取得當日/確認日 (Confirmation Date) 的基礎 K 線資料
            latest_row = sorted_df.iloc[-1]
            close_price = round(float(latest_row["close"]), 2)
            vol_today = float(latest_row.get("Trading_Volume", 0))
            vol_lots = int(vol_today / 1000)
            amount_100m = round(float(vol_today * close_price / 100_000_000.0), 2)

            for hit in hits:
                strat_name = hit.get("選股策略", hit.get("選股公式", hit.get("strategy_name", "未知策略")))

                # 🌟 2. 精準定位 Tbase 發動日相對資料列 row_t0 (-1 - delay_days)
                try:
                    delay_days_val = int(hit.get("delay_days", 0))
                except (ValueError, TypeError):
                    delay_days_val = 0

                t0_pos = -(1 + delay_days_val)
                if len(sorted_df) >= abs(t0_pos):
                    row_t0 = sorted_df.iloc[t0_pos]
                else:
                    row_t0 = latest_row

                # =================================================================
                # 📌 1. 基礎標的識別欄位 (保持確認日資訊，完全不變)
                # =================================================================
                hit_record = {
                    "日期": day_str,
                    "股票代號": sid,
                    "名稱": stock_name,
                    "選股池分類": stock_cat,
                    "今日收盤": close_price,
                    "今日成交量(張)": vol_lots,
                    "成交金額(億元)": amount_100m,
                    "選股策略": strat_name,
                }

                # =================================================================
                # 🌟 2. 策略動態回傳資料 (Strategy Hits) ➔ 完全由策略自主管控輸出
                # =================================================================
                for key, value in hit.items():
                    if key in ["strategy_name", "選股公式", "選股策略"]:
                        continue
                    if key not in hit_record and value not in ("N/A", "", None):
                        hit_record[key] = value

                # =================================================================
                # 🛡️ 3. 當日大盤環境資訊 (保持確認日大盤資料)
                # =================================================================
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

                # =================================================================
                # 🧬 4. Tbase 發動日技術與籌碼基因特徵 (根據 delay_days 精準取用 row_t0)
                # =================================================================
                hit_record.update({
                    # K線型態與位階 (T0)
                    "實體K棒比例(%)": round(float(row_t0.get("body_ratio", 0)), 2),
                    "上影線比例(%)": round(float(row_t0.get("upper_shadow_ratio", 0)), 2),
                    "是否紅K": bool(row_t0.get("is_red_k", True)),
                    "距52週高點(%)": round(float(row_t0["dist_to_52w_high_pct"]), 2) if ("dist_to_52w_high_pct" in row_t0 and pd.notnull(row_t0["dist_to_52w_high_pct"])) else "N/A",
                    "打底沉澱天數": int(row_t0.get("base_consolidation_days", 0)),

                    # 均量與輕鬆線動能 (T0)
                    "單筆均張(SPT)": round(float(row_t0.get("shares_per_trans", 0)), 2),
                    "輕鬆線乖離率(%)": round(float(row_t0.get("easy_line_bias", 0)), 2),
                    "輕鬆線OLS斜率": round(float(row_t0.get("easy_line_slope", 0)), 4),
                    "季線乖離率(%)": round(float(row_t0.get("ma60_bias", 0)), 2),
                    "年線乖離率(%)": round(float(row_t0["ma240_bias"]), 2) if ("ma240_bias" in row_t0 and pd.notnull(row_t0["ma240_bias"])) else "N/A",
                    "年線扣抵位置(%)": round(float(row_t0["ma240_deduct_bias"]), 2) if ("ma240_deduct_bias" in row_t0 and pd.notnull(row_t0["ma240_deduct_bias"])) else "N/A",
                    "均線多頭排列": bool(row_t0.get("is_bull_alignment", False)),
                    "均線糾結度(%)": round(float(row_t0["ma_tangle_ratio"]), 2) if ("ma_tangle_ratio" in row_t0 and pd.notnull(row_t0["ma_tangle_ratio"])) else "N/A",

                    # 籌碼動向 (T0，安全轉為張數)
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

# =====================================================================
# 🚀 每日實盤掃描與 Excel 報表產出進入點
# =====================================================================
def run_qiantang_strategy_excel_scan(
    stock_mode: str = STOCK_MODE,
    stock_data: str = STOCK_INPUT,
    strategies: list = TEST_QIANTANG_STRATEGY,
    target_date: str = None,
):
    """執行錢塘潮多方選股掃描並產出包含 MID100 評等之 Excel 儀表板"""
    if not strategies:
        raise ValueError("❌ [錯誤] 未指定 TEST_QIANTANG_STRATEGY 策略清單！")

    # 1. 時間設定 (UTC+8 台灣時間)
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    
    # 決定掃描日期
    scan_date_str = target_date if target_date else tw_time.strftime("%Y-%m-%d")
    start_str = (tw_time.date() - timedelta(days=150)).strftime("%Y-%m-%d")

    # 2. 解析股票清單
    stock_records = parse_and_validate_stocks(
        stock_mode=stock_mode, 
        stock_data=stock_data
    )

    if not stock_records:
        print(f"❌ [錯誤] 無法解析股票清單 ({stock_data})。")
        return

    stock_ids = list(stock_records.keys())
    _, dl = get_stock_name_dict()

    print("🚀 【錢塘潮選股系統】啟動每日實盤/測試掃描...")
    print(f"📡 讀取來源：{stock_data} | 監控 {len(stock_ids)} 檔股票數據 ({start_str} ~ {scan_date_str})...")

    # 3. 批量抓取個股日 K 線與籌碼資料
    global_df = fm_get_complete_stock_data(dl, stock_records, start_str, scan_date_str)
    if global_df.empty:
        print("❌ [錯誤] FinMind 數據抓取為空，結束執行。")
        return

    # 4. 擷取大盤 (TAIEX) EMA 均線與風控數據字典
    print("📡 正在擷取大盤 (TAIEX) 均線與風控數據...")
    market_dict = fetch_market_ema_dict(dl, start_str, scan_date_str)

    # 5. 全域技術指標與籌碼特徵預處理
    print("⚡ 正在執行全域技術面與籌碼特徵預處理...")
    global_df = preprocess_all_technical_indicators(global_df)
    print("✅ 全域指標預處理完成！\n")

    # 6. 取得當日大盤風控資料
    market_info = market_dict.get(scan_date_str) if market_dict else None

    # 7. 呼叫單日掃描核心組裝當日觸發紀錄
    print("⚡ 呼叫 scan_qiantang_strategy_day 進行策略邏輯檢測與資料組裝...\n")
    day_hits = scan_qiantang_strategy_day(
        day_str=scan_date_str,
        global_df=global_df,
        stocks_dict=stock_records,
        strategies=strategies,
        profiles_map=BUY_PARAM_PROFILES,
        market_info=market_info,
    )

    # ====================================================
    # 🛑 核心防呆檢查：若今日無任何策略觸發個股，安全結束
    # ====================================================
    if not day_hits:
        print("ℹ️ [提示] 今日無任何策略觸發符合條件之個股，安全結束 Excel 報表產出與 NAS 備份。")
        return

    # =====================================================================
    # 📊 8. 彙整 Dashboard 儀表板與各策略獨立分頁 (使用 results_by_strat 對齊 test 架構)
    # =====================================================================
    results_by_strat = {}
    stock_dashboard = {}

    for hit in day_hits:
        sid = hit["股票代號"]
        strat_name = hit["選股策略"]

        # 收集各策略分頁數據
        if strat_name not in results_by_strat:
            results_by_strat[strat_name] = []
        results_by_strat[strat_name].append(hit)

        # 彙整綜合強勢股儀表板
        if sid not in stock_dashboard:
            stock_dashboard[sid] = {
                "日期": hit["日期"],
                "股票代號": sid,
                "名稱": hit["名稱"],
                "收盤": hit["今日收盤"],
                "成交量(張)": hit["今日成交量(張)"],
                "符合策略清單": [strat_name],
            }
        else:
            if strat_name not in stock_dashboard[sid]["符合策略清單"]:
                stock_dashboard[sid]["符合策略清單"].append(strat_name)

    # 格式化 Dashboard 列資料
    dashboard_rows = []
    for item in stock_dashboard.values():
        strats = item["符合策略清單"]
        row = {
            "日期": item["日期"],
            "股票代號": item["股票代號"],
            "名稱": item["名稱"],
            "收盤": item["收盤"],
            "成交量(張)": item["成交量(張)"],
            "符合策略總數": len(strats),
            "符合策略明細": "、".join(strats),
        }
        dashboard_rows.append(row)

    # =====================================================================
    # 💾 9. 產出 Excel 多工作表 (Multi-Sheet) 報告
    # =====================================================================
    file_name = f"錢塘潮選股報告_{tw_time.strftime('%Y%m%d_%H%M')}.xlsx"
    file_path = os.path.abspath(file_name)

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        # Sheet 1: 綜合強勢股儀表板
        dashboard_df = pd.DataFrame(dashboard_rows).sort_values(
            by="符合策略總數", ascending=False
        )
        dashboard_df.to_excel(writer, sheet_name="🎯 綜合強勢股儀表板", index=False)

        # Sheet 2~N: 個別策略詳細結果 (依 results_by_strat 動態開頁)
        for strat_name, data_list in results_by_strat.items():
            if data_list:
                sheet_df = pd.DataFrame(data_list)
                safe_sheet_name = str(strat_name)[-31:]  # Excel 工作表名稱限制 31 字
                sheet_df.to_excel(writer, sheet_name=safe_sheet_name, index=False)

    print(f"\n🎉 掃描完成！包含 MID100 評等與實戰參考基因之終極選股報告已匯出至：【{file_path}】")

    # 10. 自動同步至 NAS 備份 (若設定檔已啟用)
    if os.path.exists(file_path) and os.getenv("NAS_SFTP_PATH"):
        remote_path = f"{os.getenv('NAS_SFTP_PATH')}/qiantang_daily_scan/{file_name}"
        try:
            archive_and_cleanup(file_path, remote_path)
            print(f"📦 已成功將 Excel 報告備份至 NAS 遠端：{remote_path}")
        except Exception as e:
            print(f"⚠️ NAS 備份過程跳過或失敗: {e}")

if __name__ == "__main__":
    print("🚀 正在啟動 main_qiantang_Strategy.py 主選股程式...")
    
    parser = argparse.ArgumentParser(description="錢塘潮選股系統 CLI 介面")
    parser.add_argument("-d", "--target_date", type=str, default=None, help="指定掃描日期 (YYYY-MM-DD)")
    parser.add_argument("-s", "--stock_file", type=str, default=None, help="指定股票池 CSV 檔案路徑")
    parser.add_argument("-m", "--mode", type=str, default=None, help="指定執行模式 (csv / noncsv)")

    args = parser.parse_args()

    is_schedule = (os.getenv("GITHUB_EVENT_NAME") == "schedule")

    if is_schedule:
        target_date = args.target_date.strip() if args.target_date else os.getenv("CREATED_AT_DATE")
        mode = args.mode.strip() if args.mode else STOCK_MODE
        stock_file = args.stock_file.strip() if args.stock_file else STOCK_INPUT
    else:
        target_date = args.target_date.strip() if args.target_date else GLOBAL_TEST_DATE
        mode = args.mode if args.mode else STOCK_MODE
        stock_file = args.stock_file if args.stock_file else STOCK_INPUT

    scan_kwargs = {
        "target_date": target_date,
        "stock_mode": mode,
        "stock_data": stock_file
    }

    run_qiantang_strategy_excel_scan(**scan_kwargs)
