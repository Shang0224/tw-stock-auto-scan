# utils/analytics.py
from datetime import datetime
import numpy as np
import pandas as pd

PULLBACK_LIMIT_PCT = -15.0  # 2131 版深跌門檻

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
