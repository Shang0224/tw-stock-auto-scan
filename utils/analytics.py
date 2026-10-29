# utils/analytics.py
from datetime import datetime
import re
import numpy as np
import pandas as pd

PULLBACK_LIMIT_PCT = -15.0  # 2131 版深跌門檻

def _extract_date_from_perf_str(val: str) -> str:
    """輔助函式：從績效字串 (例如 '+39.91% (2015-05-27, 價:184.01)') 擷取 YYYY-MM-DD 日期"""
    if not val or not isinstance(val, str):
        return None
    match = re.search(r'\d{4}-\d{2}-\d{2}', val)
    return match.group(0) if match else None


def calculate_wave_dedup_info(
    stock_id: str,
    trigger_date_str: str,
    global_df: pd.DataFrame,
    extreme_perf: dict = None,
    history_wave_tracker: dict = None,
    max_gap_days: int = 90
) -> dict:
    """
    完全仿照 calculate_forward_horizon_returns / calculate_one_year_extremes 介面。
    依據《三階段波段去重 SOP》，計算當前觸發訊號的【波段群組編號】與【波段首發】狀態。

    :param stock_id: 股票代號 (例如 '2368')
    :param trigger_date_str: 當前觸發日期 (例如 '2023-05-23')
    :param global_df: 全量歷史 K 線資料 DataFrame
    :param extreme_perf: 前一步 calculate_one_year_extremes 計算出的極值字典 (可選，加快計算)
    :param history_wave_tracker: 跨日掃描累計的波段快取字典 {stock_id: [wave_record_dict, ...]}
    :param max_gap_days: 60 個交易日安全鎖對應之最大日曆天數 (預設 90 天)
    :return: 包含去重標籤的字典 {'波段群組編號': '2368_20230324', '波段首发': False, '波段首發觸發日': '2023-03-24'}
    """
    if history_wave_tracker is None:
        history_wave_tracker = {}

    # 1. 取得當前訊號的極值日期 (Date_MFE / Date_MAE)
    if extreme_perf:
        mfe_str = extreme_perf.get("持倉最高績效", extreme_perf.get("1Y內最高績效", ""))
        mae_str = extreme_perf.get("持倉實際最低績效", extreme_perf.get("1Y內最低績效", ""))
    else:
        # 若未傳入，亦可自動重算一次極值
        ext_dict = calculate_one_year_extremes(stock_id, trigger_date_str, global_df)
        mfe_str = ext_dict.get("持倉最高績效", ext_dict.get("1Y內最高績效", ""))
        mae_str = ext_dict.get("持倉實際最低績效", ext_dict.get("1Y內最低績效", ""))

    cur_mfe_date = _extract_date_from_perf_str(mfe_str)
    cur_mae_date = _extract_date_from_perf_str(mae_str)
    cur_dt = pd.to_datetime(trigger_date_str)

    # 取出該股票過往已記錄的歷史波段列表
    stock_history = history_wave_tracker.setdefault(stock_id, [])

    # 2. 檢視過往歷史波段，判斷是否屬於同一波段的後續觸發
    matched_wave = None
    for wave in reversed(stock_history):
        t0_dt = wave["first_trigger_dt"]
        
        # 🛡 60 天時間間隔安全鎖 (超過 90 個日曆天自動強制切割)
        if (cur_dt - t0_dt).days > max_gap_days:
            break

        prev_mfe_date = wave["Date_MFE"]
        prev_mae_date = wave["Date_MAE"]

        # 三階段對齊條件 (雙邊完全對齊 或 單邊邊界漂移對齊)
        exact_match = (cur_mfe_date and prev_mfe_date and cur_mfe_date == prev_mfe_date) and \
                      (cur_mae_date and prev_mae_date and cur_mae_date == prev_mae_date)
        mae_match = (cur_mae_date and prev_mae_date and cur_mae_date == prev_mae_date)
        mfe_match = (cur_mfe_date and prev_mfe_date and cur_mfe_date == prev_mfe_date)

        if exact_match or mae_match or mfe_match:
            matched_wave = wave
            break

    # 3. 產出去重標記結果
    if matched_wave:
        # 屬同一波段之後續觸發
        first_date_clean = matched_wave["first_trigger_date"].replace("-", "")
        group_id = f"{stock_id}_{first_date_clean}"
        
        return {
            "波段群組編號": group_id,
            "波段首發": False,
            "波段首發觸發日": matched_wave["first_trigger_date"]
        }
    else:
        # 判定為全新波段首發 (First Trigger)
        t0_date_clean = trigger_date_str.replace("-", "")
        group_id = f"{stock_id}_{t0_date_clean}"

        # 登記新波段至歷史快取中，子供後續觸發點比對
        stock_history.append({
            "first_trigger_date": trigger_date_str,
            "first_trigger_dt": cur_dt,
            "Date_MFE": cur_mfe_date,
            "Date_MAE": cur_mae_date,
            "group_id": group_id
        })

        return {
            "波段群組編號": group_id,
            "波段首發": True,
            "波段首發觸發日": trigger_date_str
        }

