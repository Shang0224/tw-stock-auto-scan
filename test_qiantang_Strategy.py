#test_qiantang_Strategy.py
"""
錢塘潮選股系統 - 多方選股策略指定天期區間歷史掃描 (含未來前瞻與極值績效追蹤 + 大盤趨勢濾網)
說明：
1. 結合 FinMind 台股官方交易日曆，非開盤日直接跳過不計算。
2. 整合大盤 (TAIEX) EMA60 (季線) 趨勢防線，當大盤修正或處於空頭 (Close <= EMA60) 時，啟動避險機制暫停當日選股。
3. 自動計算觸發後 T+3/T+5/T+10/T+20 報酬率與未來 1 年內最高/最低極值報酬，支援 Excel 與 CSV 輸出。
"""

import os
from datetime import datetime, timedelta, timezone
import pandas as pd

# 1. 匯入核心執行引擎與預處理
from strategy.engine import scan_single_stock, preprocess_all_technical_indicators
from strategy.config import BUY_PARAM_PROFILES
#from monitor.engine import preprocess_all_technical_indicators

# 2. 匯入 7 大多方選股策略與優化策略
from strategy.qiantang_strategies import (
    st_qiantang_f1_spt_growth,      # 筆張現形
    st_qiantang_f2_volume_breakout, # 出量上輕
    st_qiantang_f3_after_shakeout,  # 洗盤後
    st_qiantang_f3_after_shakeout_20261001,
    st_qiantang_f3_after_shakeout_20261001_1,
    st_qiantang_f3_after_shakeout_20261001_1_1,
    st_qiantang_f3_after_shakeout20261001_1_2,
    st_qiantang_f3_after_shakeout_20261001_1_3,   
    st_qiantang_f3_after_shakeout_20261001_1_3_1,
    st_qiantang_f3_after_shakeout_20261001_1_3_2,
    st_qiantang_f3_after_shakeout_20261017_1,

    st_qiantang_f4_strong_rise,     # 強力上
    st_qiantang_f5_major_buy_easy,  # 主外上輕
    st_qiantang_f6_flower,          # 一朵花
    st_qiantang_f7_super_stock,     # 飆股
)

# 3. 匯入資料抓取與工具庫 (含大盤 EMA 快查工具)
from utils import (
    archive_and_cleanup,
    fm_get_complete_stock_data,
    get_stock_name_dict,
    parse_monitor_stocks,
    #parse_stock_ids,
    get_fm_trading_days,
    calculate_forward_horizon_returns,  # 前瞻固定天數報酬
    calculate_one_year_extremes,        # 一年內最高與最低極值報酬
    load_stocks_from_csv,
    fetch_market_ema_dict,               # 🌟 大盤數據與 EMA 秒查字典工具
    generate_qiantang_wave_charts,
    #parse_stock_dict,
    parse_and_validate_stocks,
)

# =====================================================================
# 🎛 多方策略測試控制面板 (指定天期區間)
# =====================================================================
# 💡 目前僅單獨測試：st_qiantang_f3_after_shakeout_20261001_1
TEST_QIANTANG_STRATEGY = [
    # st_qiantang_f1_spt_growth,      # F1: 筆張現形
    # st_qiantang_f2_volume_breakout, # F2: 出量上輕
    #st_qiantang_f3_after_shakeout,  # F3: 洗盤後    
    st_qiantang_f3_after_shakeout_20261017_1
    #st_qiantang_f3_after_shakeout_20261001_1_3_2, # F3: 洗盤後優化版 (唯一開啟)

    #st_qiantang_f3_after_shakeout_20261001_1,
    #st_qiantang_f3_after_shakeout_20261001_1_1,
    #st_qiantang_f3_after_shakeout20261001_1_2,
    #st_qiantang_f3_after_shakeout_20261001_1_3,   
    #st_qiantang_f3_after_shakeout_20261001_1_3_1,
   
    # st_qiantang_f4_strong_rise,     # F4: 強力上
    # st_qiantang_f5_major_buy_easy,  # F5: 主外上輕
    # st_qiantang_f6_flower,          # F6: 一朵花
    # st_qiantang_f7_super_stock,     # F7: 飆股

]

CHOSEN_SOURCE = "fm"
TEST_START_DATE = "2025-01-01"  # 測試起始日期 (YYYY-MM-DD)
TEST_END_DATE = "2025-09-30"    # 測試結束日期 (YYYY-MM-DD)
DAYS_BEFORE = 365               # 歷史技術指標計算緩衝天數

# 🌟 大盤趨勢濾網控制開關
USE_MARKET_FILTER = False        # 是否啟用大盤趨勢濾網 (True: 啟用防守 / False: 關閉防守)
MARKET_FILTER_KEY = "EMA60"     # 大盤門檻指標 (預設季線 EMA60)

# 🌟 檔案輸出控制開關
EXPORT_EXCEL = False            # 是否輸出與上傳 Excel 報告
EXPORT_CSV = True               # 是否輸出與上傳綜合儀表板 CSV 檔

# 模式 A：CSV 檔案載入模式
STOCK_MODE = "csv"

STOCK_INPUT = "data/TestData/qiantang_mid100_test.csv"
#STOCK_INPUT = "data/TestData/qiantang_mid100_hot.csv"
#STOCK_INPUT = "data/TestData/qiantang_ICDesign_hot.csv,data/TestData/qiantang_mid100_hot.csv,data/TestData/qiantang_tw50_hot.csv"

