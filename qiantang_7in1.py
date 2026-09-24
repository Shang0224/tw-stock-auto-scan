#qiantang_7in1.py

import os
from datetime import datetime, timedelta, timezone
import pandas as pd

# 🌟 從 utils 載入預處理指標與相關工具函式
from utils import (
    align_and_normalize_results,
    archive_and_cleanup,
    fm_get_complete_stock_data,
    get_stock_name_dict,
    parse_stock_ids,
    preprocess_all_technical_indicators,  # 來自 utils/indicators.py
    send_qiantang_7in1_line_summary,
)

STOCK_INPUT = os.getenv("STOCK_FILES", "data/MID100.csv")


def run_seven_combine_filter(stock_list):

    # 取得精確的台灣時間 (UTC+8)
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)

    today_str = tw_time.strftime("%Y-%m-%d")
    start_str = (tw_time.date() - timedelta(days=120)).strftime("%Y-%m-%d")

    # 1. 取得股票字典與 FinMind DataLoader 實例
    stock_name_dict, dl = get_stock_name_dict()

    # 清理股票代號清單
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
        f"📡 正在向 FinMind 一次性批量抓取 {len(unique_stock_ids)} 檔股票資料 ({start_str} ~ {today_str})..."
    )

    # 2. 一次性抓取全部股票資料 (K線 + 三大法人籌碼)
    global_df = fm_get_complete_stock_data(
        dl, unique_stock_ids, start_str, today_str
    )

    if global_df.empty:
        print("❌ [錯誤] FinMind 批量抓取資料為空，結束執行。")
        return

    # 🌟 3. 呼叫 utils/indicators.py 的預處理函式（一次算好全域指標）
    print("⚡ 正在執行全域技術指標預處理 (from utils/indicators.py)...")
    global_df = preprocess_all_technical_indicators(global_df)
    print("✅ 全域技術指標計算完成！")

    # 將大表依 stock_id 預先分群切片
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

    stock_dashboard = {}

    print("⚡ 開始進行 7 大選股公式邏輯掃描...\n")

    for stock_id in unique_stock_ids:
        try:
            clean_stock_id = str(stock_id)

            if clean_stock_id not in stock_groups:
                continue

            df_k = stock_groups[clean_stock_id].copy()

            if df_k.empty or len(df_k) < 20:
                continue

            # 最新價格與量能 (全程維持「股數」計算)
            close_today = float(df_k["close"].iloc[-1])
            close_yesterday = float(df_k["close"].iloc[-2])
            close_2days_ago = float(df_k["close"].iloc[-3])

            vol_today = float(df_k["Trading_Volume"].iloc[-1])
            vol_yesterday = float(df_k["Trading_Volume"].iloc[-2])

            # 🌟 直接讀取預處理算好的標準名稱欄位（全小寫底線）
            vol_5ma = float(df_k["volume_5_ma"].iloc[-1])
            easy_today = float(df_k["easy_line"].iloc[-1])

            # 核心基本通行證
            is_above_easy_today = close_today > easy_today
            is_price_ok = close_today >= 5

            if not (is_above_easy_today and is_price_ok):
                continue

            # 判斷過往是否曾在輕鬆線之下 (洗盤軌跡)
            df_k["is_below_easy"] = df_k["close"] <= df_k["easy_line"]
            was_below_easy_1d = bool(df_k["is_below_easy"].iloc[-2])
            was_below_easy_2d = bool(df_k["is_below_easy"].iloc[-3])
            was_below_easy_3d = bool(df_k["is_below_easy"].iloc[-4])

            # 🌟 使用預處理算好的 K 與 D 判斷黃金交叉
            df_k["kd_cross"] = (df_k["K"] > df_k["D"]) & (
                df_k["K"].shift(1) <= df_k["D"].shift(1)
            )
            has_kd_cross_in_6d = df_k["kd_cross"].tail(6).any()

            # 🌟 使用預處理算好的每筆成交股數 (shares_per_trans) 判斷遞增
            s_per_t_today = float(df_k["shares_per_trans"].iloc[-1])
            s_per_t_1d = float(df_k["shares_per_trans"].iloc[-2])
            s_per_t_2d = float(df_k["shares_per_trans"].iloc[-3])
            is_avg_shares_growing = (
                s_per_t_today > s_per_t_1d > s_per_t_2d
            )

            # 籌碼面資料處理
            net_inst_buy_today = 0
            is_10d_7buy = False
            is_5d_4buy = False

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

            # 審查條件
            stock_name = stock_name_dict.get(clean_stock_id, "未知")
            stock_hit_formulas = []

            # 顯示與匯出時轉換為「張數」
            stock_info = {
                "股票代號": clean_stock_id,
                "名稱": stock_name,
                "今日收盤": round(close_today, 2),
                "今日成交量(張)": int(vol_today / 1000),
            }

            # 【公式 4：強力上】
            if (
                vol_today >= 350_000
                and (close_today / close_yesterday >= 1.065)
                and (close_yesterday / close_2days_ago <= 1.06)
            ):
                results["F4_強力上"].append(stock_info)
                stock_hit_formulas.append("F4_強力上")

            # 【公式 5：洗盤後】
            if vol_today >= 350_000 and (
                was_below_easy_1d or was_below_easy_2d or was_below_easy_3d
            ):
                results["F5_洗盤後"].append(stock_info)
                stock_hit_formulas.append("F5_洗盤後")

            # 【公式 6：出量上輕】
            mode_a = (vol_today >= vol_yesterday * 3) and (
                vol_today >= 3_000_000
            )
            mode_b = (vol_today >= vol_yesterday * 4.5) and (
                vol_today < 3_000_000
            )
            if vol_today >= 350_000 and (mode_a or mode_b):
                results["F6_出量上輕"].append(stock_info)
                stock_hit_formulas.append("F6_出量上輕")

            # 【公式 7：筆張現形】
            if vol_today >= 500_000 and is_avg_shares_growing:
                results["F7_筆張現形"].append(stock_info)
                stock_hit_formulas.append("F7_筆張現形")

            # 統計
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

    # 產出 Excel 報告
    file_name = f"錢塘潮選股報告_{tw_time.strftime('%Y%m%d_%H%M')}.xlsx"
    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
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
    archive_and_cleanup(os.path.abspath(file_name), prod_remote_path)

    line_target_df = (
        dashboard_df[dashboard_df["符合公式總數"] > 3]
        if not dashboard_df.empty
        else dashboard_df
    )
    send_qiantang_7in1_line_summary(line_target_df, tw_time)


if __name__ == "__main__":
    my_watchlist = parse_stock_ids(STOCK_INPUT)
    run_seven_combine_filter(my_watchlist)