def calculate_forward_horizon_returns(
    stock_id: str, trigger_date_str: str, global_df: pd.DataFrame
) -> dict:
  """計算進場後「時間階梯前瞻報酬率」與「T+1~T+3 極短線軌跡拉回 %」

  包含：T+1~T+3 每日收盤報酬率、T+1~T+3 盤中最低價最大回撤 (Min_Pct)、
  以及 T+3, T+5, T+10, T+20, T+60 (3個月), T+120 (6個月), T+240 (1年) 時間階梯報酬。
  """
  if global_df is None or global_df.empty:
    return {}

  # 1. 篩選該股票在觸發日 (Day T) 當日及未來的 K 線
  df_stock = (
      global_df[
          (global_df["stock_id"].astype(str) == str(stock_id))
          & (global_df["date"] >= trigger_date_str)
      ]
      .sort_values("date")
      .reset_index(drop=True)
  )

  if df_stock.empty or len(df_stock) < 1:
    return {}

  # 觸發當日 (Day T0) 收盤價
  close_t0 = float(df_stock["close"].iloc[0])
  if close_t0 <= 0:
    return {}

  perf_dict = {}

  # 2. 極短線進場軌跡：T+1, T+2, T+3 的收盤報酬與盤中最低拉回 %
  for offset in [1, 2, 3]:
    if len(df_stock) > offset:
      row_offset = df_stock.iloc[offset]
      close_tn = float(row_offset["close"])
      low_tn = float(row_offset["min"])

      close_ret = ((close_tn - close_t0) / close_t0) * 100.0
      min_ret = ((low_tn - close_t0) / close_t0) * 100.0

      perf_dict[f"T+{offset}_Pct"] = round(close_ret, 2)
      perf_dict[f"T+{offset}_Min_Pct"] = round(min_ret, 2)
    else:
      perf_dict[f"T+{offset}_Pct"] = "N/A"
      perf_dict[f"T+{offset}_Min_Pct"] = "N/A"

  # 3. 前瞻時間階梯報酬 (T+3, T+5, T+10, T+20, T+60, T+120, T+240)
  horizon_days = [3, 5, 10, 20, 60, 120, 240]
  for N in horizon_days:
    if len(df_stock) > N:
      row_n = df_stock.iloc[N]
      date_n = str(row_n["date"]).split(" ")[0]
      close_n = float(row_n["close"])
      ret_n = ((close_n - close_t0) / close_t0) * 100.0

      # 輸出帶有日期與價格的可讀字串與純數值
      perf_dict[f"T+{N}日績效"] = (
          f"{ret_n:+.2f}% ({date_n}, 價:{close_n:.2f})"
      )
      perf_dict[f"T+{N}_Return_Pct"] = round(ret_n, 2)
    else:
      perf_dict[f"T+{N}日績效"] = "N/A"
      perf_dict[f"T+{N}_Return_Pct"] = "N/A"

  return perf_dict