#STOCK_MODE = 'noncsv' 
"""
STOCK_INPUT = {
    "3661": {"yf_suffix": "TW", "name": "世芯-KY", "category": "ICDesign", "market": "上市", "note": "ASIC晶片設計服務與矽智財"},
    "3035": {"yf_suffix": "TW", "name": "智原", "category": "ICDesign", "market": "上市", "note": "ASIC晶片設計服務與矽智財"},
    "3529": {"yf_suffix": "TWO", "name": "力旺", "category": "ICDesign", "market": "上櫃", "note": "ASIC晶片設計服務與矽智財"},
    "6643": {"yf_suffix": "TWO", "name": "M31", "category": "ICDesign", "market": "上櫃", "note": "ASIC晶片設計服務與矽智財"},
}
"""



# ==============================================================================
# 🎛 走勢圖繪製控制開關
# ==============================================================================
GENERATE_WAVE_CHARTS = True  # 選股完成後是否自動繪製波段 K 線走勢圖

def scan_qiantang_strategy_day(
    day_str: str,
    all_df_slice: pd.DataFrame,
    global_df: pd.DataFrame,
    stocks_dict: dict[str, dict],
    strategies: list,
    profiles_map: dict = BUY_PARAM_PROFILES,
    market_dict: dict = None,  # 🌟 新增：傳入大盤資料秒查字典
) -> list:
  """單日個股選股掃描核心，並於觸發時附加全方位技術面、大盤環境、前瞻與極值績效"""
  day_hits = []

  # 1. 直接對全市場 K 線依 stock_id 分組
  grouped = all_df_slice.groupby("stock_id")

  for stock_id, group_df in grouped:
    sid = str(stock_id)

    # 2. 快速過濾與查詢監控股票資訊
    if sid not in stocks_dict:
      continue

    stock_info = stocks_dict[sid]
    stock_name = stock_info.get("name", "未知股票")
    stock_cat = stock_info.get("category", "MID100")

    df_single = group_df.sort_values("date").copy()
    if df_single.empty or len(df_single) < 5:
      continue

    # 3. 呼叫引擎執行策略檢測
    hits = scan_single_stock(
        df_single=df_single,
        category=stock_cat,
        func_list=strategies,
        param_profiles=profiles_map,
    )

    if hits:
      # 取得觸發當日 (Day T) 的預處理資料列
      latest_row = df_single.iloc[-1]
      close_price = round(float(latest_row["close"]), 2)
      vol_today = float(latest_row.get("Trading_Volume", 0))
      vol_lots = int(vol_today / 1000)

      # 4. 查閱當日大盤環境數據
      m_info = market_dict.get(day_str, {}) if market_dict else {}
      m_close = float(m_info.get("close", 0))
      m_ma60 = float(m_info.get("MA60", 0))

      # 5. 計算第二類：前瞻天數報酬 (T+3, T+5, T+10, T+20, T+60, T+120, T+240)
      fwd_perf = calculate_forward_horizon_returns(
          stock_id=sid, trigger_date_str=day_str, global_df=global_df
      )

      # 6. 計算第二類：未來 1 年內最高/最低極值與軌跡風險 (MAE/MFE/登頂天數/Cat標籤)
      extreme_perf = calculate_one_year_extremes(
          stock_id=sid, trigger_date_str=day_str, global_df=global_df
      )

      for hit in hits:
        strat_func_name = hit.get("strategy_name", "")
        formula_label = hit.get("選股公式", strat_func_name)

        hit_record = {
            # -----------------------------------------------------------------
            # 📌 基礎標示欄位
            # -----------------------------------------------------------------
            "日期": day_str,
            "股票代號": sid,
            "名稱": stock_name,
            "選股池分類": stock_cat,
            "今日收盤": close_price,
            "今日成交量(張)": vol_lots,
            "選股公式": formula_label,
            "strategy_name": strat_func_name,
            "操作建議": hit.get("操作建議", hit.get("detail", "")),
            # -----------------------------------------------------------------
            # 🎯 第一類：觸發當下 (Day T) 技術與籌碼特徵 (因)
            # -----------------------------------------------------------------
            # 1. 輕鬆線動能
            "輕鬆線價格": round(float(latest_row.get("easy_line", 0)), 2),
            "輕鬆線乖離率(%)": round(
                float(latest_row.get("easy_line_bias", 0)), 2
            ),
            "輕鬆線OLS斜率": round(
                float(latest_row.get("easy_line_slope", 0)), 4
            ),
            # 2. 均線位階與扣抵
            "MA60季線": round(float(latest_row.get("MA60", 0)), 2),
            "季線乖離率(%)": round(float(latest_row.get("ma60_bias", 0)), 2),
            "季線扣抵位置(%)": round(
                float(latest_row.get("ma60_deduct_bias", 0)), 2
            ),
            "MA240年線": (
                round(float(latest_row["MA240"]), 2)
                if ("MA240" in latest_row and pd.notnull(latest_row["MA240"]))
                else "N/A"
            ),
            "年線乖離率(%)": (
                round(float(latest_row["ma240_bias"]), 2)
                if (
                    "ma240_bias" in latest_row
                    and pd.notnull(latest_row["ma240_bias"])
                )
                else "N/A"
            ),
            "年線扣抵位置(%)": (
                round(float(latest_row["ma240_deduct_bias"]), 2)
                if (
                    "ma240_deduct_bias" in latest_row
                    and pd.notnull(latest_row["ma240_deduct_bias"])
                )
                else "N/A"
            ),
            "MA60斜率": round(float(latest_row.get("ma60_slope", 0)), 4),
            "MA240斜率": round(float(latest_row.get("ma240_slope", 0)), 4),
            "均線多頭排列": bool(latest_row.get("is_bull_alignment", False)),
            "均線糾結度(%)": (
                round(float(latest_row["ma_tangle_ratio"]), 2)
                if (
                    "ma_tangle_ratio" in latest_row
                    and pd.notnull(latest_row["ma_tangle_ratio"])
                )
                else "N/A"
            ),
            # 3. K線型態與特徵
            "實體K棒比例(%)": round(
                float(latest_row.get("body_ratio", 0)), 2
            ),
            "上影線比例(%)": round(
                float(latest_row.get("upper_shadow_ratio", 0)), 2
            ),
            "是否紅K": bool(latest_row.get("is_red_k", True)),
            # 4. 成交金額與型態沉澱
            "成交金額(億元)": round(float(latest_row.get("amount_100m", 0)), 2),
            "單筆均張(SPT)": round(
                float(latest_row.get("shares_per_trans", 0)), 2
            ),
            "距52週高點(%)": (
                round(float(latest_row["dist_to_52w_high_pct"]), 2)
                if (
                    "dist_to_52w_high_pct" in latest_row
                    and pd.notnull(latest_row["dist_to_52w_high_pct"])
                )
                else "N/A"
            ),
            "打底沉澱天數": int(latest_row.get("base_consolidation_days", 0)),
            # -----------------------------------------------------------------
            # 🌐 外部大盤環境特徵 (Context)
            # -----------------------------------------------------------------
            "大盤位階": (
                "大盤>MA60" if m_close > m_ma60 else "大盤<=MA60"
            ),
            "大盤當日漲跌幅(%)": round(
                float(m_info.get("taiex_change_pct", 0)), 2
            ),
            "大盤季線乖離率(%)": round(
                float(m_info.get("taiex_ma60_bias_pct", 0)), 2
            ),
        }

        # -----------------------------------------------------------------
        # ⏱️ 第二類：進場後績效與軌跡細節 (果)
        # -----------------------------------------------------------------
        hit_record.update(fwd_perf)
        hit_record.update(extreme_perf)

        day_hits.append(hit_record)

  return day_hits


