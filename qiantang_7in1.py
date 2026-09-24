import datetime
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

# 🌟 匯入專屬的 utils 程式庫工具（包含 fm_get_complete_stock_data 批量抓取元件）
from utils import (
    align_and_normalize_results,
    archive_and_cleanup,
    calculate_one_year_extremes,
    fm_fetch_all_stocks,
    fm_get_complete_stock_data,  # 關鍵：批量一次性抓取 FinMind 全部資料
    get_fm_trading_days,
    get_stock_name_dict,
    parse_stock_ids,
    save_multi_day_report,
    send_email_report,
    send_qiantang_7in1_line_summary,
)

STOCK_INPUT = os.getenv("STOCK_FILES", "data/MID100.csv")


def calculate_kd(df, n=9, m1=3, m2=3):
    """計算技術指標 KD (適應 FinMind 欄位名稱 min, max, close)"""
    low_min = df["min"].rolling(window=n).min()
    high_max = df["max"].rolling(window=n).max()
    rsv = ((df["close"] - low_min) / (high_max - low_min)) * 100
    rsv = rsv.fillna(50)

    k = [50.0]
    for i in range(1, len(rsv)):
        k.append((1 / m1) * rsv.iloc[i] + ((m1 - 1) / m1) * k[-1])
    df["K"] = k

    d = [50.0]
    for i in range(1, len(df["K"])):
        d.append(
            (1 / m2) * float(df["K"].iloc[i]) + ((m2 - 1) / m2) * float(d[-1])
        )
    df["D"] = d
    return df


