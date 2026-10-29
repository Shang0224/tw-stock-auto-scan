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

from utils.analytics import PULLBACK_LIMIT_PCT

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
    st_qiantang_f3_after_shakeout_20261018_1,
    st_qiantang_f3_after_shakeout_20261020_1,
    st_qiantang_f3_after_shakeout_20261020_2,
    st_qiantang_f3_after_shakeout_20261020_3,
    st_qiantang_f3_after_shakeout_20261001_1_1_1, #MACD精進版
    st_qiantang_f3_after_shakeout_20261001_1_1_2, #大盤年線過熱過濾, ols斜率>1.0強勢股豁免
    st_qiantang_f3_after_shakeout_20261001_1_1_3, #終極精準降噪旗艦版, 失敗
    st_qiantang_f3_after_shakeout_20261001_1_1_4,  #終極精準降噪旗艦版, 失敗
    st_qiantang_f3_after_shakeout_20261001_1_1_5,  #重新回到st_qiantang_f3_after_shakeout_20261001_1_1_2 失敗, CAT1/3一起都砍
    st_qiantang_f3_after_shakeout_20261022_1_1_6, #從st_qiantang_f3_after_shakeout_20261001_1_1_2修改, 籌碼共振與高位強勢旗艦版
    st_qiantang_f3_after_shakeout_20261023, #20261020_1（強勢高位+T+3） 與 1_1_5（黃金雙防線版） 融合版
    st_qiantang_f3_after_shakeout_20261029,

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
    #generate_qiantang_wave_charts, #  🌟 直接從子模組匯入，避開 utils/__init__.py 的影響, 免得導致執行時, 不繪圖但還要花很多時間載入中文字型   
    #parse_stock_dict,
    parse_and_validate_stocks,
    calculate_wave_dedup_info,
)