def calculate_one_year_extremes(
    stock_id: str, trigger_date_str: str, global_df: pd.DataFrame
) -> dict:
  """計算進場後「持倉最高績效」、「持倉實際最低績效」、「停損波段極限深度(%)」與 Cat 1~4 自動走勢標籤

  採用「動態持倉凍結機制 (Dynamic Holding Window Freeze)」：
  1. 觀察視野統一為進場起算 T0 -> T0 + 240 個交易日 (滿 1 年)。
  2. 交易帳戶持倉區間：限定為 T0+1 -> T_stop (首次盤中跌破停損線 PULLBACK_LIMIT_PCT，預設 -15.0% 當日)。
     - 若未觸發停損，則看滿 T0+1 -> T0 + 240。
     - 「持倉最高績效」：持倉期間最高漲幅 (%) 與日期 (離場後暴漲不計入)。
     - 「持倉實際最低績效」：持倉期間最低跌幅 (%) 與日期 (反應真實 MAE 與穿透滑點)。
  3. 風控與策略優化維度：
     - 「停損波段極限深度(%)」：專門售後觀察觸發停損 (T_stop) 後的個股走勢。
       - 情況 A (停損後在 T0 + 240 內成功攻上 >= +20%)：搜尋區間為 [T_stop -> 首次達到 +20% 當日]，記錄最深跌幅 (%) 做停損放寬拯救診斷。
       - 情況 B (停損後在 T0 + 240 內未曾達到 +20%)：搜尋區間為 [T_stop -> T0 + 240]，記錄最深跌幅 (%) 驗證停損防禦效益。
     - 「創高前最大回撤(%)」：記錄進場至持倉最高價當天期間的最深拉回 (%)。
  4. 個股物理性格維度 (備查)：
     - 「1Y全期最高漲幅(%)」與「1Y全期最深跌幅(%)」：備查 240 個交易日全期極限波幅。
  5. 走勢類別標籤：
     - 若有停損：依持倉最高漲幅分類 (>=50% Cat1, >=20% Cat2, <20% Cat3)。
     - 若無停損：依全期最高漲幅分類 (>=50% Cat1, >=20% Cat2, <20% Cat4)。
  """
  if global_df is None or global_df.empty:
    return {}

  # 1. 取出觸發日及未來 240 個交易日 (約 1 年) 的 K 線資料
  df_future = (
      global_df[
          (global_df["stock_id"].astype(str) == str(stock_id))
          & (global_df["date"] >= trigger_date_str)
      ]
      .sort_values("date")
      .reset_index(drop=True)
  )

  if df_future.empty or len(df_future) < 2:
    return {
        "持倉最高績效": "N/A",
        "持倉實際最低績效": "N/A",
        "1Y內最高績效": "N/A",
        "1Y內最低績效": "N/A",
        "走勢類別標籤": "資料不足",
    }

  # 買進基準價 (Day T0 收盤價)
  close_t0 = float(df_future["close"].iloc[0])
  if close_t0 <= 0:
    return {}

  # 未來觀察視窗 (排除 Day T 當天，往後取最多 240 個交易日，即 Day T+1 ~ Day T+240)
  df_window = df_future.iloc[1:241].copy().reset_index(drop=True)

  # 2. 個股全期 1 年 (T0 + 240) 極值資訊 (作為個股性格備查)
  full_max_idx = df_window["max"].idxmax()
  full_min_idx = df_window["min"].idxmin()

  full_max_price = float(df_window.iloc[full_max_idx]["max"])
  full_min_price = float(df_window.iloc[full_min_idx]["min"])

  full_max_date = str(df_window.iloc[full_max_idx]["date"]).split(" ")[0]
  full_min_date = str(df_window.iloc[full_min_idx]["date"]).split(" ")[0]

  full_max_perf_pct = ((full_max_price - close_t0) / close_t0) * 100.0
  full_min_perf_pct = ((full_min_price - close_t0) / close_t0) * 100.0

  # 3. 🌟【時序首發停損動態持倉凍結邏輯】
  stopout_limit = (
      PULLBACK_LIMIT_PCT if "PULLBACK_LIMIT_PCT" in globals() else -15.0
  )

  # 依時間順序檢查每日盤中最低價是否跌破停損線
  stopout_mask = (
      (df_window["min"] - close_t0) / close_t0 * 100.0 < stopout_limit
  )
  has_stopout = stopout_mask.any()

  if has_stopout:
    # 第一次跌破停損線的 K 線索引位置 (T_stop)
    first_stopout_idx = int(stopout_mask.idxmax())

    # 動態凍結：持倉區間限制在進場至第一次停損當天 (Day T+1 ~ Day T_stop)
    df_holding = df_window.iloc[: first_stopout_idx + 1]

    # 持倉最高點 (MFE during holding)
    holding_max_idx = df_holding["max"].idxmax()
    row_holding_max = df_holding.iloc[holding_max_idx]
    holding_max_price = float(row_holding_max["max"])
    holding_max_date = str(row_holding_max["date"]).split(" ")[0]
    holding_days_to_max = int(holding_max_idx) + 1
    holding_max_perf_pct = ((holding_max_price - close_t0) / close_t0) * 100.0

    # 持倉實際最低點 (MAE during holding，包含離場當天滑點與穿透)
    holding_min_idx = df_holding["min"].idxmin()
    row_holding_min = df_holding.iloc[holding_min_idx]
    holding_min_price = float(row_holding_min["min"])
    holding_min_date = str(row_holding_min["date"]).split(" ")[0]
    holding_days_to_min = int(holding_min_idx) + 1
    holding_min_perf_pct = ((holding_min_price - close_t0) / close_t0) * 100.0

    # -----------------------------------------------------------------
    # 🎯 停損波段極限深度 (%)：停損當日 (T_stop) 開始往後至 T0 + 240 內診斷
    # -----------------------------------------------------------------
    df_after_stop = df_window.iloc[first_stopout_idx:]

    # 檢查在 T0 + 240 內，停損後是否攻上 >= +20% (相較於 close_t0)
    reach_20_mask = ((df_after_stop["max"] - close_t0) / close_t0 * 100.0) >= 20.0
    has_reached_20 = reach_20_mask.any()

    if has_reached_20:
      # 情況 A：停損後在 T0 + 240 內成功攻上 >= +20%
      # 找到首次達到 +20% 的相對索引位置
      first_20_rel_idx = int(reach_20_mask.idxmax())
      # 搜尋區間：[T_stop -> 首次攻上 +20% 當日]
      search_window = df_window.iloc[first_stopout_idx : first_20_rel_idx + 1]
    else:
      # 情況 B：停損後在 T0 + 240 內未曾達到 +20%
      # 搜尋區間：[T_stop -> T0 + 240]
      search_window = df_after_stop

    stopout_wave_trough_price = float(search_window["min"].min())
    stopout_wave_trough_pct = (
        (stopout_wave_trough_price - close_t0) / close_t0
    ) * 100.0

    # 分類判定 (基於持倉期間最高漲幅)
    if holding_max_perf_pct >= 50.0:
      category_tag = "Cat1_飆股"
    elif holding_max_perf_pct >= 20.0:
      category_tag = "Cat2_溫和上漲"
    else:
      category_tag = "Cat3_深跌陷阱"

  else:
    # 全程未跌破停損線，持倉視窗看滿 240 個交易日
    holding_max_idx = full_max_idx
    holding_max_price = full_max_price
    holding_max_date = full_max_date
    holding_days_to_max = int(full_max_idx) + 1
    holding_max_perf_pct = full_max_perf_pct

    holding_min_idx = full_min_idx
    holding_min_price = full_min_price
    holding_min_date = full_min_date
    holding_days_to_min = int(full_min_idx) + 1
    holding_min_perf_pct = full_min_perf_pct

    stopout_wave_trough_pct = "N/A"

    # 分類判定 (基於全期最高漲幅)
    if holding_max_perf_pct >= 50.0:
      category_tag = "Cat1_飆股"
    elif holding_max_perf_pct >= 20.0:
      category_tag = "Cat2_溫和上漲"
    else:
      category_tag = "Cat4_窄幅橫盤"

  # 創高前最大回撤 (%)：進場至持倉最高價當天 (holding_max_idx) 期間的最深拉回
  df_before_peak = df_window.iloc[: holding_max_idx + 1]
  lowest_before_peak = float(df_before_peak["min"].min())
  mdd_before_peak_pct = ((lowest_before_peak - close_t0) / close_t0) * 100.0

  extremes_dict = {
      # -----------------------------------------------------------------
      # 🎯 持倉帳戶維度 (真實持倉損益與滑點)
      # -----------------------------------------------------------------
      "持倉最高績效": f"{holding_max_perf_pct:+.2f}% ({holding_max_date})",
      "持倉實際最低績效": (
          f"{holding_min_perf_pct:+.2f}% ({holding_min_date})"
      ),
      "持倉最高價": round(holding_max_price, 2),
      "持倉最高天數": holding_days_to_max,
      "持倉最低價": round(holding_min_price, 2),
      "持倉最低天數": holding_days_to_min,
      "最大波段浮盈_MFE(%)": round(holding_max_perf_pct, 2),
      "最大波段浮虧_MAE(%)": round(holding_min_perf_pct, 2),
      # -----------------------------------------------------------------
      # 🛡️ 風控與策略優化維度 (停損敏感度診斷)
      # -----------------------------------------------------------------
      "停損波段極限深度(%)": (
          round(stopout_wave_trough_pct, 2)
          if isinstance(stopout_wave_trough_pct, (int, float))
          else stopout_wave_trough_pct
      ),
      "創高前最大回撤(%)": round(mdd_before_peak_pct, 2),
      # -----------------------------------------------------------------
      # 📈 個股物理性格維度 (全期備查)
      # -----------------------------------------------------------------
      "1Y全期最高漲幅(%)": round(full_max_perf_pct, 2),
      "1Y全期最深跌幅(%)": round(full_min_perf_pct, 2),
      "走勢類別標籤": category_tag,
      # -----------------------------------------------------------------
      # 🔄 舊版別名相容 (防止其他腳本讀取失敗)
      # -----------------------------------------------------------------
      "1Y內最高績效": f"{holding_max_perf_pct:+.2f}% ({holding_max_date})",
      "1Y內最低績效": (
          f"{holding_min_perf_pct:+.2f}% ({holding_min_date})"
      ),
  }

  return extremes_dict