"""
def scan_qiantang_strategy_day(
    day_str: str,
    all_df_slice: pd.DataFrame,
    global_df: pd.DataFrame,
    stocks_dict: dict[str, dict],
    strategies: list,
    profiles_map: dict = BUY_PARAM_PROFILES,
) -> list:
    #單日個股選股掃描核心，並於觸發時附加前瞻與極值績效
    day_hits = []
    
    # 🌟 1. 直接對全市場 K 線依 stock_id 分組 (不用再轉置 stock_meta_map)
    grouped = all_df_slice.groupby("stock_id")

    for stock_id, group_df in grouped:
        sid = str(stock_id)
        
        # 🌟 2. 直接使用傳入的 stocks_dict 快速過濾與查詢
        if sid not in stocks_dict:
            continue
            
        stock_info = stocks_dict[sid]
        stock_name = stock_info.get("name", "未知股票")

        stock_cat = stock_info.get("category", "MID100")

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

            # 🌟 1. 計算 T+3, T+5, T+10, T+20 前瞻區間報酬
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
                #print(f"hit_record : {hit_record}")

    return day_hits
"""

def run_qiantang_strategy_range_scan(
    source=CHOSEN_SOURCE,
    stock_source=STOCK_MODE,
    stock_data=STOCK_INPUT,
    strategies=TEST_QIANTANG_STRATEGY,
    start_date_str=TEST_START_DATE,
    end_date_str=TEST_END_DATE,
):
  """執行錢塘潮多方選股指定天期歷史掃描並產出報表 (含全方位買進特徵與後續軌跡分析)"""
  tz_tw = timezone(timedelta(hours=8))
  start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(
      tzinfo=tz_tw
  )
  end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
      tzinfo=tz_tw
  )

  if end_date < start_date:
    raise ValueError("❌ 結束日期不能小於開始日期！")

  if not strategies:
    raise ValueError("❌ [錯誤] 未指定 TEST_QIANTANG_STRATEGY 策略清單！")

  # 1. 解析與驗證監控股票清單
  stock_records = parse_and_validate_stocks(
      stock_source=stock_source, stock_data=stock_data
  )

  if not stock_records:
    print(f"❌ [錯誤] 無法解析股票清單 ({stock_data})。")
    return

  stock_ids = list(stock_records.keys())

  print(
      f"🧪 [測試啟動] 錢塘潮多方策略歷史掃描 ({start_date_str} ~"
      f" {end_date_str})"
  )
  print(f"📡 監控數量：{len(stock_ids)} 檔個股 ({stock_ids})\n")

  # 2. 準備歷史數據抓取區間 (含前推緩衝天數與未來 1 年極值區間)
  fetch_start_str = (start_date - timedelta(days=DAYS_BEFORE)).strftime(
      "%Y-%m-%d"
  )
  fetch_end_str = (end_date + timedelta(days=365)).strftime("%Y-%m-%d")

  print(
      "📡 正在向 FinMind/yfinance 批量抓取歷史與未來 K 線資料"
      f" ({fetch_start_str} ~ {fetch_end_str})..."
  )
  stock_name_dict, dl = get_stock_name_dict()

  global_df = fm_get_complete_stock_data(
      dl, stock_records, fetch_start_str, fetch_end_str
  )
  if global_df.empty:
    print("❌ [錯誤] 數據抓取為空，結束執行。")
    return

  # 3. 全域個股指標預處理 (計算輕鬆線動能、SMA/EMA、扣抵位置、K線型態、打底天數等)
  print("⚡ 正在執行全域技術面與籌碼替代指標預處理...")
  global_df = preprocess_all_technical_indicators(global_df)
  print("✅ 全域指標預處理完成！\n")

  # 4. 取得大盤 (TAIEX) 均線/漲跌幅秒查字典與台股官方交易日曆
  print("📡 正在擷取大盤 (TAIEX) 均線數據與官方交易日曆...")
  market_dict = fetch_market_ema_dict(dl, fetch_start_str, fetch_end_str)
  trading_days_set = get_fm_trading_days(fetch_start_str, fetch_end_str)

  if trading_days_set:
    print(
        f"✅ 成功載入 FinMind 交易日清單，共 {len(trading_days_set)} 個交易日。"
    )
  else:
    print("⚠ 無法取得 FinMind 交易日，將自動退回僅過濾週末機制。")

  print("✅ 大盤均線字典與交易日曆準備完畢！\n")

  # 5. 逐日推進監控掃描迴圈
  results_by_formula = {strat.__name__: [] for strat in strategies}
  all_hits_list = []
  current_day = start_date

  while current_day <= end_date:
    day_str = current_day.strftime("%Y-%m-%d")

    # =================================================================
    # 🛑 關卡 1：台股交易日過濾 (非開盤日直接秒過)
    # =================================================================
    if trading_days_set:
      if day_str not in trading_days_set:
        current_day += timedelta(days=1)
        continue
    else:
      if current_day.weekday() >= 5:
        current_day += timedelta(days=1)
        continue

    # =================================================================
    # 🛡 關卡 2：大盤趨勢第一道防線 (當日大盤未站上趨勢防線則暫停選股)
    # =================================================================
    if USE_MARKET_FILTER:
      market_info = market_dict.get(day_str)
      if market_info:
        m_close = market_info.get("close", 0)
        m_ema = market_info.get(MARKET_FILTER_KEY, 0)

        # 當大盤收盤價 <= 防守線時，當天直接跳過不選股
        if m_close <= m_ema:
          current_day += timedelta(days=1)
          continue

    # =================================================================
    # 🎯 階段 3：切割截至當日為止的歷史數據並執行選股
    # =================================================================
    day_data_cutoff = current_day.replace(hour=23, minute=59, second=59)
    all_df_slice = global_df[
        global_df["date"] <= day_data_cutoff.strftime("%Y-%m-%d")
    ].copy()

    if all_df_slice.empty:
      current_day += timedelta(days=1)
      continue

    # 執行當日選股掃描 (🌟 補傳入 market_dict 供大盤特徵寫入)
    day_hits = scan_qiantang_strategy_day(
        day_str=day_str,
        all_df_slice=all_df_slice,
        global_df=global_df,
        stocks_dict=stock_records,
        strategies=strategies,
        profiles_map=BUY_PARAM_PROFILES,
        market_dict=market_dict,
    )

    if day_hits:
      print(
          f"⚡ [{day_str}] 選股掃描完成，共觸發 {len(day_hits)} 筆訊號。"
      )
      for record in day_hits:
        all_hits_list.append(record)
        s_name = record["strategy_name"]
        if s_name in results_by_formula:
          results_by_formula[s_name].append(record)

    current_day += timedelta(days=1)

  # =====================================================================
  # 6. 彙整數據與產出報表 (全動態繼承所有分析欄位)
  # =====================================================================
  tw_time = datetime.now(tz_tw)
  current_time_str = tw_time.strftime("%Y%m%d_%H%M")

  file_name = (
      f"錢塘潮選股歷史報告_含績效分析_{start_date_str}_to_{end_date_str}_{current_time_str}.xlsx"
  )
  file_path = os.path.abspath(file_name)

  # 🌟 全動態多策略去重與合併：完整保留 hit_record 裡所有的 30+ 個特徵欄位
  dashboard_dict = {}
  for hit in all_hits_list:
    key = (hit["日期"], hit["股票代號"])
    if key not in dashboard_dict:
      item = hit.copy()
      item["符合公式清單"] = [hit["選股公式"]]
      dashboard_dict[key] = item
    else:
      dashboard_dict[key]["符合公式清單"].append(hit["選股公式"])

  dashboard_rows = []
  for item in dashboard_dict.values():
    formulas = list(set(item["符合公式清單"]))
    row_data = item.copy()
    row_data["符合公式總數"] = len(formulas)
    row_data["符合公式明細"] = "、".join(formulas)
    row_data.pop("選股公式", None)  # 移除單一公式欄位，改用明細欄位代替
    dashboard_rows.append(row_data)

  dashboard_df = (
      pd.DataFrame(dashboard_rows).sort_values(
          by=["日期", "符合公式總數"], ascending=[False, False]
      )
      if dashboard_rows
      else pd.DataFrame()
  )

  # 條件式輸出 Excel 報表
  if EXPORT_EXCEL:
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
      dashboard_df.to_excel(
          writer, sheet_name="🎯 區間綜合強勢股儀表板", index=False
      )

      for strat in strategies:
        func_name = strat.__name__
        data_list = results_by_formula.get(func_name, [])
        sheet_df = pd.DataFrame(data_list)
        if sheet_df.empty:
          sheet_df = pd.DataFrame()
        else:
          sheet_df = sheet_df.drop(
              columns=["strategy_name"], errors="ignore"
          )

        sheet_label = (
            data_list[0].get("選股公式", func_name) if data_list else func_name
        )
        sheet_df.to_excel(writer, sheet_name=sheet_label, index=False)

    print(
        "\n🎉 區間掃描完成！包含績效分析之終極選股 Excel 報告已成功匯出至：【"
        f"{file_path}】"
    )
  else:
    print("\nℹ [提示] EXPORT_EXCEL 為 False，已略過 Excel 報表的本地產出。")

  # =====================================================================
  # 🌟 檔案輸出控制與資料夾建立 (CSV 儀表板與單策略檔匯出)
  # =====================================================================
  csv_file_path = None
  strat_tag = (
      "_".join([s.__name__ for s in strategies]) if strategies else "qiantang"
  )

  if EXPORT_CSV:
    # 1. 建立輸出資料夾
    sub_folder_name = (
        f"qiantang_test_report/{start_date_str}_to_{end_date_str}_{current_time_str}"
    )
    output_dir = os.path.abspath(os.path.join("data", sub_folder_name))
    os.makedirs(output_dir, exist_ok=True)

    # 2. 輸出綜合儀表板 CSV 檔
    csv_file_name = (
        f"dashboard_summary_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
    )
    csv_file_path = os.path.join(output_dir, csv_file_name)
    dashboard_df.to_csv(csv_file_path, index=False, encoding="utf-8-sig")

    # 寫入頂部 Meta 標頭資訊
    with open(csv_file_path, "r", encoding="utf-8-sig") as f:
      original_content = f.read()

    with open(csv_file_path, "w", encoding="utf-8-sig") as f:
      f.write(f"策略程式: ,{strat_tag}, Stock Data:,{stock_data}\n")
      f.write(original_content)

    print(f"📊 綜合儀表板 CSV 檔已成功匯出至：【{csv_file_path}】")

    # 3. 將各策略獨立輸出為專屬 CSV 檔
    for strat in strategies:
      func_name = strat.__name__
      data_list = results_by_formula.get(func_name, [])
      sheet_df = pd.DataFrame(data_list)

      if sheet_df.empty:
        sheet_df = pd.DataFrame()
      else:
        sheet_df = sheet_df.drop(
            columns=["strategy_name"], errors="ignore"
          )

      strat_csv_name = (
          f"{func_name}_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
      )
      strat_csv_path = os.path.join(output_dir, strat_csv_name)
      sheet_df.to_csv(strat_csv_path, index=False, encoding="utf-8-sig")

      with open(strat_csv_path, "r", encoding="utf-8-sig") as f:
        strat_orig_content = f.read()

      with open(strat_csv_path, "w", encoding="utf-8-sig") as f:
        f.write(f"策略公式: ,{func_name}, Stock Data:,{stock_data}\n")
        f.write(strat_orig_content)

      print(
          f"📁 單獨策略 CSV 檔 [{func_name}]"
          f" 已成功匯出至：【{strat_csv_path}】"
      )

  else:
    print("ℹ [提示] EXPORT_CSV 為 False，已略過 CSV 檔的本地產出。")

  # ==============================================================================
  # SECTION 7. 自動繪製股票波段 K 線走勢圖 (Wave Charts Generation)
  # ==============================================================================
  if GENERATE_WAVE_CHARTS and not dashboard_df.empty:
    wave_output_dir = os.path.join(output_dir, "dashboard_wave_plots")
    print("\n📈 正在根據波段規則繪製股票 K 線走勢圖...")

    nas_path = (
        f"{os.getenv('NAS_SFTP_PATH').rstrip('/')}/{sub_folder_name}"
        if os.getenv("NAS_SFTP_PATH")
        else None
    )

    plot_files = generate_qiantang_wave_charts(
        dashboard_df=dashboard_df,
        global_df=global_df,
        output_dir=wave_output_dir,
        nas_sftp_path=nas_path,
    )

    print(
        f"✅ 成功產出 {len(plot_files)} 張波段走勢圖，儲存於:"
        f" {wave_output_dir}"
    )

  # =====================================================================
  # 8. 自動備份至 NAS 伺服器
  # =====================================================================
  if os.getenv("NAS_SFTP_PATH"):
    if EXPORT_EXCEL and os.path.exists(file_path):
      remote_excel_path = (
          f"{os.getenv('NAS_SFTP_PATH')}/{sub_folder_name}/{file_name}"
      )
      try:
        archive_and_cleanup(file_path, remote_excel_path)
        print(f"📦 Excel 報告已備份至 NAS：{remote_excel_path}")
      except Exception as e:
        print(f"⚠ Excel NAS 備份失敗: {e}")

    if EXPORT_CSV:
      if csv_file_path and os.path.exists(csv_file_path):
        remote_csv_path = (
            f"{os.getenv('NAS_SFTP_PATH')}/{sub_folder_name}/{csv_file_name}"
        )
        try:
          archive_and_cleanup(csv_file_path, remote_csv_path)
          print(
              "📦 綜合儀表板 CSV 已成功備份至 NAS"
              f" 並清理本地：{remote_csv_path}"
          )
        except Exception as e:
          print(f"⚠ 綜合儀表板 CSV NAS 備份失敗: {e}")

      for strat in strategies:
        func_name = strat.__name__
        strat_csv_name = (
            f"{func_name}_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
        )
        strat_csv_path = os.path.join(output_dir, strat_csv_name)

        if os.path.exists(strat_csv_path):
          remote_strat_csv_path = (
              f"{os.getenv('NAS_SFTP_PATH')}/{sub_folder_name}/{strat_csv_name}"
          )
          try:
            archive_and_cleanup(strat_csv_path, remote_strat_csv_path)
            print(
                f"📦 單獨策略 CSV [{func_name}]"
                f" 已成功備份至 NAS：{remote_strat_csv_path}"
            )
          except Exception as e:
            print(f"⚠ 單獨策略 CSV [{func_name}] NAS 備份失敗: {e}")


