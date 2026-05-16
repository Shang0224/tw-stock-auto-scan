import datetime
import os
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader

# 初始化 FinMind API (免代幣每日有限額，若有 Token 可自行傳入 api_token="...")
api = DataLoader()


def calculate_kd(df, n=9, m1=3, m2=3):
    """計算技術指標 KD"""
    low_min = df["Low"].rolling(window=n).min()
    high_max = df["High"].rolling(window=n).max()
    rsv = ((df["Close"] - low_min) / (high_max - low_min)) * 100
    rsv = rsv.fillna(50)

    k = [50.0]
    for i in range(1, len(rsv)):
        k.append((1 / m1) * rsv.iloc[i] + ((m1 - 1) / m1) * k[-1])
    df["K"] = k

    d = [50.0]
    for i in range(1, len(df["K"])):
        d.append(
            (1 / m2) * float(df["K"].iloc[i])
            + ((m2 - 1) / m2) * float(d[-1])
        )
    df["D"] = d
    return df


def run_seven_combine_filter(stock_list):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    start_str = (datetime.date.today() - datetime.timedelta(days=90)).strftime(
        "%Y-%m-%d"
    )

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

    print("🚀 【錢塘潮 7 合 1 終極選股系統】全面啟動掃描...\n")

    for stock_id in stock_list:
        try:
            # ==========================================
            # 1. 技術面與基本量價資料抓取 (yfinance)
            # ==========================================
            yf_id = f"{stock_id}.TW"
            df_yf = yf.download(yf_id, start=start_str, end=today_str, progress=False)
            if df_yf.empty or len(df_yf) < 20:
                continue

            if isinstance(df_yf.columns, pd.MultiIndex):
                df_yf.columns = df_yf.columns.get_level_values(0)

            # 計算模擬輕鬆線 (10日 EMA)
            df_yf["Easy_Line"] = df_yf["Close"].ewm(span=10, adjust=False).mean()
            df_yf["Vol_5MA"] = df_yf["Volume"].rolling(window=5).mean()
            df_yf = calculate_kd(df_yf)

            # 最新三天的技術數據
            close_today = float(df_yf["Close"].iloc[-1])
            close_yesterday = float(df_yf["Close"].iloc[-2])
            close_2days_ago = float(df_yf["Close"].iloc[-3])

            vol_today_txt = float(df_yf["Volume"].iloc[-1]) / 1000  # 轉張數
            vol_yesterday_txt = float(df_yf["Volume"].iloc[-2]) / 1000
            vol_5ma_txt = float(df_yf["Vol_5MA"].iloc[-1]) / 1000

            easy_today = float(df_yf["Easy_Line"].iloc[-1])

            # 核心基本通行證
            is_above_easy_today = close_today > easy_today
            is_price_ok = close_today >= 5

            # 如果連最基本的「上輕鬆線」與「收盤>=5」都不符合，直接跳過該股，節省晶片與籌碼抓取時間
            if not (is_above_easy_today and is_price_ok):
                continue

            # 定義過往洗盤軌跡
            df_yf["Is_Below_Easy"] = df_yf["Close"] <= df_yf["Easy_Line"]
            was_below_easy_1d = bool(df_yf["Is_Below_Easy"].iloc[-2])
            was_below_easy_2d = bool(df_yf["Is_Below_Easy"].iloc[-3])
            was_below_easy_3d = bool(df_yf["Is_Below_Easy"].iloc[-4])

            # KD 黃金交叉
            df_yf["KD_Cross"] = (df_yf["K"] > df_yf["D"]) & (
                df_yf["K"].shift(1) <= df_yf["D"].shift(1)
            )
            has_kd_cross_in_6d = df_yf["KD_Cross"].tail(6).any()

            # ==========================================
            # 2. 籌碼面資料抓取 (FinMind)
            # ==========================================
            # 2a. 三大法人
            chip_df = api.taiwan_stock_institutional_investors(
                stock_id=stock_id, start_date=start_str, end_date=today_str
            )
            net_inst_buy_today = 0
            is_10d_7buy = False
            is_5d_4buy = False

            if not chip_df.empty:
                chip_df["net_buy"] = chip_df["buy"] - chip_df["sell"]
                daily_chip = (
                    chip_df.groupby("date")["net_buy"].sum().reset_index()
                )

                # 當天法人淨買超
                net_inst_buy_today = (
                    float(daily_chip["net_buy"].iloc[-1]) / 1000
                )  # 換算成張

                # 10天7買與5天4買
                is_10d_7buy = (daily_chip.tail(10)["net_buy"] > 0).sum() >= 7
                is_5d_4buy = (daily_chip.tail(5)["net_buy"] > 0).sum() >= 4

            # 2b. 每筆成交張數 (張/筆)
            daily_k_df = api.taiwan_stock_daily(
                stock_id=stock_id, start_date=start_str, end_date=today_str
            )
            is_avg_shares_growing = False
            s_per_t_today = 0

            if not daily_k_df.empty and len(daily_k_df) >= 3:
                daily_k_df["Total_Shares"] = daily_k_df["turnover_vol"] / 1000
                daily_k_df["Shares_Per_Trans"] = (
                    daily_k_df["Total_Shares"] / daily_k_df["transaction"]
                )

                s_per_t_today = float(daily_k_df["Shares_Per_Trans"].iloc[-1])
                s_per_t_1d = float(daily_k_df["Shares_Per_Trans"].iloc[-2])
                s_per_t_2d = float(daily_k_df["Shares_Per_Trans"].iloc[-3])

                is_avg_shares_growing = (
                    s_per_t_today > s_per_t_1d > s_per_t_2d
                )

            # ==========================================
            # 3. 執行 7 大公式邏輯審查
            # ==========================================
            stock_hit_formulas = []
            stock_info = {
                "股票代號": stock_id,
                "今日收盤": round(close_today, 2),
                "今日成交量(張)": int(vol_today_txt),
            }

            # 【公式 1：主力大買】 上輕鬆 且 主外大買(法人單日買超>1000張) 且 量>=350
            if vol_today_txt >= 350 and net_inst_buy_today >= 1000:
                results["F1_主力大買"].append(stock_info)
                stock_hit_formulas.append("F1_主力大買")

            # 【公式 2：一朵花】 上輕鬆 且 (10天7買 或 量暴發2倍) 貼心門檻量>=350
            if vol_today_txt >= 350 and (
                is_10d_7buy or (vol_today_txt >= vol_5ma_txt * 2)
            ):
                results["F2_一朵花"].append(stock_info)
                stock_hit_formulas.append("F2_一朵花")

            # 【公式 3：主外上輕】 上輕鬆 且 (5天4買 或 6內黃金) 且 量>=350
            if vol_today_txt >= 350 and (is_5d_4buy or has_kd_cross_in_6d):
                results["F3_主外上輕"].append(stock_info)
                stock_hit_formulas.append("F3_主外上輕")

            # 【公式 4：強力上】 上輕鬆 且 今日漲幅>=6.5% 且 昨日漲幅<=6% 且 量>=350
            if (
                vol_today_txt >= 350
                and (close_today / close_yesterday >= 1.065)
                and (close_yesterday / close_2days_ago <= 1.06)
            ):
                results["F4_強力上"].append(stock_info)
                stock_hit_formulas.append("F4_強力上")

            # 【公式 5：洗盤後】 上輕鬆 且 (1天前下輕鬆 或 2天前下輕鬆 或 3天前下輕鬆) 且 量>=350
            if vol_today_txt >= 350 and (
                was_below_easy_1d or was_below_easy_2d or was_below_easy_3d
            ):
                results["F5_洗盤後"].append(stock_info)
                stock_hit_formulas.append("F5_洗盤後")

            # 【公式 6：出量上輕】 上輕鬆 且 ((量>=昨量*3 且 量>=3000) 或 (量>=昨量*4.5 且 量<3000)) 且 量>=350
            mode_a = (vol_today_txt >= vol_yesterday_txt * 3) and (
                vol_today_txt >= 3000
            )
            mode_b = (vol_today_txt >= vol_yesterday_txt * 4.5) and (
                vol_today_txt < 3000
            )
            if vol_today_txt >= 350 and (mode_a or mode_b):
                results["F6_出量上輕"].append(stock_info)
                stock_hit_formulas.append("F6_出量上輕")

            # 【公式 7：筆張現形】 上輕鬆 且 張/筆 連續遞增 且 量>=500
            if vol_today_txt >= 500 and is_avg_shares_growing:
                results["F7_筆張現形"].append(stock_info)
                stock_hit_formulas.append("F7_筆張現形")

            # 彙整至總儀表板
            if stock_hit_formulas:
                stock_dashboard[stock_id] = {
                    "股票代號": stock_id,
                    "今日收盤": round(close_today, 2),
                    "今日成交量(張)": int(vol_today_txt),
                    "符合公式總數": len(stock_hit_formulas),
                    "符合公式明細": "、".join(stock_hit_formulas),
                }
                print(
                    f"🎯 股票 {stock_id} 觸發訊號！符合：{', '.join(stock_hit_formulas)}"
                )

        except Exception as e:
            print(f"❌ 處理股票 {stock_id} 時發生異常: {e}")

    # ==========================================
    # 4. 產生多頁籤 Excel 選股報告
    # ==========================================
    file_name = f"錢塘潮選股報告_{today_str}.xlsx"
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
                    "今日收盤",
                    "今日成交量(張)",
                    "符合公式總數",
                    "符合公式明細",
                ]
            )
        dashboard_df.to_excel(writer, sheet_name="🎯 綜合強勢股儀表板", index=False)

        # 後續頁籤：個別公式清單
        for formula_name, data_list in results.items():
            sheet_df = pd.DataFrame(data_list)
            if sheet_df.empty:
                sheet_df = pd.DataFrame(columns=["股票代號", "今日收盤", "今日成交量(張)"])
            sheet_df.to_excel(writer, sheet_name=formula_name, index=False)

    print(f"\n🎉 掃描完成！終極報告已成功匯出至：【{os.path.abspath(file_name)}】")


if __name__ == "__main__":
    # 您可以自由替換或擴充這個台股代號清單（例如填入您觀察的所有個股）
    my_watchlist = [
        "2330",
        "2317",
        "3227",
        "3260",
        "2454",
        "2382",
        "2603",
        "2303",
        "2881",
        "2308",
    ]
    run_seven_combine_filter(my_watchlist)