def calculate_one_year_extremes_old1(
    stock_id: str, trigger_date_str: str, global_df: pd.DataFrame
) -> dict:
  """計算進場後未來 1 年 (約 240 個交易日) 內的「極值、登頂軌跡風險與 Cat 1~4 自動走勢標籤」

  包含：1Y內最高/最低價、極值報酬率與達到天數、創高前最大回撤 % (Max Drawdown Before Peak)、
  創低前最大漲幅 % (Max Gain Before Trough)、MAE/MFE 波動指標，並自動判定走勢類別標籤 
  (Cat 1 飆股 / Cat 2 溫和小漲 / Cat 3 深跌陷阱 / Cat 4 窄幅橫盤)。
  """
  if global_df is None or global_df.empty:
    return {}

  # 1. 取出觸發日及未來 240 個交易日 (約 1 年) 的 K 線資料
  df_future = (
      global_df[
          (global_df["stock_id"].astype(str) == str(stock_id))
          & (global_df["date"] >= trigger_date_str)
      ]
      .sort_values("date")
      .reset_index(drop=True)
  )

  if df_future.empty or len(df_future) < 2:
    return {
        "1Y內最高績效": "N/A",
        "1Y內最低績效": "N/A",
        "走勢類別標籤": "資料不足",
    }

  # 買進基準價 (Day T 收盤價)
  close_t0 = float(df_future["close"].iloc[0])
  if close_t0 <= 0:
    return {}

  # 未來觀察視窗 (排除 Day T 當天，往後取最多 240 個交易日)
  df_window = df_future.iloc[1:241].copy().reset_index(drop=True)

  # 2. 定位未來 1 年內最高點與最低點
  max_idx = df_window["max"].idxmax()
  min_idx = df_window["min"].idxmin()

  row_max = df_window.iloc[max_idx]
  row_min = df_window.iloc[min_idx]

  max_price_1y = float(row_max["max"])
  min_price_1y = float(row_min["min"])

  max_date_1y = str(row_max["date"]).split(" ")[0]
  min_date_1y = str(row_min["date"]).split(" ")[0]

  # 交易日天數差距 (從 Day T+1 開始算起第幾天達到極值)
  days_to_max = int(max_idx) + 1
  days_to_min = int(min_idx) + 1

  # 極值報酬率 (%)
  max_perf_pct = ((max_price_1y - close_t0) / close_t0) * 100.0
  min_perf_pct = ((min_price_1y - close_t0) / close_t0) * 100.0

  # 3. 計算【創高前最大回撤 % (Max Drawdown Before Peak)】
  df_before_peak = df_window.iloc[: max_idx + 1]
  lowest_before_peak = float(df_before_peak["min"].min())
  mdd_before_peak_pct = (
      (lowest_before_peak - close_t0) / close_t0
  ) * 100.0

  # 4. 判定最低點是否先於最高點發生 (is_pullback_first)
  is_pullback_first = days_to_min < days_to_max

  gain_before_trough_pct = None

  if is_pullback_first:
    # 🌟 僅在 is_pullback_first 為 True 時，才去計算「創低前的最高漲幅 %」
    df_before_trough = df_window.iloc[: min_idx + 1]
    highest_before_trough = float(df_before_trough["max"].max())
    gain_before_trough_pct = (
        (highest_before_trough - close_t0) / close_t0
    ) * 100.0

    if min_perf_pct < PULLBACK_LIMIT_PCT:
      # 最低點先發生且跌破 -15%：依「創低前的最高漲幅」認定走勢分類
      if gain_before_trough_pct >= 50.0:
        category_tag = "Cat1_飆股"
      elif gain_before_trough_pct >= 20.0:
        category_tag = "Cat2_溫和上漲"
      else:
        category_tag = "Cat3_深跌陷阱"
    else:
      # 未跌破 -15%：依 1Y 最高漲幅分類
      if max_perf_pct >= 50.0:
        category_tag = "Cat1_飆股"
      elif max_perf_pct >= 20.0:
        category_tag = "Cat2_溫和上漲"
      else:
        category_tag = "Cat4_窄幅橫盤"
  else:
    # 🌟 最高點先於最低點發生 (is_pullback_first 為 False)
    if max_perf_pct >= 50.0:
      category_tag = "Cat1_飆股"
    elif max_perf_pct >= 20.0:
      category_tag = "Cat2_溫和上漲"
    elif min_perf_pct < PULLBACK_LIMIT_PCT:
      category_tag = "Cat3_深跌陷阱"
    else:
      category_tag = "Cat4_窄幅橫盤"

  extremes_dict = {
      "1Y內最高績效": f"{max_perf_pct:+.2f}% ({max_date_1y})",
      "1Y內最低績效": f"{min_perf_pct:+.2f}% ({min_date_1y})",
      "1Y最高價": round(max_price_1y, 2),
      "1Y最高天數": days_to_max,
      "1Y最低價": round(min_price_1y, 2),
      "1Y最低天數": days_to_min,
      "創高前最大回撤(%)": round(mdd_before_peak_pct, 2),
      "創低前最大漲幅(%)": (
          round(gain_before_trough_pct, 2)
          if gain_before_trough_pct is not None
          else "N/A"
      ),
      "最大波段浮盈_MFE(%)": round(max_perf_pct, 2),
      "最大波段浮虧_MAE(%)": round(min_perf_pct, 2),
      "走勢類別標籤": category_tag,
  }

  return extremes_dict