def run_qiantang_strategy_range_scan_old(
    source=CHOSEN_SOURCE,
    stock_source=STOCK_MODE,
    stock_data=STOCK_INPUT,
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
    #monitor_stocks = load_stocks_from_csv(stock_input)

    # 1. 呼叫函數，傳入模式與數據
    stock_records = parse_and_validate_stocks(
        stock_source=stock_source, 
        stock_data=stock_data
    )
   
    if not stock_records:
        print(f"❌ [錯誤] 無照解析股票清單 ({stock_input})。")
        return

    # 2. 提煉純數字代號串列與 Log 標籤
    stock_ids = list(stock_records.keys())
    
    # 清理股票代號清單
    #unique_stock_ids = list(
    #    set(
    #        [
    #            str(s["stock_id"] if isinstance(s, dict) else s)
    #            .replace(".TWO", "")
    #            .replace(".TW", "")
    #            .replace("^", "")
    #            for s in monitor_stocks
    #        ]
    #    )
    #)

    print(f"🧪 [測試啟動] 錢塘潮多方策略歷史掃描 ({start_date_str} ~ {end_date_str})")
    print(f"📡 監控數量：{len(stock_ids)} 檔個股 ({stock_ids})\n")

    # 2. 準備歷史資料抓取區間
    fetch_start_str = (start_date - timedelta(days=DAYS_BEFORE)).strftime("%Y-%m-%d")
    fetch_end_str = (end_date + timedelta(days=365)).strftime("%Y-%m-%d")

    print(f"📡 正在向 FinMind 批量抓取歷史與未來 K 線資料 ({fetch_start_str} ~ {fetch_end_str})...")
    stock_name_dict, dl = get_stock_name_dict()

    global_df = fm_get_complete_stock_data(dl, stock_records, fetch_start_str, fetch_end_str)
    if global_df.empty:
        print("❌ [錯誤] FinMind 數據抓取為空，結束執行。")
        return

    # 3. 全域個股指標預處理
    print("⚡ 正在執行全域技術面與籌碼替代指標預處理...")
    global_df = preprocess_all_technical_indicators(global_df)
    print("✅ 全域指標預處理完成！\n")

    # 4. 取得大盤 (TAIEX) EMA 秒查字典與台股官方交易日曆
    print("📡 正在向 FinMind 擷取大盤 (TAIEX) 均線數據與官方交易日曆...")
    market_dict = fetch_market_ema_dict(dl, fetch_start_str, fetch_end_str)
    trading_days_set = get_fm_trading_days(fetch_start_str, fetch_end_str)

    if trading_days_set:
        print(f"✅ 成功載入 FinMind 交易日清單，共 {len(trading_days_set)} 個交易日。")
    else:
        print("⚠ 無法取得 FinMind 交易日，將自動退回僅過濾週末機制。")

    print("✅ 大盤 EMA 均線與交易日曆準備完畢！\n")

    # 5. 逐日推進監控掃描迴圈
    results_by_formula = {strat.__name__: [] for strat in strategies}
    all_hits_list = []
    current_day = start_date

    while current_day <= end_date:
        day_str = current_day.strftime("%Y-%m-%d")

        # =================================================================
        # 🛑 關卡 1：台股交易日過濾 (非開盤日直接秒過)
        # =================================================================
        if trading_days_set:
            if day_str not in trading_days_set:
                current_day += timedelta(days=1)
                print(f"{day_str} 本日無交易****************************************************\n")
                continue
        else:
            if current_day.weekday() >= 5:
                current_day += timedelta(days=1)
                continue

        # =================================================================
        # 🛡 關卡 2：大盤趨勢第一道防線 (當日大盤未站上 EMA60 季線則暫停選股)
        # =================================================================
        if USE_MARKET_FILTER:
            market_info = market_dict.get(day_str)
            if market_info:
                m_close = market_info.get("close", 0)
                m_ema = market_info.get(MARKET_FILTER_KEY, 0)
                
                # 當大盤收盤價 <= EMA60 季線時，當天直接跳過不選股
                if m_close <= m_ema:
                    current_day += timedelta(days=1)
                    continue

        # =================================================================
        # 🎯 階段 3：通過雙重過濾，切割截至當日為止的歷史數據並執行選股
        # =================================================================
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
            stocks_dict=stock_records,
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

    # 條件式輸出 Excel 報表
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

                sheet_label = data_list.get("選股公式", func_name) if data_list else func_name
                sheet_df.to_excel(writer, sheet_name=sheet_label, index=False)

        print(f"\n🎉 區間掃描完成！包含績效分析之終極選股 Excel 報告已成功匯出至：【{file_path}】")
    else:
        print("\nℹ [提示] EXPORT_EXCEL 為 False，已略過 Excel 報表的本地產出。")

    # =====================================================================
    # 🌟 檔案輸出控制與資料夾建立
    # =====================================================================
    csv_file_path = None
    strat_tag = "_".join([s.__name__ for s in strategies]) if strategies else "qiantang"

    if EXPORT_CSV:
        # 1. 在 qiantang_test_report 下方建立以執行時間命名的資料夾
        sub_folder_name = f"qiantang_test_report/{start_date_str}_to_{end_date_str}_{current_time_str}"
        output_dir = os.path.abspath(os.path.join("data", sub_folder_name))
        os.makedirs(output_dir, exist_ok=True)

        # 2. 輸出綜合儀表板 CSV 檔（Dashboard 的 Meta 放入全部策略的 strat_tag）
        csv_file_name = f"dashboard_summary_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
        csv_file_path = os.path.join(output_dir, csv_file_name)
        dashboard_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')

        with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
            original_content = f.read()
            
        with open(csv_file_path, 'w', encoding='utf-8-sig') as f:
            f.write(f"策略程式: ,{strat_tag}, Stock Data:,{stock_data}\n") 
            f.write(original_content)
        
        print(f"📊 綜合儀表板 CSV 檔已成功匯出至：【{csv_file_path}】")

        # 3. 將各策略獨立輸出為 CSV 檔（檔名與 Meta 均對應該「單獨策略名稱」 func_name）
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

            # 檔名加入該單獨策略名稱 func_name
            strat_csv_name = f"{func_name}_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
            strat_csv_path = os.path.join(output_dir, strat_csv_name)
            sheet_df.to_csv(strat_csv_path, index=False, encoding='utf-8-sig')

            # 該單獨策略 CSV 的 Meta 寫入單獨的 func_name
            with open(strat_csv_path, 'r', encoding='utf-8-sig') as f:
                strat_orig_content = f.read()
                
            with open(strat_csv_path, 'w', encoding='utf-8-sig') as f:
                f.write(f"策略公式: ,{func_name}, Stock Data:,{stock_data}\n")
                f.write(strat_orig_content)

            print(f"📁 單獨策略 CSV 檔 [{func_name}] 已成功匯出至：【{strat_csv_path}】")

    else:
        print("ℹ [提示] EXPORT_CSV 為 False，已略過 CSV 檔的本地產出。")


    # ==============================================================================
    # SECTION 7. 自動繪製股票波段 K 線走勢圖 (Wave Charts Generation)
    # ==============================================================================
    if GENERATE_WAVE_CHARTS and not dashboard_df.empty:

        # 繪圖資料夾以 "dashboard" 代替 strat_tag，並直接輸出到剛才建立的 CSV 資料夾內
        wave_output_dir = os.path.join(output_dir, "dashboard_wave_plots")

        print(f'\n📈 正在根據波段規則繪製股票 K 線走勢圖...')

        nas_path = f"{os.getenv('NAS_SFTP_PATH').rstrip('/')}/{sub_folder_name}" if os.getenv('NAS_SFTP_PATH') else None  

        plot_files = generate_qiantang_wave_charts(
            dashboard_df=dashboard_df,
            global_df=global_df,
            output_dir=wave_output_dir,
            nas_sftp_path=nas_path,
        )

        print(
            f'✅ 成功產出 {len(plot_files)} 張波段走勢圖，儲存於:'
            f' {wave_output_dir}'
        )

        
    # =====================================================================
    # 7. 自動備份至 NAS
    # =====================================================================
    if os.getenv("NAS_SFTP_PATH"):
        if EXPORT_EXCEL and os.path.exists(file_path):
            remote_excel_path = f"{os.getenv('NAS_SFTP_PATH')}/{sub_folder_name}/{file_name}"
            try:
                archive_and_cleanup(file_path, remote_excel_path)
                print(f"📦 Excel 報告已備份至 NAS：{remote_excel_path}")
            except Exception as e:
                print(f"⚠ Excel NAS 備份失敗: {e}")

        if EXPORT_CSV:
            # 1. 備份總表 Dashboard CSV
            if csv_file_path and os.path.exists(csv_file_path):
                remote_csv_path = f"{os.getenv('NAS_SFTP_PATH')}/{sub_folder_name}/{csv_file_name}"
                try:
                    archive_and_cleanup(csv_file_path, remote_csv_path)
                    print(f"📦 綜合儀表板 CSV 已成功備份至 NAS 並清理本地：{remote_csv_path}")
                except Exception as e:
                    print(f"⚠ 綜合儀表板 CSV NAS 備份失敗: {e}")

            # 2. 🌟 迴圈備份所有「單獨策略」的 CSV 檔至 NAS
            for strat in strategies:
                func_name = strat.__name__
                strat_csv_name = f"{func_name}_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
                strat_csv_path = os.path.join(output_dir, strat_csv_name)
                
                if os.path.exists(strat_csv_path):
                    remote_strat_csv_path = f"{os.getenv('NAS_SFTP_PATH')}/{sub_folder_name}/{strat_csv_name}"
                    try:
                        archive_and_cleanup(strat_csv_path, remote_strat_csv_path)
                        print(f"📦 單獨策略 CSV [{func_name}] 已成功備份至 NAS：{remote_strat_csv_path}")
                    except Exception as e:
                        print(f"⚠ 單獨策略 CSV [{func_name}] NAS 備份失敗: {e}")
    
    """
    csv_file_path = None
    
    # 🌟 1. 自動取得當前測試策略名稱
    strat_tag = "_".join([s.__name__ for s in strategies]) if strategies else "qiantang"

    # 🌟 2. 找到 EXPORT_CSV 區塊，修改 csv_file_name 這行：
    if EXPORT_CSV:
        source_folder_name = "qiantang_test_report"
        os.makedirs(f"data/{source_folder_name}", exist_ok=True)
    
        # ❌ 原本：f"dashboard_summary_{start_date_str}..."
        # ✅ 改為（直接以策略名稱開頭，不帶 dashboard_summary_）：
        csv_file_name = f"{strat_tag}_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
    
        csv_file_path = os.path.abspath(f"data/{source_folder_name}/{csv_file_name}")
        dashboard_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')

        # 2. 🌟 讀取剛剛寫入的檔案，並在最前面插入 stock_data 字串與一個空行
        with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
            original_content = f.read()
            
        with open(csv_file_path, 'w', encoding='utf-8-sig') as f:
            # 寫入第一列（你可以根據喜好調整格式，例如加上標籤或直接寫入 stock_data）
            f.write(f"策略程式: ,{strat_tag}, Stock Data:,{stock_data}\n") 
            # 接著寫入原本的 DataFrame 內容
            f.write(original_content)
        
        print(f"📊 綜合儀表板 CSV 檔已成功匯出至：【{csv_file_path}】")
    else:
        print("ℹ [提示] EXPORT_CSV 為 False，已略過 CSV 檔的本地產出。")


    # ==============================================================================
    # SECTION 7. 自動繪製股票波段 K 線走勢圖 (Wave Charts Generation)
    # ==============================================================================
    if GENERATE_WAVE_CHARTS and not dashboard_df.empty:

      # 1. 定義基礎資料目錄 (統一使用 "data")
      DATA_DIR = "output"

      # 2. 自動建立帶有執行時間戳記的輸出資料夾 (例如: data/wave_plots_20261011_1544)
      run_time_str = datetime.now(tz_tw).strftime('%Y%m%d_%H%M')
      wave_output_dir = os.path.join(DATA_DIR, f'{strat_tag}_wave_plots_{run_time_str}')

      print(f'\n📈 正在根據波段規則繪製股票 K 線走勢圖...')

      # 3. 取得 NAS 備份路徑 (對齊原主程式的環境變數讀取方式)
      #nas_path = os.getenv('NAS_SFTP_PATH') if os.getenv('NAS_SFTP_PATH') else None
      nas_path = f"{os.getenv('NAS_SFTP_PATH').rstrip('/')}/{source_folder_name}" if os.getenv('NAS_SFTP_PATH') else None  

      # 4. 呼叫繪圖模組 (搭配最新 v3 版本的純 SFTP 模式，會自動傳至 NAS)
      plot_files = generate_qiantang_wave_charts(
          dashboard_df=dashboard_df,
          global_df=global_df,
          output_dir=wave_output_dir,
          nas_sftp_path=nas_path,
      )

      print(
          f'✅ 成功產出 {len(plot_files)} 張波段走勢圖，儲存於:'
          f' {wave_output_dir}'
      )
    
    # =====================================================================
    # 7. 自動備份至 NAS
    # =====================================================================
    if os.getenv("NAS_SFTP_PATH"):
        if EXPORT_EXCEL and os.path.exists(file_path):
            remote_excel_path = f"{os.getenv('NAS_SFTP_PATH')}/{source_folder_name}/{file_name}"
            try:
                archive_and_cleanup(file_path, remote_excel_path)
                print(f"📦 Excel 報告已備份至 NAS：{remote_excel_path}")
            except Exception as e:
                print(f"⚠ Excel NAS 備份失敗: {e}")

        if EXPORT_CSV and csv_file_path and os.path.exists(csv_file_path):
            remote_csv_path = f"{os.getenv('NAS_SFTP_PATH')}/{source_folder_name}/{csv_file_name}"
            try:
                archive_and_cleanup(csv_file_path, remote_csv_path)
                print(f"📦 儀表板 CSV 已成功備份至 NAS 並清理本地：{remote_csv_path}")
            except Exception as e:
                print(f"⚠ CSV NAS 備份失敗: {e}")
    """


if __name__ == "__main__":
    print("test_qiantang_Strategy.py")
    run_qiantang_strategy_range_scan()