# =====================================================================
# 🎛 多方策略測試控制面板 (指定天期區間)
# =====================================================================
# 💡 目前僅單獨測試：st_qiantang_f3_after_shakeout_20261001_1
TEST_QIANTANG_STRATEGY = [
    #st_qiantang_f1_spt_growth,      # F1: 筆張現形
    #st_qiantang_f2_volume_breakout, # F2: 出量上輕
    #st_qiantang_f3_after_shakeout,  # F3: 洗盤後
    #st_qiantang_f3_after_shakeout_20261020_2,
    #st_qiantang_f3_after_shakeout_20261020_3,
    st_qiantang_f3_after_shakeout_20261020_1,
    #st_qiantang_f3_after_shakeout_20261018_1,
    #st_qiantang_f3_after_shakeout_20261017_1,
    #st_qiantang_f3_after_shakeout_20261001_1_3_2, # F3: 洗盤後優化版 (唯一開啟)
    #st_qiantang_f3_after_shakeout_20261001_1_1_1, #MACD精進版
    #st_qiantang_f3_after_shakeout_20261001_1_1_2, #大盤年線過熱過濾, ols斜率>1.0強勢股豁免
    #st_qiantang_f3_after_shakeout_20261001_1_1_3, #終極精準降噪旗艦版
    #st_qiantang_f3_after_shakeout_20261001_1_1_4,  #終極精準降噪旗艦版, 修正版
    st_qiantang_f3_after_shakeout_20261001_1_1_5,  #重新回到st_qiantang_f3_after_shakeout_20261001_1_1_2
    #st_qiantang_f3_after_shakeout_20261022_1_1_6, #從st_qiantang_f3_after_shakeout_20261001_1_1_2修改, 籌碼共振與高位強勢旗艦版
    st_qiantang_f3_after_shakeout_20261023, #20261020_1（強勢高位+T+3） 與 1_1_5（黃金雙防線版） 融合版
    st_qiantang_f3_after_shakeout_20261029,
        
    
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
TEST_START_DATE = "2015-01-01"  # 測試起始日期 (YYYY-MM-DD)
TEST_END_DATE = "2025-09-30"    # 測試結束日期 (YYYY-MM-DD)
DAYS_BEFORE = 400               # 歷史技術指標計算緩衝天數, 配合某些策略要T+N日, 故從365天向前增加至400

# 🌟 大盤趨勢濾網控制開關
USE_MARKET_FILTER = True        # 是否啟用大盤趨勢濾網 (True: 啟用防守 / False: 關閉防守)
MARKET_FILTER_KEY = "EMA60"     # 大盤門檻指標 (預設季線 EMA60)

# ==============================================================================
# 🎛 走勢圖繪製控制開關
# ==============================================================================
GENERATE_WAVE_CHARTS = True  # 選股完成後是否自動繪製波段 K 線走勢圖

# 🌟 檔案輸出控制開關
EXPORT_EXCEL = False            # 是否輸出與上傳 Excel 報告
EXPORT_CSV = True               # 是否輸出與上傳綜合儀表板 CSV 檔

# 模式 A：CSV 檔案載入模式
STOCK_MODE = "csv"

STOCK_INPUT = "data/TestData/qiantang_mid100_test.csv"
#STOCK_INPUT = "data/TestData/qiantang_mid100_hot.csv"
#STOCK_INPUT = "data/MID100.csv"
#STOCK_INPUT = os.getenv("STOCK_FILES", "data/MID100.csv")
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


# -----------------------------------------------------------------
# 型態安全工具函式 (攔截 NaN，自動補 0 維持整數欄位)
# -----------------------------------------------------------------
def safe_lots_from_shares(val) -> int:
  """三大法人專用：原生為「股」，除以 1000 轉為「張」"""
  if pd.isna(val) or val is None:
    return 0
  return int(round(float(val) / 1000.0))


def safe_lots_from_lots(val) -> int:
  """信用交易專用：原生即為「張」，不除以 1000"""
  if pd.isna(val) or val is None:
    return 0
  return int(round(float(val)))

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

    # 4. 查閱當日大盤環境數據
    m_info = market_dict.get(day_str, {}) if market_dict else {}

    try:
        # 執行當日單一股票掃描
        hits = scan_single_stock(
            df_single=df_single,
            category=stock_cat,
            func_list=strategies,
            param_profiles=profiles_map,
            market_info=m_info,
        )
    except Exception as e:
        # 攔截該檔股票當天發生的任何例外    
        print(f'⚠️ [股票掃描跳過] 股票代號: {stock_id} | 日期: {day_str} | 錯誤: {e}')
        continue
        
    if hits:
      # 取得觸發當日 (Day T) 的預處理資料列
      latest_row = df_single.iloc[-1]
      close_price = round(float(latest_row["close"]), 2)
      vol_today = float(latest_row.get("Trading_Volume", 0))
      vol_lots = int(vol_today / 1000)

      # 4. 查閱當日大盤環境數據
      #m_info = market_dict.get(day_str, {}) if market_dict else {}
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
            
            "大盤月線乖離率(%)": round(
                float(m_info.get("taiex_ma20_bias_pct", 0)), 2
            ),
            
            "大盤季線乖離率(%)": round(
                float(m_info.get("taiex_ma60_bias_pct", 0)), 2
            ),

            "大盤年線乖離率(%)": round(
                float(m_info.get("taiex_ma240_bias_pct", 0)), 2
            ),

            "大盤季線與年線乖離率(%)": round(
                float(m_info.get("taiex_ma60_ma240_bias_pct", 0)), 2
            ),
            
            # -----------------------------------------------------------------
            # 📌 基礎量能與三大法人/資券動向 (報表層統一除以 1000 輸出張數)
            # -----------------------------------------------------------------
            "今日成交量(張)": int(
                round(float(latest_row.get("Trading_Volume", 0)) / 1000.0)
            ),
            "外資買超(張)": safe_lots_from_shares(latest_row.get("Foreign_Investor")),
            "投信買超(張)": safe_lots_from_shares(latest_row.get("Investment_Trust")),
            "自營商買超(張)": safe_lots_from_shares(latest_row.get("Dealer_self")),
            "主力買超(張)": safe_lots_from_shares(latest_row.get("major_net")),
            "外資近5日累計(張)": safe_lots_from_shares(latest_row.get("foreign_5d_shares_sum")),
            "投信近5日累計(張)": safe_lots_from_shares(latest_row.get("trust_5d_shares_sum")),
            "主力近5日累計(張)": safe_lots_from_shares(latest_row.get("major_5d_shares_sum")),
            "融資餘額(張)": safe_lots_from_lots(latest_row.get("MarginPurchaseTodayBalance")),
            "融資當日增減(張)": safe_lots_from_lots(latest_row.get("margin_diff_shares")),
            "融券餘額(張)": safe_lots_from_lots(latest_row.get("ShortSaleTodayBalance")),
            "融券當日增減(張)": safe_lots_from_lots(latest_row.get("short_diff_shares")),
        }

        # -----------------------------------------------------------------
        # ⏱️ 第二類：進場後績效與軌跡細節 (果)
        # -----------------------------------------------------------------
        hit_record.update(fwd_perf)
        hit_record.update(extreme_perf)
          
        day_hits.append(hit_record)

  return day_hits

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
    # 🛡 關卡 2：大盤趨勢第一道防線 (雙重確認：價格 > EMA60 且 斜率 > 0)
    # =================================================================
    if USE_MARKET_FILTER:
        market_info = market_dict.get(day_str)
        if market_info:
            m_close = market_info.get("close", 0)
            m_ema = market_info.get(MARKET_FILTER_KEY, 0)
            m_slope = market_info.get("EMA60_slope", 0)  # 🌟 1. 取出大盤 EMA60 斜率    
            print(f"EMA60_slope : {m_slope}\n")
            # 🌟 2. 雙重防線：當大盤 <= EMA60 季線 或 斜率 <= 0 (走平/向下) 時，當天跳過不選股
            if m_close <= m_ema or m_slope <= 0:
                current_day += timedelta(days=1)
                continue
    """
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
    """
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

  # 🌟 核心修改：針對「各個別策略」獨立執行波段去重與標記
  for strat in strategies:
      func_name = strat.__name__
      if func_name in results_by_formula and results_by_formula[func_name]:
          print(f"🔄 正在對個別策略 [{func_name}] 進行波段 First Trigger 去重與標記...")
          # 傳入該策略獨立的選股串列，產出專屬的波段群組編號與首發標籤
          results_by_formula[func_name] = calculate_wave_dedup_info(results_by_formula[func_name])

    
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

  # =====================================================================
  # 🌟 統一定義輸出資料夾名稱與絕對路徑 (供 CSV、Excel 與繪圖模組共用)
  # =====================================================================
  mkt_tag = "大盤濾網" if USE_MARKET_FILTER else "無大盤濾網"

  sub_folder_name = f"qiantang_test_report/{start_date_str}_to_{end_date_str}_{current_time_str}_{mkt_tag}_{PULLBACK_LIMIT_PCT}"
    
  output_dir = os.path.abspath(os.path.join("data", sub_folder_name))
  os.makedirs(output_dir, exist_ok=True)
    
  if EXPORT_CSV:
    # 1. 建立輸出資料夾
    #sub_folder_name = (
    #    f"qiantang_test_report/{start_date_str}_to_{end_date_str}_{current_time_str}"
    #)
    #output_dir = os.path.abspath(os.path.join("data", sub_folder_name))
    #os.makedirs(output_dir, exist_ok=True)

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
      f.write(f"策略程式: ,{strat_tag}, Stock Data:,{stock_data}, 大盤濾網: {USE_MARKET_FILTER}\n")
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
        f.write(f"策略公式: ,{func_name}, Stock Data:,{stock_data}, 大盤濾網: {USE_MARKET_FILTER}\n")
        f.write(strat_orig_content)

      print(
          f"📁 單獨策略 CSV 檔 [{func_name}]"
          f" 已成功匯出至：【{strat_csv_path}】"
      )

  else:
    print("ℹ [提示] EXPORT_CSV 為 False，已略過 CSV 檔的本地產出。")

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

  # ==============================================================================
  # SECTION 7. 自動繪製股票波段 K 線走勢圖 (Wave Charts Generation)
  # ==============================================================================
  if GENERATE_WAVE_CHARTS and not dashboard_df.empty:
    # 🌟 直接從子模組匯入，避開 utils/__init__.py 的影響
    from utils.wave_chart_generator import generate_qiantang_wave_charts

    # 🌟 核心修改：繪圖前，直接為跨策略的 dashboard_df 補上波段去重編號
    dashboard_records = calculate_wave_dedup_info(dashboard_df.to_dict('records'))
    dashboard_df = pd.DataFrame(dashboard_records)
    
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

if __name__ == "__main__":
    print("test_qiantang_Strategy.py")
    run_qiantang_strategy_range_scan()