def calculate_one_year_extremes_old(
    stock_id: str, trigger_date_str: str, global_df: pd.DataFrame
) -> dict:
  """計算進場後未來 1 年 (約 240 個交易日) 內的「極值、登頂軌跡風險與 Cat 1~4 自動走勢標籤」

  包含：1Y內最高/最低價、極值報酬率與達到天數、創高前最大回撤 % (Max Drawdown Before
  Peak)、 MAE/MFE 波動指標，並自動判定走勢類別標籤 (Cat 1 飆股 / Cat 2 小漲 / Cat 3
  陷阱股 / Cat 4 盤整)。
  """
  if global_df is None or global_df.empty:
    return {}

  # 1. 取出觸發日及未來 240 個交易日 (約 1 年) 的 K 線資料
  df_future = (
      global_df[
          (global_df["stock_id"].astype(str) == str(stock_id))
          & (global_df["date"] >= trigger_date_str)
      ]
      .sort_values("date")
      .reset_index(drop=True)
  )

  if df_future.empty or len(df_future) < 2:
    return {
        "1Y內最高績效": "N/A",
        "1Y內最低績效": "N/A",
        "Category_Tag": "資料不足",
    }

  # 買進基準價 (Day T 收盤價)
  close_t0 = float(df_future["close"].iloc[0])
  if close_t0 <= 0:
    return {}

  # 未來觀察視窗 (排除 Day T 當天，往後取最多 240 個交易日)
  df_window = df_future.iloc[1:241].copy().reset_index(drop=True)

  # 2. 定位未來 1 年內最高點與最低點
  max_idx = df_window["max"].idxmax()
  min_idx = df_window["min"].idxmin()

  row_max = df_window.iloc[max_idx]
  row_min = df_window.iloc[min_idx]

  max_price_1y = float(row_max["max"])
  min_price_1y = float(row_min["min"])

  max_date_1y = str(row_max["date"]).split(" ")[0]
  min_date_1y = str(row_min["date"]).split(" ")[0]

  # 交易日天數差距 (從 Day T+1 開始算起第幾天達到極值)
  days_to_max = int(max_idx) + 1
  days_to_min = int(min_idx) + 1

  # 極值報酬率 (%)
  max_perf_pct = ((max_price_1y - close_t0) / close_t0) * 100.0
  min_perf_pct = ((min_price_1y - close_t0) / close_t0) * 100.0

  # 3. 計算【創高前最大回撤 % (Max Drawdown Before Peak)】
  # 觀察區間：從 T+1 日起算直到「達 1Y 最高價」當天為止，過程中的最低價與最大拉回 %
  df_before_peak = df_window.iloc[: max_idx + 1]
  lowest_before_peak = float(df_before_peak["min"].min())
  mdd_before_peak_pct = (
      (lowest_before_peak - close_t0) / close_t0
  ) * 100.0


  # 4. 自動判定走勢類別標籤 (Category_Tag: Cat1 ~ Cat4)
  # 判斷最低點日期是否早於最高點日期 (Date_min < Date_max，即先甩轎/跌破)
  is_pullback_first = days_to_min < days_to_max

  PULLBACK_LIMIT_PCT = -15.0
   
  if is_pullback_first:
    # 第一種情況：最低點先發生 (is_pullback_first == True)
    if min_perf_pct < PULLBACK_LIMIT_PCT:
        category_tag = "Cat3_深跌陷阱"
    elif max_perf_pct >= 50.0:
        category_tag = "Cat1_飆股"
    elif max_perf_pct >= 20.0:
        category_tag = "Cat2_溫和上漲"
    else:
        category_tag = "Cat4_窄幅橫盤"
  else:
    # 第二種情況：最高點先發生 (is_pullback_first == False)
    # 往前找最高點前的最低點 (mdd_before_peak_pct)
    if mdd_before_peak_pct < PULLBACK_LIMIT_PCT:
        category_tag = "Cat3_深跌陷阱"
    elif max_perf_pct >= 50.0:
        category_tag = "Cat1_飆股"
    elif max_perf_pct >= 20.0:
        category_tag = "Cat2_溫和上漲"
    else:
        category_tag = "Cat4_窄幅橫盤"
    
  """
  # 4. 自動判定走勢類別標籤 (Category_Tag: Cat 1 ~ Cat 4)
  # - Cat 1 飆股：1Y 最高報酬 >= +50% 且未跌破 -20% 毀滅性崩跌
  # - Cat 2 小漲：1Y 最高報酬在 +15% ~ +50% 之間
  # - Cat 3 陷阱股：1Y 最低報酬 <= -15% 且最高報酬未達 +30%
  # - Cat 4 盤整：1Y 最高與最低報酬均維持在 -15% ~ +15% 之間
  if max_perf_pct >= 50.0 and min_perf_pct > -20.0:
    category_tag = "Cat1_飆股"
  elif min_perf_pct <= -15.0 and max_perf_pct < 30.0:
    category_tag = "Cat3_陷阱股"
  elif 15.0 <= max_perf_pct < 50.0:
    category_tag = "Cat2_小漲"
  else:
    category_tag = "Cat4_盤整"
  """

  extremes_dict = {
      # -----------------------------------------------------------------
      # 🏆 1Y 極值與可讀字串報表
      # -----------------------------------------------------------------
      "1Y內最高績效": f"{max_perf_pct:+.2f}% ({max_date_1y})",
      "1Y內最低績效": f"{min_perf_pct:+.2f}% ({min_date_1y})",
      # -----------------------------------------------------------------
      # ⏱️ 軌跡與天數細節 (供敏感度分析與 Excel 分析)
      # -----------------------------------------------------------------
      "1Y最高價": round(max_price_1y, 2),
      "1Y最高天數": days_to_max,
      "1Y最低價": round(min_price_1y, 2),
      "1Y最低天數": days_to_min,
      "創高前最大回撤(%)": round(mdd_before_peak_pct, 2),
      "最大波段浮盈_MFE(%)": round(max_perf_pct, 2),
      "最大波段浮虧_MAE(%)": round(min_perf_pct, 2),
      "走勢類別標籤": category_tag,
  }

  return extremes_dict