def run_seven_combine_filter(stock_list):

    # 取得精確的台灣時間 (UTC+8)
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)

    today_str = tw_time.strftime("%Y-%m-%d")
    start_str = (tw_time.date() - timedelta(days=90)).strftime("%Y-%m-%d")

    # 1. 取得股票字典與 FinMind DataLoader 實例
    stock_name_dict, dl = get_stock_name_dict()

    # 清理股票代號清單（確保為純數字字串並去重）
    unique_stock_ids = list(
        set(
            [
                str(sid)
                .replace(".TW", "")
                .replace(".TWO", "")
                .replace("^", "")
                for sid in stock_list
            ]
        )
    )

    print("🚀 【錢塘潮 7 合 1 終極選股系統】全面啟動掃描...")
    print(
        f"📡 正在向 FinMind 一次性批量抓取 {len(unique_stock_ids)} 檔股票之完整 K 線與籌碼資料 ({start_str} ~ {today_str})..."
    )

    # 🌟 2. 仿照監控架構：一次性向 FinMind 抓取全清單的完整資料 (K線 + 籌碼)
    global_df = fm_get_complete_stock_data(
        dl, unique_stock_ids, start_str, today_str
    )

    if global_df.empty:
        print("❌ [錯誤] FinMind 批量抓取資料為空，結束執行。")
        return

    # 將大表依 stock_id 預先分群切片，以記憶體高速讀取取代迴圈內的 API 請求
    stock_groups = {
        str(sid): group.sort_values("date").reset_index(drop=True)
        for sid, group in global_df.groupby("stock_id")
    }

    # 初始化 7 個公式的篩選結果清單
    results = {
        "F1_主力大買": [],
        "F2_一朵花": [],
        "F3_主外上輕": [],
        "F4_強力上": [],
        "F5_洗盤後": [],
        "F6_出量上輕": [],
        "F7_筆張現形": [],
    }

    # 紀錄每檔股票符合的所有公式，用來做大盤點
    stock_dashboard = {}

    print("⚡ 數據載入完成，開始進行 7 大選股公式邏輯掃描...\n")

    for stock_id in unique_stock_ids:
        try:
            clean_stock_id = str(stock_id)

            if clean_stock_id not in stock_groups:
                continue

            df_k = stock_groups[clean_stock_id].copy()

            if df_k.empty or len(df_k) < 20:
                continue

            # 轉為數值型態，防範型態異常
            numeric_cols = [
                "close",
                "min",
                "max",
                "Trading_Volume",
                "Trading_turnover",
            ]
            for col in numeric_cols:
                if col in df_k.columns:
                    df_k[col] = pd.to_numeric(df_k[col], errors="coerce")

            # 計算模擬輕鬆線 (10日 EMA) 與 5日均量 (單位：股)
            df_k["Easy_Line"] = (
                df_k["close"].ewm(span=10, adjust=False).mean()
            )
            df_k["Vol_5MA"] = df_k["Trading_Volume"].rolling(window=5).mean()
            df_k = calculate_kd(df_k)

            # 每筆成交股數 (股/筆) = 總成交股數 (Trading_Volume) / 成交筆數 (Trading_turnover)
            if (
                "Trading_turnover" in df_k.columns
                and (df_k["Trading_turnover"] > 0).any()
            ):
                df_k["Shares_Per_Trans"] = (
                    df_k["Trading_Volume"] / df_k["Trading_turnover"]
                )
            else:
                df_k["Shares_Per_Trans"] = 0

            # 最新三天的技術數據與成交量 (全程維持「股數」計算)
            close_today = float(df_k["close"].iloc[-1])
            close_yesterday = float(df_k["close"].iloc[-2])
            close_2days_ago = float(df_k["close"].iloc[-3])

            vol_today = float(df_k["Trading_Volume"].iloc[-1])  # 單位：股
            vol_yesterday = float(
                df_k["Trading_Volume"].iloc[-2]
            )  # 單位：股
            vol_5ma = float(df_k["Vol_5MA"].iloc[-1])  # 單位：股

            easy_today = float(df_k["Easy_Line"].iloc[-1])

            # 核心基本通行證
            is_above_easy_today = close_today > easy_today
            is_price_ok = close_today >= 5

            # 若不符合基本條件，直接跳過該股
            if not (is_above_easy_today and is_price_ok):
                continue

            # 定義過往洗盤軌跡
            df_k["Is_Below_Easy"] = df_k["close"] <= df_k["Easy_Line"]
            was_below_easy_1d = bool(df_k["Is_Below_Easy"].iloc[-2])
            was_below_easy_2d = bool(df_k["Is_Below_Easy"].iloc[-3])
            was_below_easy_3d = bool(df_k["Is_Below_Easy"].iloc[-4])

            # KD 黃金交叉
            df_k["KD_Cross"] = (df_k["K"] > df_k["D"]) & (
                df_k["K"].shift(1) <= df_k["D"].shift(1)
            )
            has_kd_cross_in_6d = df_k["KD_Cross"].tail(6).any()

            # 每筆成交股數遞增判斷
            s_per_t_today = float(df_k["Shares_Per_Trans"].iloc[-1])
            s_per_t_1d = float(df_k["Shares_Per_Trans"].iloc[-2])
            s_per_t_2d = float(df_k["Shares_Per_Trans"].iloc[-3])
            is_avg_shares_growing = (
                s_per_t_today > s_per_t_1d > s_per_t_2d
            )

            # ==========================================
            # 籌碼面資料處理 (直接從批量抓取的 df_k 提取三大法人)
            # ==========================================
            net_inst_buy_today = 0  # 單位：股
            is_10d_7buy = False
            is_5d_4buy = False

            # 若資料包含三大法人欄位（如 net_buy 或買賣超相關欄位）
            if "net_buy" in df_k.columns:
                daily_chip = (
                    df_k.groupby("date")["net_buy"]
                    .sum()
                    .reset_index()
                    .sort_values("date")
                )
                if len(daily_chip) >= 1:
                    net_inst_buy_today = float(daily_chip["net_buy"].iloc[-1])
                    if len(daily_chip) >= 10:
                        is_10d_7buy = (
                            daily_chip.tail(10)["net_buy"] > 0
                        ).sum() >= 7
                    if len(daily_chip) >= 5:
                        is_5d_4buy = (
                            daily_chip.tail(5)["net_buy"] > 0
                        ).sum() >= 4

            # ==========================================
            # 執行 7 大公式邏輯審查 (門檻以「股數」判斷，如 350張 = 350,000股)
            # ==========================================
            stock_name = stock_name_dict.get(clean_stock_id, "未知")
            stock_hit_formulas = []

            # 🌟 僅在顯示/輸出 Excel 時才將「股數」轉換為「張數」
            stock_info = {
                "股票代號": clean_stock_id,
                "名稱": stock_name,
                "今日收盤": round(close_today, 2),
                "今日成交量(張)": int(vol_today / 1000),
            }

            # ----------------------------------------------------------------------
            # ⚠️【公式 1：主力大買】
            # ----------------------------------------------------------------------
            # if vol_today >= 350_000 and net_inst_buy_today >= 1_000_000:
            #     results["F1_主力大買"].append(stock_info)
            #     stock_hit_formulas.append("F1_主力大買")

            # ----------------------------------------------------------------------
            # ⚠️【公式 2：一朵花】
            # ----------------------------------------------------------------------
            # if vol_today >= 350_000 and (
            #     is_10d_7buy or (vol_today >= vol_5ma * 2)
            # ):
            #     results["F2_一朵花"].append(stock_info)
            #     stock_hit_formulas.append("F2_一朵花")

            # ----------------------------------------------------------------------
            # ⚠️【公式 3：主外上輕】
            # ----------------------------------------------------------------------
            # if vol_today >= 350_000 and (is_5d_4buy or has_kd_cross_in_6d):
            #     results["F3_主外上輕"].append(stock_info)
            #     stock_hit_formulas.append("F3_主外上輕")

            # ----------------------------------------------------------------------
            # ✅【公式 4：強力上】
            # ----------------------------------------------------------------------
            if (
                vol_today >= 350_000
                and (close_today / close_yesterday >= 1.065)
                and (close_yesterday / close_2days_ago <= 1.06)
            ):
                results["F4_強力上"].append(stock_info)
                stock_hit_formulas.append("F4_強力上")

            # ----------------------------------------------------------------------
            # ✅【公式 5：洗盤後】
            # ----------------------------------------------------------------------
            if vol_today >= 350_000 and (
                was_below_easy_1d or was_below_easy_2d or was_below_easy_3d
            ):
                results["F5_洗盤後"].append(stock_info)
                stock_hit_formulas.append("F5_洗盤後")

            # ----------------------------------------------------------------------
            # ✅【公式 6：出量上輕】
            # ----------------------------------------------------------------------
            mode_a = (vol_today >= vol_yesterday * 3) and (
                vol_today >= 3_000_000
            )
            mode_b = (vol_today >= vol_yesterday * 4.5) and (
                vol_today < 3_000_000
            )
            if vol_today >= 350_000 and (mode_a or mode_b):
                results["F6_出量上輕"].append(stock_info)
                stock_hit_formulas.append("F6_出量上輕")

            # ----------------------------------------------------------------------
            # ✅【公式 7：筆張現形】
            # ----------------------------------------------------------------------
            if vol_today >= 500_000 and is_avg_shares_growing:
                results["F7_筆張現形"].append(stock_info)
                stock_hit_formulas.append("F7_筆張現形")

            # 彙整至總儀表板 (顯示時轉為張)
            if stock_hit_formulas:
                stock_dashboard[clean_stock_id] = {
                    "股票代號": clean_stock_id,
                    "名稱": stock_name,
                    "收盤": round(close_today, 2),
                    "成交量(張)": int(vol_today / 1000),
                    "符合公式總數": len(stock_hit_formulas),
                    "符合公式明細": "、".join(stock_hit_formulas),
                }
                print(
                    f"🎯 {stock_name}({clean_stock_id}) 觸發訊號！符合：{', '.join(stock_hit_formulas)}"
                )

        except Exception as e:
            print(f"❌ 處理股票 {stock_id} 時發生異常: {e}")

    # ==========================================
    # 產出多頁籤 Excel 選股報告
    # ==========================================
    file_name = f"錢塘潮選股報告_{tw_time.strftime('%Y%m%d_%H%M')}.xlsx"
    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
        # 第一頁：綜合儀表板
        if stock_dashboard:
            dashboard_df = pd.DataFrame(stock_dashboard.values()).sort_values(
                by="符合公式總數", ascending=False
            )
        else:
            dashboard_df = pd.DataFrame(
                columns=[
                    "股票代號",
                    "名稱",
                    "收盤",
                    "成交量(張)",
                    "符合公式總數",
                    "符合公式明細",
                ]
            )
        dashboard_df.to_excel(
            writer, sheet_name="🎯 綜合強勢股儀表板", index=False
        )

        # 後續頁籤：個別公式清單
        for formula_name, data_list in results.items():
            sheet_df = pd.DataFrame(data_list)
            if sheet_df.empty:
                sheet_df = pd.DataFrame(
                    columns=["股票代號", "名稱", "今日收盤", "今日成交量(張)"]
                )
            sheet_df.to_excel(writer, sheet_name=formula_name, index=False)

    print(
        f"\n🎉 掃描完成！終極報告已成功匯出至：【{os.path.abspath(file_name)}】"
    )

    prod_remote_path = (
        f"{os.getenv('NAS_SFTP_PATH')}/qiantang_7in1/{file_name}"
    )

    # 備份與清理
    print(
        f"📦 [備份啟動] 準備將 Excel 報告上傳至 NAS...\n file_name : {file_name}  prod_remote_path : {prod_remote_path}"
    )
    archive_and_cleanup(os.path.abspath(file_name), prod_remote_path)

    # 篩選出符合公式總數大於 3 個的強勢股傳至 LINE
    line_target_df = (
        dashboard_df[dashboard_df["符合公式總數"] > 3]
        if not dashboard_df.empty
        else dashboard_df
    )

    send_qiantang_7in1_line_summary(line_target_df, tw_time)


if __name__ == "__main__":
    my_watchlist = parse_stock_ids(STOCK_INPUT)
    print(f"監控清單: {my_watchlist}")
    run_seven_combine_filter(my_watchlist)