def calculate_forward_horizon_returns_old(stock_id, trigger_date_str, global_df, horizons=[3, 5, 10, 20]):
    """
    【前瞻區間績效】計算特定股票在條件觸發後，多個不同時間視野（如 3, 5, 10, 20 天）後的報酬率與股價。
    """
    df_stock = global_df[global_df['stock_id'] == stock_id].sort_values('date').reset_index(drop=True)
    if df_stock.empty: return {}
    
    trigger_idx_list = df_stock[df_stock['date'] <= trigger_date_str].index
    if len(trigger_idx_list) == 0: return {}
    
    trigger_idx = trigger_idx_list[-1]
    entry_price = df_stock.loc[trigger_idx, 'close']
    
    perf_results = {}
    
    for h in horizons:
        target_idx = trigger_idx + h
        if target_idx < len(df_stock):
            target_row = df_stock.iloc[target_idx]
            target_date = target_row['date']
            target_price = target_row['close']
            
            if entry_price > 0:
                return_val = ((target_price - entry_price) / entry_price) * 100
                perf_results[f"T+{h}日績效"] = f"{round(return_val, 2)}% ({target_date}, 價:{target_price})"
            else:
                perf_results[f"T+{h}日績效"] = "基準價異常"
        else:
            perf_results[f"T+{h}日績效"] = "資料不足 (未滿交易日)"
            
    return perf_results


def calculate_one_year_extremes_old(stock_id, trigger_date_str, global_df):
    """
    【區間極值績效】計算特定股票在觸發日期之後，一年內(240個交易日)的最高與最低績效。
    並透過特殊符號標註時序：先發生的日期用 $$ 框住，後發生的日期用 () 框住。
    """
    df_stock = global_df[global_df['stock_id'] == stock_id].sort_values('date').reset_index(drop=True)
    if df_stock.empty: return {}
    
    trigger_idx_list = df_stock[df_stock['date'] <= trigger_date_str].index
    if len(trigger_idx_list) == 0: return {}
    
    trigger_idx = trigger_idx_list[-1]
    entry_price = df_stock.loc[trigger_idx, 'close']
    
    # 擷取未來一年（240個交易日）的資料
    df_future = df_stock.iloc[trigger_idx + 1 : trigger_idx + 241]
    perf_results = {}
    
    if df_future.empty:
        perf_results["1Y內最高績效"] = "資料不足"
        perf_results["1Y內最低績效"] = "資料不足"
        return perf_results

    # 1. 找出最高與最低價的資料列與索引
    max_idx = df_future['close'].idxmax()

    # 【修改處】：過濾掉 close <= 0 的異常值/暫停交易值後，再找最低價的索引
    df_future_valid = df_future[df_future['close'] > 0]

    # 如果過濾後未來一年完全沒有大於 0 的有效價格（極端少見），則給予安全防護
    if df_future_valid.empty:
        perf_results["1Y內最高績效"] = "資料異常"
        perf_results["1Y內最低績效"] = "資料異常"
        return perf_results
        
    min_idx = df_future_valid['close'].idxmin()
            
    max_row = df_future.loc[max_idx]
    min_row = df_future.loc[min_idx]
    
    max_date = max_row['date']
    min_date = min_row['date']
    
    max_return = ((max_row['close'] - entry_price) / entry_price) * 100
    min_return = ((min_row['close'] - entry_price) / entry_price) * 100

    #print(f"{stock_id} ---min_date : {min_date} | min_row : {min_row['close']} | entry_price : {entry_price}-----------")
    
    # 2. 時序判定：比較 index 來決定誰先發生
    if max_idx < min_idx:
        # 最高價先發生
        max_date_fmt = f"$${max_date}$$"
        min_date_fmt = f"({min_date})"
    elif min_idx < max_idx:
        # 最低價先發生
        max_date_fmt = f"({max_date})"
        min_date_fmt = f"$${min_date}$$"
    else:
        # 同一天發生（通常是 df_future 只有一筆資料）
        max_date_fmt = f"({max_date})"
        min_date_fmt = f"({min_date})"
        
    status_suffix = "" if len(df_future) >= 240 else " (未滿1年)"
    
    # 3. 組合輸出結果
    perf_results["1Y內最高績效"] = f"{round(max_return, 2)}% {max_date_fmt}{status_suffix}"
    perf_results["1Y內最低績效"] = f"{round(min_return, 2)}% {min_date_fmt}{status_suffix}"
    
    return perf_results


def calculate_fixed_horizon_returns(stock_id, trigger_date_str, global_df):
    """
    【績效回測工具】計算特定股票在觸發日期之後 1M, 3M, 6M, 1Y 的實質績效
    """
    df_stock = global_df[global_df['stock_id'] == stock_id].sort_values('date').reset_index(drop=True)
    
    if df_stock.empty:
        return {}
    
    # 找到觸發當日在 DataFrame 中的索引位置
    trigger_idx_list = df_stock[df_stock['date'] <= trigger_date_str].index
    if len(trigger_idx_list) == 0:
        return {}
    
    trigger_idx = trigger_idx_list[-1]
    entry_price = df_stock.loc[trigger_idx, 'close']
    
    perf_results = {}
    # 交易日跨度估算 (1M=20天, 3M=60天, 6M=120天, 1Y=240天)
    horizons = {
        "1M後績效": 20,
        "3M後績效": 60,
        "6M後績效": 120,
        "1Y後績效": 240
    }
    
    for label, offset in horizons.items():
        target_idx = trigger_idx + offset
        if target_idx < len(df_stock):
            future_price = df_stock.loc[target_idx, 'close']
            future_date = df_stock.loc[target_idx, 'date']
            return_rate = ((future_price - entry_price) / entry_price) * 100
            perf_results[label] = f"{round(return_rate, 2)}% ({future_date})"
        else:
            perf_results[label] = "資料不足 (未滿期)"
            
    return perf_results
